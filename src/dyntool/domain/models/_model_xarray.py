"""Private / implementation detail：模型快照的单位、形状及追溯交换。"""

from __future__ import annotations

from copy import deepcopy
from inspect import signature
from typing import TYPE_CHECKING, Any, Mapping

import numpy as np
import xarray as xr

from .._provenance import _ResultProvenance
from ..constants import convert_array, normalize_unit_map

if TYPE_CHECKING:
    from .base import DataModelBase


class _ModelXarrayExchange:
    """复用模型恢复边界，避免 Dataset 与 DataArray 单位合同分叉。"""

    @staticmethod
    def annotate(model: DataModelBase, snapshot: xr.Dataset | xr.DataArray) -> xr.Dataset | xr.DataArray:
        """给独立快照附加当前表示和已有计算依据。"""
        snapshot.attrs["_units"] = model.current_units()
        snapshot.attrs["_dyntool"] = deepcopy(model._provenance)
        snapshot.attrs["_model_type"] = type(model).__name__
        return snapshot

    @classmethod
    def export(cls, model: DataModelBase) -> xr.Dataset | xr.DataArray:
        """保留模型原有 xarray 类型，复合模型使用共享轴 Dataset。"""
        snapshot = getattr(model, "xr", None)
        if snapshot is not None:
            return snapshot
        stored = getattr(model, "_ds", None)
        if isinstance(stored, xr.Dataset):
            return cls.annotate(model, stored.copy(deep=True))
        components = getattr(type(model), "_xarray_components", {})
        if components:
            axis = model.axis_field
            assert axis is not None
            ds = xr.Dataset(coords={axis: (axis, model.get_axis().copy(), {"units": model.axis_unit})})
            records = {}
            for name in components:
                component = getattr(model, name)
                if component is None:
                    continue
                field = "phase" if name == "pha" else name
                ds[field] = xr.DataArray(
                    component.get_value().copy(), dims=(axis,), attrs={"units": component.value_unit}
                )
                records[name] = {"units": component.current_units(), "_dyntool": deepcopy(component._provenance)}
            ds.attrs["_components"] = records
            return cls.annotate(model, ds)
        # 保留已有自定义模型的自动导出能力，避免通过修复正式模型删除扩展路径。
        payload = model.to_dict()
        axis = model.axis_field
        coords: dict[str, Any] = {}
        if axis is not None and axis in payload:
            coords[axis] = (axis, np.asarray(payload[axis]).copy(), {"units": model.axis_unit})
        variables: dict[str, Any] = {}
        units = model.current_units()
        for name, value in payload.items():
            if name in {"_units", "_dyntool", *coords} or value is None or isinstance(value, Mapping):
                continue
            values = np.asarray(value)
            dims = tuple(
                axis
                if index == 0 and axis in coords and values.shape[0] == len(payload[axis])
                else f"{name}_dim_{index}"
                for index in range(values.ndim)
            )
            variables[name] = (dims, values.copy(), {"units": units.get(name)})
        if not variables:
            raise TypeError(f"{type(model).__name__} 无法自动导出为 xarray")
        return cls.annotate(model, xr.Dataset(variables, coords=coords))

    @staticmethod
    def units(
        source: xr.Dataset | xr.DataArray, fields: Mapping[str, str | None], explicit: Mapping[str, str | None] | None
    ) -> dict[str, str]:
        """重复单位可使用别名，但转换后必须保持相同尺度和偏移。"""
        result: dict[str, str] = {}
        declarations = [fields, source.attrs.get("_units", {}), source.attrs.get("_current_units", {}), explicit or {}]
        for declaration in declarations:
            for name, unit in normalize_unit_map(declaration).items():
                if name in result and not np.array_equal(
                    convert_array(np.array([0.0, 1.0]), from_unit=unit, to_unit=result[name]), [0.0, 1.0]
                ):
                    raise ValueError(f"xarray 字段单位与重复单位声明不一致：{name}")
                result.setdefault(name, unit)
        return result

    @classmethod
    def restore(
        cls,
        model_type: type[DataModelBase],
        source: xr.Dataset | xr.DataArray,
        explicit: Mapping[str, str | None] | None,
    ) -> DataModelBase:
        """按字段恢复，原始 TypeError 直接传播，不再次尝试另一条恢复路径。"""
        if not isinstance(source, (xr.Dataset, xr.DataArray)):
            raise TypeError(f"不支持的 xarray 对象类型：{type(source).__name__}")
        fields: dict[str, Any] = {}
        declared: dict[str, str | None] = {}
        if isinstance(source, xr.DataArray):
            field = model_type.value_field
            if field is None:
                raise ValueError("组合模型需要含各分量字段的 Dataset")
            fields[field] = source.to_numpy()
            declared[field] = source.attrs.get("units")
            axis = model_type.axis_field
            if axis is not None:
                dim = source.dims[0] if source.dims else axis
                fields[axis] = (
                    source.coords[dim].to_numpy() if dim in source.coords else np.arange(source.shape[0], dtype=float)
                )
                if dim in source.coords:
                    declared[axis] = source.coords[dim].attrs.get("units")
        else:
            for name, variable in source.variables.items():
                field = model_type.axis_field if name == getattr(model_type, "_xarray_axis_key", None) else str(name)
                assert field is not None
                if field in fields:
                    raise ValueError(f"xarray 重复声明轴字段：{field}")
                fields[field] = variable.to_numpy()
                declared[field] = variable.attrs.get("units")
        units = cls.units(source, declared, explicit)
        components = getattr(model_type, "_xarray_components", {})
        if components:
            payload: dict[str, Any] = {}
            axis = model_type.axis_field
            assert axis is not None
            records = source.attrs.get("_components", {})
            for name, component_type in components.items():
                field = "phase" if name == "pha" else name
                if field not in fields:
                    continue
                record = records.get(name, {})
                component_units = dict(record.get("units", {}))
                axis_unit = component_units.get(axis, units.get(axis))
                values = fields[axis]
                if axis_unit is not None and units.get(axis) is not None:
                    values = convert_array(values, from_unit=units[axis], to_unit=axis_unit)
                value_unit = units.get(field)
                stored_value_unit = component_units.get(component_type.value_field)
                if (
                    value_unit is not None
                    and stored_value_unit is not None
                    and not np.array_equal(
                        convert_array(np.array([0.0, 1.0]), from_unit=value_unit, to_unit=stored_value_unit), [0.0, 1.0]
                    )
                ):
                    raise ValueError(f"xarray 分量单位与字段单位声明不一致：{name}")
                if axis_unit is not None:
                    component_units[axis] = axis_unit
                if value_unit is not None:
                    component_units[component_type.value_field] = value_unit
                payload_axis = getattr(component_type, "_xarray_axis_key", axis)
                payload[name] = {
                    payload_axis: values,
                    component_type.value_field: fields[field],
                    "_units": component_units,
                }
                if "_dyntool" in record:
                    payload[name]["_dyntool"] = record["_dyntool"]
        else:
            payload = {**fields, "_units": units}
            axis = model_type.axis_field
            payload_axis = getattr(model_type, "_xarray_axis_key", axis)
            if axis is not None and axis != payload_axis and axis in payload:
                payload[payload_axis] = payload.pop(axis)
        if "_dyntool" in source.attrs:
            payload["_dyntool"] = _ResultProvenance.validate(source.attrs["_dyntool"])
        options = {"units": units or None} if "units" in signature(model_type.from_dict).parameters else {}
        return model_type.from_dict(payload, **options)
