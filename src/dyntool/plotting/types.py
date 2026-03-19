"""独立绘图模块的公开类型。"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from matplotlib.artist import Artist
from matplotlib.axes import Axes
from matplotlib.figure import Figure

from ..domain.plot_types import PlotKind


class PlotterKind(StrEnum):
    """绘图器类型。"""

    FRAME = "frame"
    ONE_THIRD_OCTAVE = "one_third_octave"
    STORY_VALUE = "story_value"


@dataclass(slots=True)
class PlotResult:
    """统一封装绘图结果对象。"""

    raw: Figure | Axes | tuple[Axes, ...]
    figure: Figure | None = None
    axes: tuple[Axes, ...] = field(default_factory=tuple)
    artists: tuple[Artist, ...] = field(default_factory=tuple)

    @classmethod
    def from_raw(cls, raw: Figure | Axes | tuple[Axes, ...] | list[Axes]) -> "PlotResult":
        """从底层绘图返回值构造标准结果。"""

        if isinstance(raw, cls):
            return raw
        if isinstance(raw, Figure):
            figure = raw
            axes = tuple(raw.axes)
        elif isinstance(raw, Axes):
            figure = raw.figure
            axes = (raw,)
        elif isinstance(raw, tuple):
            axes = raw
            figure = axes[0].figure if axes else None
        else:
            axes = tuple(raw)
            figure = axes[0].figure if axes else None
        return cls(raw=raw, figure=figure, axes=axes)

    def __getattr__(self, name: str) -> Any:
        """将未知属性委托给底层 figure 或 raw 对象。"""

        target = self.figure if self.figure is not None else self.raw
        return getattr(target, name)


__all__ = ["PlotKind", "PlotResult", "PlotterKind"]
