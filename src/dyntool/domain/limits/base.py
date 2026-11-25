"""限值模型公共基类。"""

from __future__ import annotations

from enum import StrEnum
from copy import deepcopy
from typing import Any, ClassVar, Mapping, Self

import numpy as np
import pandas as pd
import xarray as xr

from .._provenance import _ResultProvenance
from ..constants import (
    DataCategory,
    UnitSystem,
    convert_array,
    format_label_with_unit,
    normalize_unit_map,
    parse_label_unit,
    resolve_current_units,
    resolve_file_units,
)
from ..models.base import DataModelBase
from ..models._model_xarray import _ModelXarrayExchange

_STANDARD_ATTR = "_limit_standard"
_SCENE_ATTR = "_limit_scene"
_CLAUSE_ATTR = "_limit_clause"
_RESOURCE_KEY_ATTR = "_limit_resource_key"


class LimitModelBase(DataModelBase):
    """规范驱动限值模型公共基类。"""

    category: ClassVar[str | DataCategory] = "limit_model_base_internal"
    standard_enum: ClassVar[type[StrEnum]]
    _registry_name: ClassVar[str]

    def __init__(self, dataset: xr.Dataset) -> None:
        self._ds = dataset

    @classmethod
    def _validate_standard(cls, standard: StrEnum) -> None:
        if not isinstance(standard, cls.standard_enum):
            raise TypeError(f"standard 必须是 {cls.standard_enum.__name__} 枚举")

    @classmethod
    def supported_standards(cls) -> tuple[StrEnum, ...]:
        """返回当前限值类支持的标准枚举成员。"""

        from .registry import get_supported_standards

        return get_supported_standards(cls._registry_name)

    @classmethod
    def supported_scenes(cls, standard: StrEnum) -> tuple[str, ...]:
        """返回指定标准下可用的场景名称。"""

        cls._validate_standard(standard)
        from .registry import get_supported_scenes

        return get_supported_scenes(cls._registry_name, standard)

    @classmethod
    def _metadata_attrs(
        cls,
        *,
        standard: StrEnum,
        scene: str,
        clause: str,
        resource_key: str,
    ) -> dict[str, str]:
        return {
            _STANDARD_ATTR: standard.value,
            _SCENE_ATTR: scene,
            _CLAUSE_ATTR: clause,
            _RESOURCE_KEY_ATTR: resource_key,
        }

    @classmethod
    def _metadata_from_mapping(
        cls,
        data: Mapping[str, Any],
    ) -> tuple[StrEnum, str, str, str]:
        raw_standard = data.get("standard")
        if raw_standard is None:
            raise ValueError("缺少 standard 元信息。")
        try:
            standard = cls.standard_enum(str(raw_standard))
        except ValueError as error:
            raise ValueError(
                f"标准编号 {raw_standard!r} 不受支持，请使用 {cls.standard_enum.__name__} 的正式编号。"
            ) from error
        scene = str(data.get("scene") or "")
        clause = str(data.get("clause") or "")
        resource_key = str(data.get("resource_key") or "")
        if not scene:
            raise ValueError("缺少 scene 元信息。")
        if not clause:
            raise ValueError("缺少 clause 元信息。")
        if not resource_key:
            raise ValueError("缺少 resource_key 元信息。")
        return standard, scene, clause, resource_key

    @property
    def standard(self) -> StrEnum:
        """返回当前对象对应的标准。"""

        return self.standard_enum(str(self._ds.attrs[_STANDARD_ATTR]))

    @property
    def scene(self) -> str:
        """返回当前对象对应的场景。"""

        return str(self._ds.attrs[_SCENE_ATTR])

    @property
    def clause(self) -> str:
        """返回当前对象对应的规范条款。"""

        return str(self._ds.attrs[_CLAUSE_ATTR])

    @property
    def resource_key(self) -> str:
        """返回当前对象对应的资源键。"""

        return str(self._ds.attrs[_RESOURCE_KEY_ATTR])

    def _frame_attrs(self) -> dict[str, Any]:
        """生成与模型隔离的规范及追溯属性，不向数值列混入元信息。"""
        return {
            "standard": self.standard.value,
            "scene": self.scene,
            "clause": self.clause,
            "resource_key": self.resource_key,
            "_dyntool": deepcopy(self._provenance),
        }

    def _restore_frame_provenance(self, frame: pd.DataFrame) -> Self:
        """恢复可选追溯；旧表缺少依据时继续保持来源未知。"""
        if frame.attrs.get("_dyntool") is not None:
            self.__dict__["_provenance"] = _ResultProvenance.validate(frame.attrs["_dyntool"])
        return self

    def to_xarray(self) -> xr.Dataset:
        """导出独立 xarray 快照，保留数值形状、字段单位、规范来源和追溯。"""
        snapshot = self._ds.copy(deep=True)
        snapshot.attrs = self._frame_attrs()
        snapshot.attrs["_units"] = self.current_units()
        snapshot.attrs["_category"] = self._normalize_category(self.category)
        snapshot.attrs["_model_type"] = type(self).__name__
        return snapshot

    @classmethod
    def from_xarray(
        cls,
        xr_obj: xr.Dataset | xr.DataArray,
        *,
        units: Mapping[str, str | None] | None = None,
    ) -> Self:
        """从带规范 attrs 的 xarray 快照恢复，字段单位与可选单位映射须一致。"""
        if not isinstance(xr_obj, (xr.Dataset, xr.DataArray)):
            raise TypeError(f"不支持的 xarray 对象类型：{type(xr_obj).__name__}")
        assert cls.value_field is not None
        source = xr_obj.to_dataset(name=cls.value_field) if isinstance(xr_obj, xr.DataArray) else xr_obj
        expected = {cls.value_field}
        if cls.axis_field is not None:
            expected.add(cls.axis_field)
        missing = expected - set(source.variables)
        if missing:
            raise ValueError(f"限值 xarray 缺少字段：{', '.join(sorted(missing))}")
        parsed_units = normalize_unit_map({name: source[name].attrs.get("units") for name in expected})
        current = _ModelXarrayExchange.units(xr_obj, parsed_units, units)
        payload = dict(xr_obj.attrs)
        payload.update({name: source[name].to_numpy() for name in expected})
        payload["_units"] = current
        return cls.from_dict(payload, units=units)


