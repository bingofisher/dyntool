"""Z 振级限值模型。"""

from __future__ import annotations

from typing import Mapping, Self

import numpy as np

from ..constants import DataCategory, UnitSystem, convert_array, get_default_unit_system
from .base import ScalarLimitBase
from .enums import ZVLLimitStandard
from .registry import resolve_limit_payload


class ZVLLimit(ScalarLimitBase):
    """规范驱动 Z 振级限值对象。"""

    category = DataCategory.ZVL_LIMIT
    value_field = "zvl"
    standard_enum = ZVLLimitStandard
    _registry_name = "zvl"

    @classmethod
    def _default_current_units(cls, unit_system: UnitSystem | None = None) -> dict[str, str]:
        units = unit_system or get_default_unit_system()
        return {"zvl": units.level}

    @classmethod
    def from_data(
        cls,
        *,
        zvl: float,
        standard: ZVLLimitStandard,
        scene: str,
        clause: str,
        resource_key: str,
        units: Mapping[str, str | None] | None = None,
        unit_system: UnitSystem | None = None,
    ) -> Self:
        """根据显式数据构建 Z 振级限值对象。"""

        cls._validate_standard(standard)
        current = cls._resolve_current_units(units=units, unit_system=unit_system)
        return cls._from_base_data(
            value=float(zvl),
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
        standard: ZVLLimitStandard,
        *,
        scene: str,
        units: Mapping[str, str | None] | None = None,
        unit_system: UnitSystem | None = None,
    ) -> Self:
        """从内置规范表构建单个 Z 振级限值对象。"""

        cls._validate_standard(standard)
        payload = resolve_limit_payload(cls._registry_name, standard, scene)
        current = cls._resolve_current_units(units=units, unit_system=unit_system)
        value = float(
            convert_array(
                np.asarray(payload.fields["zvl"]),
                from_unit=payload.units["zvl"],
                to_unit=current["zvl"],
            ).flat[0]
        )
        return cls._from_base_data(
            value=value,
            standard=standard,
            scene=payload.scene,
            clause=payload.clause,
            resource_key=payload.resource_key,
            units=current,
            unit_system=unit_system,
        )

    @property
    def zvl(self) -> np.ndarray:
        """返回 Z 振级限值。"""

        return self.get_field("zvl")


__all__ = ["ZVLLimit"]
