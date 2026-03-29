"""样本加载、字段与视图配置类型。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class SampleField(StrEnum):
    """样本内部数据槽位键。"""

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


class StorageAccessMode(StrEnum):
    """样本集视图的存储访问权限模式。"""

    READ_ONLY = "read_only"
    READ_WRITE = "read_write"


@dataclass(slots=True)
class SampleSetViewOptions:
    """样本集查询结果视图的加载与访问配置。"""

    storage_mode: object | None = None
    load_mode: SampleLoadMode | None = None
    access_mode: StorageAccessMode = StorageAccessMode.READ_ONLY


__all__ = [
    "SampleField",
    "SampleLoadMode",
    "SampleSetViewOptions",
    "StorageAccessMode",
]