class ScalarLimitBase(LimitModelBase):
    """标量限值公共基类。"""

    category: ClassVar[str | DataCategory] = "scalar_limit_base_internal"
    axis_field: ClassVar[str | None] = None

    @classmethod
    def _default_current_units(cls, unit_system: UnitSystem | None = None) -> dict[str, str]:
        raise NotImplementedError

    @classmethod
    def _resolve_current_units(
        cls,
        *,
        units: Mapping[str, str | None] | None = None,
        unit_system: UnitSystem | None = None,
    ) -> dict[str, str]:
        return resolve_current_units(cls._default_current_units(unit_system), units=units)

    @classmethod
    def _from_base_data(
        cls,
        *,
        value: float,
        standard: StrEnum,
        scene: str,
        clause: str,
        resource_key: str,
        units: Mapping[str, str | None] | None = None,
        unit_system: UnitSystem | None = None,
    ) -> Self:
        current = cls._resolve_current_units(units=units, unit_system=unit_system)
        assert cls.value_field is not None
        ds = xr.Dataset(
            {
                cls.value_field: ((), float(value), {"units": current[cls.value_field]}),
            },
            attrs=cls._metadata_attrs(
                standard=standard,
                scene=scene,
                clause=clause,
                resource_key=resource_key,
            ),
        )
        return cls(ds)

    def current_units(self) -> dict[str, str]:
        """返回当前对象对外暴露的单位映射。"""

        return self.base_units()

    def base_units(self) -> dict[str, str]:
        """返回模型当前记录的字段单位。"""

        assert self.value_field is not None
        default_units = self._default_current_units()
        return {self.value_field: str(self._ds[self.value_field].attrs.get("units", default_units[self.value_field]))}

    def get_field(self, name: str, unit: str | None = None) -> np.ndarray:
        """读取标量限值字段。"""

        if name != self.value_field:
            raise KeyError(f"{self.__class__.__name__} 不暴露字段 {name!r}。")
        assert self.value_field is not None
        source = self.base_units()[self.value_field]
        return convert_array(
            np.asarray(self._ds[self.value_field].values),
            from_unit=source,
            to_unit=unit or source,
        )

    def convert_units(
        self,
        units: Mapping[str, str | None],
        *,
        replace: bool = True,
    ) -> Self:
        """将标量限值转换到目标单位视图。"""

        current = self.current_units().copy()
        current.update(normalize_unit_map(units))
        assert self.value_field is not None
        converted = self.__class__._from_base_data(
            value=float(
                convert_array(
                    np.asarray(self._ds[self.value_field].values),
                    from_unit=self.base_units()[self.value_field],
                    to_unit=current[self.value_field],
                ).flat[0]
            ),
            standard=self.standard,
            scene=self.scene,
            clause=self.clause,
            resource_key=self.resource_key,
            units=current,
        )
        if replace:
            self._ds = converted._ds
            return self
        return converted

    def to_dict(self) -> dict[str, Any]:
        """导出字典载荷。"""

        assert self.value_field is not None
        return {
            self.value_field: self.get_field(self.value_field),
            "standard": self.standard.value,
            "scene": self.scene,
            "clause": self.clause,
            "resource_key": self.resource_key,
            "_units": self.current_units(),
        }

    def to_pandas(self) -> pd.DataFrame:
        """导出单行数值表，attrs 携带独立的规范来源和可选追溯。"""

        assert self.value_field is not None
        frame = pd.DataFrame(
            [
                {
                    format_label_with_unit(self.value_field, self.current_units()[self.value_field]): float(
                        self.get_field(self.value_field).flat[0]
                    )
                }
            ]
        ).rename_axis(index=None)
        frame.attrs = self._frame_attrs()
        return frame

    @classmethod
    def from_pandas(
        cls,
        df: pd.DataFrame,
        *,
        units: Mapping[str, str | None] | None = None,
        unit_system: UnitSystem | None = None,
    ) -> Self:
        """从恰好一行的数值表及 attrs 中恢复标量限值和可选追溯。"""

        if len(df) != 1:
            raise ValueError(f"{cls.__name__}.from_pandas 必须恰好有一行标量数据。")
        assert cls.value_field is not None
        columns_by_name: dict[str, str] = {}
        parsed_units: dict[str, str | None] = {}
        for col in df.columns:
            name, unit = parse_label_unit(col)
            columns_by_name[name] = col
            parsed_units[name] = unit
        current = resolve_file_units(
            {cls.value_field},
            parsed_units=parsed_units,
            units=units,
            allow_partial=True,
        )
        standard, scene, clause, resource_key = cls._metadata_from_mapping(df.attrs)
        return cls._from_base_data(
            value=float(df.iloc[0][columns_by_name[cls.value_field]]),
            standard=standard,
            scene=scene,
            clause=clause,
            resource_key=resource_key,
            units=current if current else units,
            unit_system=unit_system,
        )._restore_frame_provenance(df)

    @classmethod
    def from_dict(
        cls,
        data: Mapping[str, Any],
        category: DataCategory | None = None,
        *,
        units: Mapping[str, str | None] | None = None,
    ) -> Self:
        """从字典恢复恰好一个标量；缺值、空数组和多个值均明确拒绝。"""

        del category
        assert cls.value_field is not None
        if cls.value_field not in data or np.asarray(data[cls.value_field]).size != 1:
            raise ValueError(f"{cls.__name__} 需要单个 {cls.value_field} 标量。")
        current = resolve_file_units(
            {cls.value_field},
            parsed_units=data.get("_units", {}),
            units=units,
            allow_partial=True,
        )
        standard, scene, clause, resource_key = cls._metadata_from_mapping(data)
        return cls._from_base_data(
            value=float(np.asarray(data[cls.value_field]).flat[0]),
            standard=standard,
            scene=scene,
            clause=clause,
            resource_key=resource_key,
            units=current if current else units,
        )


