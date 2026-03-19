"""限值模型公共基类。"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, ClassVar, Mapping, Self

import numpy as np
import pandas as pd
import xarray as xr

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
        standard = cls.standard_enum(str(raw_standard))
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
        """导出单行 DataFrame。"""

        assert self.value_field is not None
        return pd.DataFrame(
            [
                {
                    format_label_with_unit(self.value_field, self.current_units()[self.value_field]): float(
                        self.get_field(self.value_field).flat[0]
                    )
                }
            ]
        ).rename_axis(index=None)

    @classmethod
    def from_pandas(
        cls,
        df: pd.DataFrame,
        *,
        units: Mapping[str, str | None] | None = None,
        unit_system: UnitSystem | None = None,
    ) -> Self:
        """从 DataFrame 构建标量限值对象。"""

        if df.empty:
            raise ValueError(f"{cls.__name__}.from_pandas 至少需要一行数据。")
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
        )

    @classmethod
    def from_dict(
        cls,
        data: Mapping[str, Any],
        category: DataCategory | None = None,
        *,
        units: Mapping[str, str | None] | None = None,
    ) -> Self:
        """从字典恢复标量限值对象。"""

        del category
        assert cls.value_field is not None
        current = resolve_file_units(
            {cls.value_field},
            parsed_units=data.get("_units", {}),
            units=units,
            allow_partial=True,
        )
        standard, scene, clause, resource_key = cls._metadata_from_mapping(data)
        return cls._from_base_data(
            value=float(np.asarray(data.get(cls.value_field, [0.0])).flat[0]),
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
        """导出曲线限值为 DataFrame。"""

        assert self.axis_field is not None
        assert self.value_field is not None
        return pd.DataFrame(
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

    @classmethod
    def from_pandas(
        cls,
        df: pd.DataFrame,
        *,
        units: Mapping[str, str | None] | None = None,
        unit_system: UnitSystem | None = None,
    ) -> Self:
        """从 DataFrame 构建曲线限值对象。"""

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
        )

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
