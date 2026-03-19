"""样本加载与内部字段相关类型。"""

from __future__ import annotations

from enum import StrEnum


class SampleField(StrEnum):
    """样本内部数据项主键。

    该枚举作为样本 schema、懒加载状态、脏标记和 storage 读写的内部
    canonical key。公开层仍以 ``DataCategory`` 作为选择器；样本属性
    名仅作为访问别名。
    """

    ACCEL = "accel"
    VEL = "vel"
    DISP = "disp"
    FORCE = "force"
    FREQSPEC = "freqspec"
    RESPSPEC = "respspec"
    ZVL = "zvl"
    OTOVL = "otovl"
    FDMVL = "fdmvl"
    FPVDV = "fpvdv"


class SampleLoadMode(StrEnum):
    """样本与样本集的数据加载模式。"""

    METADATA_ONLY = "metadata_only"
    LAZY = "lazy"
    EAGER = "eager"


__all__ = ["SampleField", "SampleLoadMode"]
