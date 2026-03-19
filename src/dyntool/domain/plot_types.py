"""领域共享绘图枚举。"""

from __future__ import annotations

from enum import StrEnum


class PlotKind(StrEnum):
    """公开绘图类型。"""

    TIME = "time"
    SPECTRUM = "spectrum"
    FREQSPEC = "freqspec"
    RESPONSE = "response"
    RESPSPEC = "respspec"
    OTOVL = "otovl"


__all__ = ["PlotKind"]
