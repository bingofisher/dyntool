"""plotting 轴样式、网格、图例与修轴辅助公开入口。"""

from __future__ import annotations

from ._axes_common import AxisFormatMode, AxisSide
from ._axes_formatters import AxisNumberFormatter, DiscreteAxisFormatter, TickPlanner
from ._axes_frame import AxisFrame, GridFrame
from ._axes_helpers import AxisHelper, LegendHelper

AxisFrame.__module__ = __name__
GridFrame.__module__ = __name__
AxisNumberFormatter.__module__ = __name__
TickPlanner.__module__ = __name__
DiscreteAxisFormatter.__module__ = __name__
LegendHelper.__module__ = __name__
AxisHelper.__module__ = __name__

__all__ = [
    "AxisFrame",
    "AxisFormatMode",
    "AxisHelper",
    "AxisNumberFormatter",
    "AxisSide",
    "DiscreteAxisFormatter",
    "GridFrame",
    "LegendHelper",
    "TickPlanner",
]
