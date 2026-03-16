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


class PlotBackend(StrEnum):
    """公开绘图后端。"""

    MATPLOTLIB = "matplotlib"


__all__ = ["PlotBackend", "PlotKind"]
