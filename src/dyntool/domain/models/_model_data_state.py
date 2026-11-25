"""模型的不可变载荷、独立快照与拥有者通知。"""

from __future__ import annotations

from copy import copy, deepcopy
from functools import wraps
from typing import Any
import weakref
from inspect import signature

from .._provenance import _ResultProvenance

import numpy as np
import xarray as xr


class _ModelRepresentationUpdate:
    """发布单位表示，并在通知失败时恢复模型及拥有者聚合状态。"""

    def __init__(self, model: Any, converted: Any) -> None:
        self.model = model
        self.converted = converted
        owner_ref = model.__dict__.get("_owner_ref")
        self.owner = owner_ref() if owner_ref is not None else None
        self.slot = model.__dict__.get("_owner_slot")

    def apply(self) -> None:
        """先保存旧状态，再发布并通知；数组仍共享不可变载荷。"""
        from .base import DataModelBase

        model, owner = self.model, self.owner
        previous = dict(model.__dict__)
        root = owner._data_map.get(self.slot) if owner is not None else None
        root_provenance = deepcopy(root._provenance) if root is not None else None
        states = deepcopy(owner._slot_state) if owner is not None else None
        dirty = set(owner._dirty_categories) if owner is not None else None
        collection = owner._storage_set if owner is not None else None
        collection_dirty = collection.storage_dirty if collection is not None else False
        try:
            if owner is not None:
                for component in model.__dict__.values():
                    if isinstance(component, DataModelBase):
                        _ModelDataState.detach_owner(component, owner)
            model.__dict__.clear()
            model.__dict__.update(self.converted.__dict__)
            if owner is not None:
                _ModelDataState.bind_owner(model, owner, self.slot)
                owner._on_model_representation_changed(self.slot)
        except BaseException:
            if owner is not None:
                _ModelDataState.detach_owner(model, owner)
            model.__dict__.clear()
            model.__dict__.update(previous)
            if owner is not None:
                _ModelDataState.bind_owner(model, owner, self.slot)
                owner._slot_state = states
                owner._dirty_categories = dirty
            if root is not None:
                root.__dict__["_provenance"] = root_provenance
            if collection is not None:
                collection.storage_dirty = collection_dirty
            raise


