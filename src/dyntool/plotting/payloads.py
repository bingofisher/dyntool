"""绘图 payload 数据结构。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from .types import PlotterKind


@dataclass(slots=True)
class PlotLinePayload:
    """描述一条可绘制曲线。"""

    y: object
    x: object | None = None
    label: str | None = None
    category: str | None = None
    tags: tuple[str, ...] = field(default_factory=tuple)
    style: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True)
class FramePanelPayload:
    """描述一个二维坐标面板。"""

    series: tuple[PlotLinePayload, ...] = field(default_factory=tuple)
    title: str | None = None
    x_label: str | None = None
    y_label: str | None = None
    x_unit: str | None = None
    y_unit: str | None = None
    legend: bool = True
    x_scale: str = "linear"
    y_scale: str = "linear"
    style: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True)
class FramePlotPayload:
    """通用二维曲线绘图 payload。"""

    panels: tuple[FramePanelPayload, ...] = field(default_factory=tuple)
    plotter_kind: PlotterKind = field(default=PlotterKind.FRAME, init=False)


@dataclass(slots=True)
class OctavePlotPayload:
    """倍频程/包络/限值绘图 payload。"""

    title: str | None = None
    x_label: str | None = None
    y_label: str | None = None
    x_unit: str | None = None
    y_unit: str | None = None
    samples: tuple[PlotLinePayload, ...] = field(default_factory=tuple)
    envelopes: tuple[PlotLinePayload, ...] = field(default_factory=tuple)
    limits: tuple[PlotLinePayload, ...] = field(default_factory=tuple)
    legend: bool = True
    style: dict[str, object] = field(default_factory=dict)
    plotter_kind: PlotterKind = field(default=PlotterKind.ONE_THIRD_OCTAVE, init=False)


@dataclass(slots=True)
class StorySeriesPayload:
    """楼层/剖面值序列。"""

    levels: object
    values: object
    label: str | None = None
    category: str | None = None
    tags: tuple[str, ...] = field(default_factory=tuple)
    style: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True)
class StoryLimitPayload:
    """楼层图中的限值线。"""

    value: float
    label: str | None = None
    style: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True)
class StoryValuePayload:
    """楼层/剖面值绘图 payload。"""

    title: str | None = None
    x_label: str | None = None
    y_label: str | None = None
    x_unit: str | None = None
    y_unit: str | None = None
    tick_labels: Mapping[float, str] | None = None
    samples: tuple[StorySeriesPayload, ...] = field(default_factory=tuple)
    stats: tuple[StorySeriesPayload, ...] = field(default_factory=tuple)
    limits: tuple[StoryLimitPayload, ...] = field(default_factory=tuple)
    legend: bool = True
    style: dict[str, object] = field(default_factory=dict)
    plotter_kind: PlotterKind = field(default=PlotterKind.STORY_VALUE, init=False)


PlotPayload = FramePlotPayload | OctavePlotPayload | StoryValuePayload


def normalize_payload(payload: PlotPayload | Mapping[str, object]) -> PlotPayload:
    """将映射或 dataclass 规范化为标准 payload 对象。"""

    if isinstance(payload, (FramePlotPayload, OctavePlotPayload, StoryValuePayload)):
        return payload
    plotter_kind = PlotterKind(str(payload["plotter_kind"]))
    if plotter_kind is PlotterKind.FRAME:
        return _normalize_frame_payload(payload)
    if plotter_kind is PlotterKind.ONE_THIRD_OCTAVE:
        return _normalize_octave_payload(payload)
    if plotter_kind is PlotterKind.STORY_VALUE:
        return _normalize_story_payload(payload)
    raise ValueError(f"不支持的 plotter_kind: {plotter_kind}")


def _normalize_frame_payload(payload: Mapping[str, object]) -> FramePlotPayload:
    panels_raw = payload.get("panels", ())
    panels = tuple(_normalize_frame_panel(panel) for panel in _as_sequence(panels_raw))
    return FramePlotPayload(panels=panels)


def _normalize_frame_panel(panel: object) -> FramePanelPayload:
    if isinstance(panel, FramePanelPayload):
        return panel
    if not isinstance(panel, Mapping):
        raise TypeError("frame panel 必须是映射或 FramePanelPayload。")
    return FramePanelPayload(
        series=tuple(_normalize_line_payload(item) for item in _as_sequence(panel.get("series", ()))),
        title=_optional_str(panel.get("title")),
        x_label=_optional_str(panel.get("x_label")),
        y_label=_optional_str(panel.get("y_label")),
        x_unit=_optional_str(panel.get("x_unit")),
        y_unit=_optional_str(panel.get("y_unit")),
        legend=bool(panel.get("legend", True)),
        x_scale=str(panel.get("x_scale", "linear")),
        y_scale=str(panel.get("y_scale", "linear")),
        style=_mapping_to_dict(panel.get("style")),
    )


def _normalize_octave_payload(payload: Mapping[str, object]) -> OctavePlotPayload:
    return OctavePlotPayload(
        title=_optional_str(payload.get("title")),
        x_label=_optional_str(payload.get("x_label")),
        y_label=_optional_str(payload.get("y_label")),
        x_unit=_optional_str(payload.get("x_unit")),
        y_unit=_optional_str(payload.get("y_unit")),
        samples=tuple(_normalize_line_payload(item) for item in _as_sequence(payload.get("samples", ()))),
        envelopes=tuple(_normalize_line_payload(item) for item in _as_sequence(payload.get("envelopes", ()))),
        limits=tuple(_normalize_line_payload(item) for item in _as_sequence(payload.get("limits", ()))),
        legend=bool(payload.get("legend", True)),
        style=_mapping_to_dict(payload.get("style")),
    )


def _normalize_story_payload(payload: Mapping[str, object]) -> StoryValuePayload:
    tick_labels_raw = payload.get("tick_labels")
    tick_labels = None
    if isinstance(tick_labels_raw, Mapping):
        tick_labels = {float(key): str(value) for key, value in tick_labels_raw.items()}
    return StoryValuePayload(
        title=_optional_str(payload.get("title")),
        x_label=_optional_str(payload.get("x_label")),
        y_label=_optional_str(payload.get("y_label")),
        x_unit=_optional_str(payload.get("x_unit")),
        y_unit=_optional_str(payload.get("y_unit")),
        tick_labels=tick_labels,
        samples=tuple(_normalize_story_series(item) for item in _as_sequence(payload.get("samples", ()))),
        stats=tuple(_normalize_story_series(item) for item in _as_sequence(payload.get("stats", ()))),
        limits=tuple(_normalize_story_limit(item) for item in _as_sequence(payload.get("limits", ()))),
        legend=bool(payload.get("legend", True)),
        style=_mapping_to_dict(payload.get("style")),
    )


def _normalize_line_payload(payload: object) -> PlotLinePayload:
    if isinstance(payload, PlotLinePayload):
        return payload
    if not isinstance(payload, Mapping):
        raise TypeError("曲线 payload 必须是映射或 PlotLinePayload。")
    return PlotLinePayload(
        x=payload.get("x"),
        y=payload.get("y", ()),
        label=_optional_str(payload.get("label")),
        category=_optional_str(payload.get("category")),
        tags=tuple(str(item) for item in _as_sequence(payload.get("tags", ()))),
        style=_mapping_to_dict(payload.get("style")),
    )


def _normalize_story_series(payload: object) -> StorySeriesPayload:
    if isinstance(payload, StorySeriesPayload):
        return payload
    if not isinstance(payload, Mapping):
        raise TypeError("楼层序列 payload 必须是映射或 StorySeriesPayload。")
    return StorySeriesPayload(
        levels=payload.get("levels", ()),
        values=payload.get("values", ()),
        label=_optional_str(payload.get("label")),
        category=_optional_str(payload.get("category")),
        tags=tuple(str(item) for item in _as_sequence(payload.get("tags", ()))),
        style=_mapping_to_dict(payload.get("style")),
    )


def _normalize_story_limit(payload: object) -> StoryLimitPayload:
    if isinstance(payload, StoryLimitPayload):
        return payload
    if not isinstance(payload, Mapping):
        raise TypeError("楼层限值 payload 必须是映射或 StoryLimitPayload。")
    return StoryLimitPayload(
        value=float(payload.get("value", 0.0)),
        label=_optional_str(payload.get("label")),
        style=_mapping_to_dict(payload.get("style")),
    )


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def _as_sequence(value: object) -> tuple[object, ...]:
    if value is None:
        return ()
    if isinstance(value, tuple):
        return value
    if isinstance(value, list):
        return tuple(value)
    return (value,)


def _mapping_to_dict(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        return {}
    return {str(key): item for key, item in value.items()}


__all__ = [
    "FramePanelPayload",
    "FramePlotPayload",
    "OctavePlotPayload",
    "PlotLinePayload",
    "PlotPayload",
    "StoryLimitPayload",
    "StorySeriesPayload",
    "StoryValuePayload",
    "normalize_payload",
]