class CurveLimitBase(LimitModelBase):
    """曲线限值公共基类。"""

    category: ClassVar[str | DataCategory] = "curve_limit_base_internal"

    @classmethod
    def _default_current_units(cls, unit_system: UnitSystem | None = None) -> dict[str, str]:
        raise NotImplementedError

    @classmethod
    def _resolve_current_units(
        cls,
        *,
        units: Mapping[str, str | None] | None = None,
        unit_system: UnitSystem | None = None,
    ) -> dict[str, str]:
        return resolve_current_units(cls._default_current_units(unit_system), units=units)

    @classmethod
    def _from_base_data(
        cls,
        *,
        axis: np.ndarray,
        values: np.ndarray,
        standard: StrEnum,
        scene: str,
        clause: str,
        resource_key: str,
        units: Mapping[str, str | None] | None = None,
        unit_system: UnitSystem | None = None,
    ) -> Self:
        current = cls._resolve_current_units(units=units, unit_system=unit_system)
        assert cls.axis_field is not None
        assert cls.value_field is not None
        ds = xr.Dataset(
            {
                cls.value_field: (
                    [cls.axis_field],
                    np.asarray(values, dtype=np.float64).flatten(),
                    {"units": current[cls.value_field]},
                ),
            },
            coords={
                cls.axis_field: (
                    cls.axis_field,
                    np.asarray(axis, dtype=np.float64).flatten(),
                    {"units": current[cls.axis_field]},
                )
            },
            attrs=cls._metadata_attrs(
                standard=standard,
                scene=scene,
                clause=clause,
                resource_key=resource_key,
            ),
        )
        return cls(ds)

    def current_units(self) -> dict[str, str]:
        """返回当前对象对外暴露的单位映射。"""

        return self.base_units()

    def base_units(self) -> dict[str, str]:
        """返回曲线限值的字段单位。"""

        assert self.axis_field is not None
        assert self.value_field is not None
        default_units = self._default_current_units()
        return {
            self.axis_field: str(self._ds.coords[self.axis_field].attrs.get("units", default_units[self.axis_field])),
            self.value_field: str(self._ds[self.value_field].attrs.get("units", default_units[self.value_field])),
        }

    def get_field(self, name: str, unit: str | None = None) -> np.ndarray:
        """读取曲线限值字段。"""

        assert self.axis_field is not None
        assert self.value_field is not None
        if name == self.axis_field:
            source = self.base_units()[self.axis_field]
            return convert_array(
                np.asarray(self._ds.coords[self.axis_field].values),
                from_unit=source,
                to_unit=unit or source,
            )
        if name != self.value_field:
            raise KeyError(f"{self.__class__.__name__} 不暴露字段 {name!r}。")
        source = self.base_units()[self.value_field]
        return convert_array(
            np.asarray(self._ds[self.value_field].values),
            from_unit=source,
            to_unit=unit or source,
        )

    def convert_units(
        self,
        units: Mapping[str, str | None],
        *,
        replace: bool = True,
    ) -> Self:
        """将曲线限值转换到目标单位视图。"""

        current = self.current_units().copy()
        current.update(normalize_unit_map(units))
        assert self.axis_field is not None
        assert self.value_field is not None
        converted = self.__class__._from_base_data(
            axis=convert_array(
                np.asarray(self._ds.coords[self.axis_field].values),
                from_unit=self.base_units()[self.axis_field],
                to_unit=current[self.axis_field],
            ),
            values=convert_array(
                np.asarray(self._ds[self.value_field].values),
                from_unit=self.base_units()[self.value_field],
                to_unit=current[self.value_field],
            ),
            standard=self.standard,
            scene=self.scene,
            clause=self.clause,
            resource_key=self.resource_key,
            units=current,
        )
        if replace:
            self._ds = converted._ds
            return self
        return converted

    def to_dict(self) -> dict[str, Any]:
        """导出字典载荷。"""

        assert self.axis_field is not None
        assert self.value_field is not None
        return {
            self.axis_field: self.get_field(self.axis_field),
            self.value_field: self.get_field(self.value_field),
            "standard": self.standard.value,
            "scene": self.scene,
            "clause": self.clause,
            "resource_key": self.resource_key,
            "_units": self.current_units(),
        }

    def to_pandas(self) -> pd.DataFrame:
        """导出曲线数值表，attrs 携带独立的规范来源和可选追溯。"""

        assert self.axis_field is not None
        assert self.value_field is not None
        frame = pd.DataFrame(
            {
                format_label_with_unit(self.value_field, self.current_units()[self.value_field]): self.get_field(
                    self.value_field
                )
            },
            index=pd.Index(
                self.get_field(self.axis_field),
                name=format_label_with_unit(self.axis_field, self.current_units()[self.axis_field]),
            ),
        )
        frame.attrs = self._frame_attrs()
        return frame

    @classmethod
    def from_pandas(
        cls,
        df: pd.DataFrame,
        *,
        units: Mapping[str, str | None] | None = None,
        unit_system: UnitSystem | None = None,
    ) -> Self:
        """从数值表及 attrs 中的规范来源、可选追溯恢复曲线限值。"""

        assert cls.axis_field is not None
        assert cls.value_field is not None
        _, axis_unit = parse_label_unit(df.index.name or cls.axis_field)
        columns_by_name: dict[str, str] = {}
        parsed_units: dict[str, str | None] = {cls.axis_field: axis_unit}
        for col in df.columns:
            name, unit = parse_label_unit(col)
            columns_by_name[name] = col
            parsed_units[name] = unit
        current = resolve_file_units(
            {cls.axis_field, cls.value_field},
            parsed_units=parsed_units,
            units=units,
            allow_partial=True,
        )
        standard, scene, clause, resource_key = cls._metadata_from_mapping(df.attrs)
        return cls._from_base_data(
            axis=df.index.to_numpy(),
            values=df[columns_by_name[cls.value_field]].to_numpy(),
            standard=standard,
            scene=scene,
            clause=clause,
            resource_key=resource_key,
            units=current if current else units,
            unit_system=unit_system,
        )._restore_frame_provenance(df)

    @classmethod
    def from_dict(
        cls,
        data: Mapping[str, Any],
        category: DataCategory | None = None,
        *,
        units: Mapping[str, str | None] | None = None,
    ) -> Self:
        """从字典恢复曲线限值对象。"""

        del category
        assert cls.axis_field is not None
        assert cls.value_field is not None
        current = resolve_file_units(
            {cls.axis_field, cls.value_field},
            parsed_units=data.get("_units", {}),
            units=units,
            allow_partial=True,
        )
        standard, scene, clause, resource_key = cls._metadata_from_mapping(data)
        return cls._from_base_data(
            axis=np.asarray(data.get(cls.axis_field, [])),
            values=np.asarray(data.get(cls.value_field, [])),
            standard=standard,
            scene=scene,
            clause=clause,
            resource_key=resource_key,
            units=current if current else units,
        )


__all__ = ["CurveLimitBase", "LimitModelBase", "ScalarLimitBase"]