class _ModelDataState:
    """集中管理现有模型的数据访问和受控表示更新。"""

    @classmethod
    def prepare_class(cls, model_type: type) -> None:
        """为模型自身声明的入口安装同一访问合同，保留原签名。"""
        constructor = model_type.__dict__.get("__init__")
        if constructor is not None:

            @wraps(constructor)
            def initialize(model: Any, *args: Any, **kwargs: Any) -> None:
                constructor(model, *args, **kwargs)
                cls.freeze_owned(model)

            model_type.__init__ = initialize
        getter = model_type.__dict__.get("get_field")
        if getter is not None:

            @wraps(getter)
            def read(model: Any, *args: Any, **kwargs: Any) -> np.ndarray:
                values = np.asarray(getter(model, *args, **kwargs))
                if values.flags.writeable:
                    values.setflags(write=False)
                result = values.view()
                result.setflags(write=False)
                return result

            model_type.get_field = read
        for name in ("xr", "xr_base"):
            prop = model_type.__dict__.get(name)
            if isinstance(prop, property) and prop.fget is not None:
                model_type_prop = cls.snapshot_property(prop)
                setattr(model_type, name, model_type_prop)
        converter = model_type.__dict__.get("convert_units")
        if converter is not None:

            @wraps(converter)
            def convert(model: Any, units: Any, *, replace: bool = True) -> Any:
                converted = converter(model, units, replace=False)
                converted.__dict__["_provenance"] = deepcopy(model._provenance)
                converted._provenance["output_units"] = converted.current_units()
                if not replace:
                    return converted
                _ModelRepresentationUpdate(model, converted).apply()
                return model

            model_type.convert_units = convert

        for name, method in tuple(model_type.__dict__.items()):
            if (
                name.startswith(("calc_", "eval_", "filter_", "resample_")) or name in {"truncate", "baseline_correct"}
            ) and callable(method):
                setattr(model_type, name, cls.calculation(method, name))
        exporter = model_type.__dict__.get("to_dict")
        if exporter is not None:

            @wraps(exporter)
            def export(model: Any) -> dict[str, Any]:
                payload = exporter(model)
                payload["_dyntool"] = deepcopy(model._provenance)
                return payload

            model_type.to_dict = export
        importer = model_type.__dict__.get("from_dict")
        if isinstance(importer, classmethod):
            original = importer.__func__

            @wraps(original)
            def restore(model_class: type, data: Any, *args: Any, **options: Any) -> Any:
                payload = dict(data)
                record = payload.pop("_dyntool", None)
                result = original(model_class, payload, *args, **options)
                if record is not None:
                    result.__dict__["_provenance"] = _ResultProvenance.validate(record)
                return result

            model_type.from_dict = classmethod(restore)

    @staticmethod
    def calculation(method: Any, name: str) -> Any:
        """在现有数值入口完成后记录依据，保留原签名和结果类型。"""

        @wraps(method)
        def calculate(model: Any, *args: Any, **kwargs: Any) -> Any:
            from .base import DataModelBase

            result = method(model, *args, **kwargs)
            if isinstance(result, DataModelBase):
                bound = signature(method).bind(model, *args, **kwargs)
                bound.apply_defaults()
                parameters = {key: value for key, value in bound.arguments.items() if key != "self"}
                _ResultProvenance.computed(model, result, name, parameters)
            return result

        return calculate

    @staticmethod
    def snapshot_property(prop: property) -> property:
        """保留 xarray 返回类型，隔离数组和可变属性。"""
        getter = prop.fget
        assert getter is not None

        @wraps(getter)
        def snapshot(model: Any) -> xr.DataArray | xr.Dataset:
            from ._model_xarray import _ModelXarrayExchange

            return _ModelXarrayExchange.annotate(model, getter(model).copy(deep=True))

        return property(snapshot, doc=prop.__doc__)

    @classmethod
    def freeze_owned(cls, model: Any) -> None:
        """隔离构造输入并冻结拥有的数组。"""
        from .base import DataModelBase

        for name, value in tuple(model.__dict__.items()):
            if isinstance(value, DataModelBase):
                model.__dict__[name] = cls.clone(value)
            elif isinstance(value, (xr.DataArray, xr.Dataset)):
                owned = value.copy(deep=True)
                arrays = [owned.data] if isinstance(owned, xr.DataArray) else [v.data for v in owned.data_vars.values()]
                arrays.extend(coordinate.data for coordinate in owned.coords.values())
                for array in arrays:
                    if isinstance(array, np.ndarray):
                        array.setflags(write=False)
                model.__dict__[name] = owned
        model.__dict__.setdefault("_provenance", _ResultProvenance.unknown())

    @classmethod
    def clone(cls, model: Any, memo: dict[int, Any] | None = None) -> Any:
        """复制模型状态，共享不可变数组而不复制拥有者。"""
        memo = {} if memo is None else memo
        result = copy(model)
        memo[id(model)] = result
        result.__dict__ = {}
        for name, value in model.__dict__.items():
            if name in {"_owner_ref", "_owner_slot"}:
                continue
            if isinstance(value, (xr.DataArray, xr.Dataset)):
                shared = value.copy(deep=False)
                shared.attrs = deepcopy(value.attrs)
                for coordinate in shared.coords:
                    shared.coords[coordinate].attrs = deepcopy(value.coords[coordinate].attrs)
                result.__dict__[name] = shared
            else:
                result.__dict__[name] = deepcopy(value, memo)
        return result

    @classmethod
    def detach_owner(cls, model: Any, owner: Any) -> None:
        """卸载或替换模型时解除通知绑定，保留外部模型的独立使用能力。"""
        from .base import DataModelBase

        ref = model.__dict__.get("_owner_ref")
        if ref is None or ref() is not owner:
            return
        model.__dict__.pop("_owner_ref", None)
        model.__dict__.pop("_owner_slot", None)
        for value in model.__dict__.values():
            if isinstance(value, DataModelBase):
                cls.detach_owner(value, owner)

    @classmethod
    def bind_owner(cls, model: Any, owner: Any, slot: Any) -> Any:
        """一个可变模型壳只绑定一个样本；必要时隔离状态。"""
        old_ref = model.__dict__.get("_owner_ref")
        if (
            old_ref is not None
            and old_ref() is not None
            and (old_ref() is not owner or model.__dict__.get("_owner_slot") != slot)
        ):
            model = cls.clone(model)
        model.__dict__["_owner_ref"] = weakref.ref(owner)
        model.__dict__["_owner_slot"] = slot
        from .base import DataModelBase

        for name, value in tuple(model.__dict__.items()):
            if isinstance(value, DataModelBase):
                model.__dict__[name] = cls.bind_owner(value, owner, slot)
        return model


__all__ = ["_ModelDataState"]
