"""四次方振动剂量值限值模型。"""

from __future__ import annotations

from typing import Mapping, Self

import numpy as np

from ..constants import DataCategory, UnitSystem, convert_array, get_default_unit_system
from .base import ScalarLimitBase
from .enums import FPVDVLimitStandard
from .registry import resolve_limit_payload


class FPVDVLimit(ScalarLimitBase):
    """规范驱动四次方振动剂量值限值对象。"""

    category = DataCategory.FPVDV_LIMIT
    value_field = "fpvdv"
    standard_enum = FPVDVLimitStandard
    _registry_name = "fpvdv"

    @classmethod
    def _default_current_units(cls, unit_system: UnitSystem | None = None) -> dict[str, str]:
        units = unit_system or get_default_unit_system()
        return {"fpvdv": units.vibration_dose_value}

    @classmethod
    def from_data(
        cls,
        *,
        fpvdv: float,
        standard: FPVDVLimitStandard,
        scene: str,
        clause: str,
        resource_key: str,
        units: Mapping[str, str | None] | None = None,
        unit_system: UnitSystem | None = None,
    ) -> Self:
        """根据显式数据构建 FPVDV 限值对象。"""

        cls._validate_standard(standard)
        current = cls._resolve_current_units(units=units, unit_system=unit_system)
        return cls._from_base_data(
            value=float(fpvdv),
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
        standard: FPVDVLimitStandard,
        *,
        scene: str,
        units: Mapping[str, str | None] | None = None,
        unit_system: UnitSystem | None = None,
    ) -> Self:
        """从内置规范表构建单个 FPVDV 限值对象。"""

        cls._validate_standard(standard)
        payload = resolve_limit_payload(cls._registry_name, standard, scene)
        current = cls._resolve_current_units(units=units, unit_system=unit_system)
        value = float(
            convert_array(
                np.asarray(payload.fields["fpvdv"]),
                from_unit=payload.units["fpvdv"],
                to_unit=current["fpvdv"],
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
    def fpvdv(self) -> np.ndarray:
        """返回四次方振动剂量值限值。"""

        return self.get_field("fpvdv")


__all__ = ["FPVDVLimit"]
