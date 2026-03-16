"""基础设施层 HDF5 持久化后端。"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import h5py
import numpy as np

from ...domain.constants import DataCategory, normalize_unit_map


def _write_mapping(
    group: h5py.Group,
    data: Mapping[str, Any],
    *,
    dataset_options: Mapping[str, Any] | None = None,
) -> None:
    units = normalize_unit_map(data.get("_units")) if isinstance(data.get("_units"), Mapping) else {}
    for key, value in data.items():
        if key == "_units" or value is None:
            continue
        if isinstance(value, Mapping):
            subgroup = group.create_group(str(key))
            _write_mapping(subgroup, value, dataset_options=dataset_options)
            continue
        arr = np.asarray(value)
        dataset = group.create_dataset(str(key), data=arr, **(dataset_options or {}))
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
        arr = value[()]
        data[key] = arr
        if "unit" in value.attrs:
            unit = value.attrs["unit"]
            if isinstance(unit, bytes):
                unit = unit.decode("utf-8")
            units[key] = str(unit)
    if units:
        data["_units"] = units
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
        dataset_options = options.get("dataset_options", {})
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
            data = _read_mapping(handle)
        units: dict[str, str] = {}

        def _collect(prefix: str, payload: Mapping[str, Any]) -> None:
            local_units = payload.get("_units", {})
            if isinstance(local_units, Mapping):
                for key, unit in local_units.items():
                    field = f"{prefix}{key}" if not prefix else f"{prefix}.{key}"
                    units[field] = str(unit)
            for key, value in payload.items():
                if key == "_units" or not isinstance(value, Mapping):
                    continue
                nested_prefix = f"{prefix}{key}" if not prefix else f"{prefix}.{key}"
                _collect(nested_prefix, value)

        _collect("", data)
        return units


__all__ = ["H5Backend"]
