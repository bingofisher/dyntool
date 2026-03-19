"""1/3 倍频程振动加速度级限值模型。"""

from __future__ import annotations

from typing import Mapping, Self

import numpy as np

from ..constants import DataCategory, UnitSystem, convert_array, get_default_unit_system
from .base import CurveLimitBase
from .enums import OTOVLLimitStandard
from .registry import resolve_limit_payload


class OTOVLLimit(CurveLimitBase):
    """规范驱动 1/3 倍频程振动加速度级限值对象。"""

    category = DataCategory.OTOVL_LIMIT
    axis_field = "freq"
    value_field = "otovl"
    standard_enum = OTOVLLimitStandard
    _registry_name = "otovl"

    @classmethod
    def _default_current_units(cls, unit_system: UnitSystem | None = None) -> dict[str, str]:
        units = unit_system or get_default_unit_system()
        return {"freq": units.frequency, "otovl": units.level}

    @classmethod
    def from_data(
        cls,
        *,
        freq: np.ndarray,
        otovl: np.ndarray,
        standard: OTOVLLimitStandard,
        scene: str,
        clause: str,
        resource_key: str,
        units: Mapping[str, str | None] | None = None,
        unit_system: UnitSystem | None = None,
    ) -> Self:
        """根据显式数据构建 1/3 倍频程限值对象。"""

        cls._validate_standard(standard)
        current = cls._resolve_current_units(units=units, unit_system=unit_system)
        return cls._from_base_data(
            axis=np.asarray(freq, dtype=np.float64),
            values=np.asarray(otovl, dtype=np.float64),
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
        standard: OTOVLLimitStandard,
        *,
        scene: str,
        units: Mapping[str, str | None] | None = None,
        unit_system: UnitSystem | None = None,
    ) -> Self:
        """从内置规范表构建单个 1/3 倍频程限值对象。"""

        cls._validate_standard(standard)
        payload = resolve_limit_payload(cls._registry_name, standard, scene)
        current = cls._resolve_current_units(units=units, unit_system=unit_system)
        return cls._from_base_data(
            axis=convert_array(
                payload.fields["freq"],
                from_unit=payload.units["freq"],
                to_unit=current["freq"],
            ),
            values=convert_array(
                payload.fields["otovl"],
                from_unit=payload.units["otovl"],
                to_unit=current["otovl"],
            ),
            standard=standard,
            scene=payload.scene,
            clause=payload.clause,
            resource_key=payload.resource_key,
            units=current,
            unit_system=unit_system,
        )

    @property
    def freq(self) -> np.ndarray:
        """返回频率轴。"""

        return self.get_field("freq")

    @property
    def otovl(self) -> np.ndarray:
        """返回 1/3 倍频程限值曲线。"""

        return self.get_field("otovl")


__all__ = ["OTOVLLimit"]
