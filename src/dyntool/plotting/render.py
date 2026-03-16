"""plotter-first 渲染入口。"""

from __future__ import annotations

from typing import Mapping

from .payloads import PlotPayload, normalize_payload
from .plotters import FramePlotter, OneThirdOctavePlotter, StoryValuePlotter
from .types import PlotBackend, PlotResult, PlotterKind


def render_payload(
    payload: PlotPayload | Mapping[str, object],
    *,
    backend: PlotBackend = PlotBackend.MATPLOTLIB,
) -> PlotResult:
    """根据 payload 自动选择 plotter 并渲染。"""

    normalized = normalize_payload(payload)
    if normalized.plotter_kind is PlotterKind.FRAME:
        return FramePlotter().render(normalized, backend=backend)
    if normalized.plotter_kind is PlotterKind.ONE_THIRD_OCTAVE:
        return OneThirdOctavePlotter().render(normalized, backend=backend)
    if normalized.plotter_kind is PlotterKind.STORY_VALUE:
        return StoryValuePlotter().render(normalized, backend=backend)
    raise ValueError(f"不支持的 plotter_kind: {normalized.plotter_kind}")


def render_plotter(
    plotter: FramePlotter | OneThirdOctavePlotter | StoryValuePlotter,
    payload: PlotPayload | Mapping[str, object],
    *,
    backend: PlotBackend = PlotBackend.MATPLOTLIB,
) -> PlotResult:
    """使用显式 plotter 实例渲染 payload。"""

    normalized = normalize_payload(payload)
    return plotter.render(normalized, backend=backend)


__all__ = ["render_payload", "render_plotter"]
