"""规范驱动限值类使用的标准枚举。"""

from __future__ import annotations

from enum import StrEnum


class ZVLLimitStandard(StrEnum):
    """Z 振级限值标准，值只接受统一的规范编号。"""

    GB_10070_1988 = "GB 10070-1988"
    GB_T_50355_2018 = "GB/T 50355-2018"


class OTOVLLimitStandard(StrEnum):
    """1/3 倍频程振动加速度级限值支持的标准枚举。"""

    GB_T_50355_2018 = "GB/T 50355-2018"


class FPVDVLimitStandard(StrEnum):
    """四次方振动剂量值限值支持的标准枚举。"""

    GB_50868_2013 = "GB 50868-2013"


class FDMVLLimitStandard(StrEnum):
    """分频最大振级限值支持的标准枚举。"""

    JGJ_T_170_2009 = "JGJ/T 170-2009"


__all__ = [
    "ZVLLimitStandard",
    "OTOVLLimitStandard",
    "FPVDVLimitStandard",
    "FDMVLLimitStandard",
]
