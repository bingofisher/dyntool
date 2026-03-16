"""独立绘图模块的公开类型。"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from ..domain.plot_types import PlotBackend, PlotKind


class PlotterKind(StrEnum):
    """绘图器类型。"""

    FRAME = "frame"
    ONE_THIRD_OCTAVE = "one_third_octave"
    STORY_VALUE = "story_value"


@dataclass(slots=True)
class PlotResult:
    """统一封装绘图结果对象。"""

    raw: object
    backend: PlotBackend
    figure: object | None = None
    axes: tuple[object, ...] = field(default_factory=tuple)
    artists: tuple[object, ...] = field(default_factory=tuple)

    @classmethod
    def from_raw(cls, raw: object, *, backend: PlotBackend) -> "PlotResult":
        """从底层绘图返回值构造标准结果。"""

        if isinstance(raw, cls):
            return raw
        figure = raw if hasattr(raw, "axes") else None
        axes_value = getattr(raw, "axes", None)
        if axes_value is None:
            axes: tuple[object, ...] = ()
        elif isinstance(axes_value, tuple):
            axes = axes_value
        elif isinstance(axes_value, list):
            axes = tuple(axes_value)
        else:
            axes = (axes_value,)
        return cls(raw=raw, backend=backend, figure=figure, axes=axes)

    def __getattr__(self, name: str) -> Any:
        """将未知属性委托给底层 figure 或 raw 对象。"""

        target = self.figure if self.figure is not None else self.raw
        return getattr(target, name)


__all__ = ["PlotBackend", "PlotKind", "PlotResult", "PlotterKind"]
