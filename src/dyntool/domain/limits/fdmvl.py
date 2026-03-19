"""分频振级限值模型占位。"""

from __future__ import annotations

from typing import Mapping, Self

import numpy as np

from ..constants import DataCategory, UnitSystem, get_default_unit_system
from .base import CurveLimitBase
from .enums import FDMVLLimitStandard


class FDMVLLimit(CurveLimitBase):
    """分频振级限值对象占位。"""

    category = DataCategory.FDMVL_LIMIT
    axis_field = "freq"
    value_field = "fdmvl"
    standard_enum = FDMVLLimitStandard
    _registry_name = "fdmvl"

    @classmethod
    def _default_current_units(cls, unit_system: UnitSystem | None = None) -> dict[str, str]:
        units = unit_system or get_default_unit_system()
        return {"freq": units.frequency, "fdmvl": units.level}

    @classmethod
    def from_data(
        cls,
        *,
        freq: np.ndarray,
        fdmvl: np.ndarray,
        standard: FDMVLLimitStandard,
        scene: str,
        clause: str,
        resource_key: str,
        units: Mapping[str, str | None] | None = None,
        unit_system: UnitSystem | None = None,
    ) -> Self:
        """根据显式数据构建分频振级限值对象。"""

        cls._validate_standard(standard)
        current = cls._resolve_current_units(units=units, unit_system=unit_system)
        return cls._from_base_data(
            axis=np.asarray(freq, dtype=np.float64),
            values=np.asarray(fdmvl, dtype=np.float64),
            standard=standard,
            scene=scene,
            clause=clause,
            resource_key=resource_key,
            units=current,
            unit_system=unit_system,
        )

    @classmethod
    def from_standard(
        cls,
        standard: FDMVLLimitStandard,
        *,
        scene: str,
        units: Mapping[str, str | None] | None = None,
        unit_system: UnitSystem | None = None,
    ) -> Self:
        """从内置规范表构建分频振级限值对象。"""

        del standard, scene, units, unit_system
        raise ValueError("FDMVLLimit 当前暂无预置规范限值。")


__all__ = ["FDMVLLimit"]
