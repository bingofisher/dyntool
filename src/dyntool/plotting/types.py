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

    BOX = "box"
    FRAME = "frame"
    ONE_THIRD_OCTAVE = "one_third_octave"
    STORY_VALUE = "story_value"


class PlotStatMetric(StrEnum):
    """正式公开的统计指标枚举。"""

    MEAN = "mean"
    MEDIAN = "median"
    MIN = "min"
    MAX = "max"
    Q1 = "q1"
    Q3 = "q3"

    @property
    def label(self) -> str:
        """返回默认中文显示文案。"""

        return {
            self.MEAN: "均值",
            self.MEDIAN: "中位数",
            self.MIN: "最小值",
            self.MAX: "最大值",
            self.Q1: "下四分位数",
            self.Q3: "上四分位数",
        }[self]


@dataclass(slots=True)
class PlotResult:
    """统一封装绘图结果对象。"""

    raw: Figure | Axes | tuple[Axes, ...]
    figure: Figure | None = None
    axes: tuple[Axes, ...] = field(default_factory=tuple)
    artists: tuple[Artist, ...] = field(default_factory=tuple)

    @property
    def ax(self) -> Axes | None:
        """返回首个 ``Axes``，作为最终微调出口。"""

        return self.axes[0] if self.axes else None

    @classmethod
    def from_raw(cls, raw: Figure | Axes | tuple[Axes, ...] | list[Axes]) -> "PlotResult":
        """从底层返回值构造标准绘图结果。"""

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
        """将未定义属性委托给底层 figure 或 raw 对象。"""

        target = self.figure if self.figure is not None else self.raw
        return getattr(target, name)


__all__ = ["PlotKind", "PlotResult", "PlotStatMetric"]
