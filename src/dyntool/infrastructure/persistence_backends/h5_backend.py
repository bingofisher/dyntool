"""基础设施层 HDF5 持久化后端。"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import json

import h5py
import numpy as np

from ...domain.constants import DataCategory, normalize_unit_map
from ..storage_options import resolve_h5_dataset_options


class _H5UnitInspector:
    """仅遍历结构与属性，不读取 Dataset 数值。"""

    @classmethod
    def collect(cls, group: h5py.Group, prefix: str = "") -> dict[str, str]:
        """返回字段路径与当前单位。"""
        units: dict[str, str] = {}
        for name, node in group.items():
            path = f"{prefix}.{name}" if prefix else str(name)
            if isinstance(node, h5py.Group):
                units.update(cls.collect(node, path))
            elif "unit" in node.attrs:
                unit = node.attrs["unit"]
                units[path] = unit.decode("utf-8") if isinstance(unit, bytes) else str(unit)
        return units


def _write_mapping(
    group: h5py.Group,
    data: Mapping[str, Any],
    *,
    dataset_options: Mapping[str, Any] | None = None,
) -> None:
    units = normalize_unit_map(data.get("_units")) if isinstance(data.get("_units"), Mapping) else {}
    for key, value in data.items():
        if key == "_dyntool":
            group.attrs["_dyntool"] = json.dumps(value, ensure_ascii=False)
            continue
        if key == "_units" or value is None:
            continue
        if isinstance(value, Mapping):
            subgroup = group.create_group(str(key))
            _write_mapping(subgroup, value, dataset_options=dataset_options)
            continue
        arr = np.asarray(value)
        if arr.dtype.kind == "U":
            arr = arr.astype(h5py.string_dtype(encoding="utf-8"))
        effective_dataset_options = {} if arr.shape == () else dict(dataset_options or {})
        dataset = group.create_dataset(str(key), data=arr, **effective_dataset_options)
        unit = units.get(str(key))
        if unit:
            dataset.attrs["unit"] = unit


def _read_mapping(group: h5py.Group) -> dict[str, Any]:
    data: dict[str, Any] = {}
    units: dict[str, str] = {}
    for key, value in group.items():
        if isinstance(value, h5py.Group):
            data[key] = _read_mapping(value)
            continue
        arr = value.asstr()[()] if h5py.check_string_dtype(value.dtype) is not None else value[()]
        data[key] = arr
        if "unit" in value.attrs:
            unit = value.attrs["unit"]
            if isinstance(unit, bytes):
                unit = unit.decode("utf-8")
            units[key] = str(unit)
    if units:
        data["_units"] = units
    if "_dyntool" in group.attrs:
        data["_dyntool"] = json.loads(str(group.attrs["_dyntool"]))
    return data


class H5Backend:
    """通过 HDF5 读写带字段单位的模型。"""

    def save(self, path: Path, model: Any, **options: Any) -> None:
        """保存模型到 HDF5。"""

        path = Path(path)
        if not hasattr(model, "to_dict"):
            raise TypeError(f"{type(model).__name__} must implement to_dict().")
        data = model.to_dict()
        path.parent.mkdir(parents=True, exist_ok=True)
        dataset_options = resolve_h5_dataset_options(dataset_options=options.get("dataset_options"))
        with h5py.File(path, "w") as handle:
            _write_mapping(handle, data, dataset_options=dataset_options)

    def load(
        self,
        path: Path,
        category: DataCategory | None = None,
        **options: Any,
    ) -> Any:
        """从 HDF5 加载模型。"""

        path = Path(path)
        if category is None:
            raise ValueError("Loading a model from HDF5 requires `category`.")
        units = options.pop("units", None)

        from ...domain.models import DataModelBase

        cls = DataModelBase.from_category(category)
        if not hasattr(cls, "from_dict"):
            raise TypeError(f"{cls.__name__} must implement from_dict().")
        with h5py.File(path, "r") as handle:
            data = _read_mapping(handle)
        return cls.from_dict(data, units=units)

    def inspect_units(
        self,
        path: Path,
        category: DataCategory | None = None,
        **options: Any,
    ) -> dict[str, str]:
        """在不加载模型对象的前提下检查 HDF5 中的单位信息。"""

        del category, options
        path = Path(path)
        with h5py.File(path, "r") as handle:
            return _H5UnitInspector.collect(handle)


__all__ = ["H5Backend"]
