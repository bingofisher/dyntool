"""plotting 坐标轴辅助的共享类型与基础函数。"""

from __future__ import annotations

from typing import Literal

AxisSide = Literal["top", "bottom", "left", "right"]
AxisFormatMode = Literal["continuous", "discrete"]


def format_plain_number(value: float) -> str:
    """把数值格式化为紧凑的普通字符串。"""

    value_int = int(value)
    if abs(value - value_int) < 1e-9:
        return str(value_int)
    return f"{value:.12f}".rstrip("0").rstrip(".")
