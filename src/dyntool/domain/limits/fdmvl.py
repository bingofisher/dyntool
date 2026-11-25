"""规范驱动分频最大振级标量限值模型。"""

from __future__ import annotations

from typing import Any, Mapping, Self

import numpy as np

from ..constants import DataCategory, UnitSystem, convert_array, get_default_unit_system
from .base import ScalarLimitBase
from .enums import FDMVLLimitStandard
from .registry import resolve_limit_payload


class FDMVLLimit(ScalarLimitBase):
    """分频最大振级标量阈值，对应 JGJ/T 170—2009 表 4.0.1。

    限值与按表 5.1.3 进行 Z 计权后的分频最大振级比较，不与未计权的
    倍频程加速度级或最大 Z 振级混用。对象沿用标量限值、单位及规范元信息
    合同；绘图时通过 ``PlotDataset.add_limit(..., axis=...)`` 广播为水平线。
    """

    category = DataCategory.FDMVL_LIMIT
    value_field = "fdmvl"
    standard_enum = FDMVLLimitStandard
    _registry_name = "fdmvl"

    @classmethod
    def _default_current_units(cls, unit_system: UnitSystem | None = None) -> dict[str, str]:
        units = unit_system or get_default_unit_system()
        return {"fdmvl": units.level}

    @classmethod
    def from_data(
        cls,
        *,
        fdmvl: float,
        standard: FDMVLLimitStandard,
        scene: str,
        clause: str,
        resource_key: str,
        units: Mapping[str, str | None] | None = None,
        unit_system: UnitSystem | None = None,
    ) -> Self:
        """根据显式标量和规范元信息构建限值对象。

        Args:
            fdmvl: 当前单位下的单个分频最大振级阈值。
            standard: 正式标准枚举。
            scene: 明确选择的区域及昼夜场景。
            clause: 限值对应的规范条款。
            resource_key: 限值对应的资源键。
            units: 字段单位；默认 fdmvl 为 decibel。
            unit_system: 默认单位上下文。

        Returns:
            不含频率轴的标量限值对象。
        """

        cls._validate_standard(standard)
        current = cls._resolve_current_units(units=units, unit_system=unit_system)
        return cls._from_base_data(
            value=float(fdmvl),
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
        """沿既有注册链路读取所选区域及昼夜的单个规范阈值。

        Args:
            standard: ``FDMVLLimitStandard.JGJ_T_170_2009``。
            scene: ``supported_scenes(standard)`` 中的完整场景名。
            units: 输出字段单位；与规范表的 dB 数值同步转换。
            unit_system: 输出默认单位上下文。

        Returns:
            带表 4.0.1 出处信息的标量限值对象。

        Raises:
            TypeError: standard 不是正式 FDMVLLimitStandard 枚举。
            ValueError: 场景不存在或目标单位与振级不相容。
        """

        cls._validate_standard(standard)
        payload = resolve_limit_payload(cls._registry_name, standard, scene)
        current = cls._resolve_current_units(units=units, unit_system=unit_system)
        value = float(
            convert_array(
                payload.fields["fdmvl"],
                from_unit=payload.units["fdmvl"],
                to_unit=current["fdmvl"],
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
    def fdmvl(self) -> np.ndarray:
        """返回只读零维数组表示的分频最大振级限值。"""

        return self.get_field("fdmvl")

    @classmethod
    def from_dict(
        cls,
        data: Mapping[str, Any],
        category: DataCategory | None = None,
        *,
        units: Mapping[str, str | None] | None = None,
    ) -> Self:
        """恢复标量限值，拒绝将原曲线占位载荷静默截断为首值。"""

        if "freq" in data or np.asarray(data.get("fdmvl", [])).size != 1:
            raise ValueError("FDMVLLimit 需要单个 fdmvl 标量且不含 freq；请先明确原曲线的标量阈值再迁移。")
        return super().from_dict(data, category, units=units)


__all__ = ["FDMVLLimit"]
