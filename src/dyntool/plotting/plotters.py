"""Plotter-first 绘图器实现。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd

from ..config import read_config_file
from .payloads import (
    FramePanelPayload,
    FramePlotPayload,
    OctavePlotPayload,
    PlotLinePayload,
    StorySeriesPayload,
    StoryValuePayload,
)
from .types import PlotBackend, PlotResult

_ASSETS_DIR = Path(__file__).resolve().parent / "assets"


def _ensure_matplotlib():
    import matplotlib.pyplot as plt

    return plt


@dataclass(slots=True)
class AxisFrame:
    """坐标轴框样式配置。"""

    params: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_file(cls, path: str | Path) -> "AxisFrame":
        """从配置文件读取轴样式。"""

        payload = read_config_file(Path(path))
        if not isinstance(payload, dict):
            raise TypeError("轴样式配置必须解析为字典。")
        return cls(params=payload)

    @classmethod
    def default(cls) -> "AxisFrame":
        """返回默认轴样式。"""

        return cls(
            params={
                "spine": {"linewidth": 0.8, "color": "black", "visible": True},
                "major_ticks": {"direction": "out", "length": 3.0, "width": 0.8, "labelsize": 8},
                "minor_ticks": {"direction": "out", "length": 2.0, "width": 0.6},
            }
        )

    def apply(self, ax: object) -> None:
        """应用样式到 matplotlib 坐标轴。"""

        params = self.params or {}
        spine_params = dict(params.get("spine", {}))
        for spine in ax.spines.values():
            if "linewidth" in spine_params:
                spine.set_linewidth(float(spine_params["linewidth"]))
            if "color" in spine_params:
                spine.set_color(str(spine_params["color"]))
            if "visible" in spine_params:
                spine.set_visible(bool(spine_params["visible"]))

        major_params = dict(params.get("major_ticks", {}))
        if major_params:
            ax.tick_params(which="major", **major_params)
        minor_params = dict(params.get("minor_ticks", {}))
        if minor_params:
            ax.tick_params(which="minor", **minor_params)


@dataclass(slots=True)
class OctaveBandSpec:
    """倍频程频带定义。"""

    band_octaves: float
    lower_frequency: float | None = None
    upper_frequency: float | None = None
    tolerance: float = 0.05
    reference_frequency: float = 1000.0

    DEFAULT_TABLE_PATH = _ASSETS_DIR / "one_third_octave_bands.csv"
    BAND_NUMBER_COLUMN = "频带数"
    CENTER_FREQUENCY_COLUMN = "中心频率 (Hz)"
    OCTAVE_RATIO = 10 ** (3 / 10)

    @classmethod
    def load_truth_table(cls, table_path: str | Path | None = None) -> pd.DataFrame:
        """读取默认真值表。"""

        path = Path(table_path) if table_path is not None else cls.DEFAULT_TABLE_PATH
        table = pd.read_csv(path)
        return table[[cls.BAND_NUMBER_COLUMN, cls.CENTER_FREQUENCY_COLUMN]].copy()

    @classmethod
    def from_default_table(
        cls,
        *,
        band_octaves: float = 1 / 3,
        lower_frequency: float | None = None,
        upper_frequency: float | None = None,
        tolerance: float = 0.05,
    ) -> "OctaveBandSpec":
        """基于 plotting 内置真值表构造频带规范。"""

        cls.load_truth_table()
        return cls(
            band_octaves=band_octaves,
            lower_frequency=lower_frequency,
            upper_frequency=upper_frequency,
            tolerance=tolerance,
        )

    @classmethod
    def _derive_reference_band_number(cls, band_octaves: float, reference_frequency: float) -> int:
        step_log10 = np.log10(cls.OCTAVE_RATIO) * band_octaves
        return int(round(np.log10(reference_frequency) / step_log10))

    def center_frequency(self, band_number: int) -> float:
        """根据频带数计算中心频率。"""

        reference_band_number = self._derive_reference_band_number(self.band_octaves, self.reference_frequency)
        exponent = (int(band_number) - reference_band_number) * self.band_octaves
        return float(self.reference_frequency * (self.OCTAVE_RATIO**exponent))

    def band_numbers_from_range(
        self,
        lower_frequency: float | None = None,
        upper_frequency: float | None = None,
    ) -> list[int]:
        """根据频率范围返回频带数。"""

        lower = lower_frequency if lower_frequency is not None else self.lower_frequency
        upper = upper_frequency if upper_frequency is not None else self.upper_frequency
        if lower is None or upper is None:
            raise ValueError("必须提供上下限频率。")
        if lower <= 0 or upper <= 0 or lower > upper:
            raise ValueError("频率范围无效。")
        step_log10 = np.log10(self.OCTAVE_RATIO) * self.band_octaves
        reference_band_number = self._derive_reference_band_number(self.band_octaves, self.reference_frequency)
        band_min = int(np.ceil(np.log10(lower / self.reference_frequency) / step_log10 + reference_band_number))
        band_max = int(np.floor(np.log10(upper / self.reference_frequency) / step_log10 + reference_band_number))
        if band_min > band_max:
            return []
        return list(range(band_min, band_max + 1))

    def validate_segment(self, freqs: np.ndarray | list[float]) -> None:
        """验证一段频率数组是否可映射到连续频带。"""

        values = np.asarray(freqs, dtype=float).flatten()
        if values.size == 0:
            raise ValueError("频率数组不能为空。")
        if np.any(values <= 0):
            raise ValueError("频率必须为正数。")
        if np.any(np.diff(values) < 0):
            raise ValueError("频率数组必须升序。")
        candidate_numbers = self.band_numbers_from_range(
            float(values[0]) / (1.0 + self.tolerance),
            float(values[-1]) / max(1e-12, 1.0 - self.tolerance),
        )
        if len(candidate_numbers) < len(values):
            raise ValueError("频率数组无法映射到连续倍频程频带。")
        for start in range(len(candidate_numbers) - len(values) + 1):
            segment = candidate_numbers[start : start + len(values)]
            centers = np.asarray([self.center_frequency(number) for number in segment], dtype=float)
            rel_error = np.abs(values - centers) / values
            if np.all(rel_error <= self.tolerance):
                return
        raise ValueError("频率数组无法映射到连续倍频程频带。")


class FramePlotter:
    """通用二维曲线绘图器。"""

    def __init__(self, ax: object | None = None, *, axis_frame: AxisFrame | None = None) -> None:
        self.ax = ax
        self.axis_frame = axis_frame or AxisFrame.default()

    def render(
        self,
        payload: FramePlotPayload,
        *,
        backend: PlotBackend = PlotBackend.MATPLOTLIB,
    ) -> PlotResult:
        """渲染二维曲线 payload。"""

        if backend is not PlotBackend.MATPLOTLIB:
            raise ValueError(f"不支持的绘图后端: {backend}")
        plt = _ensure_matplotlib()
        panels = payload.panels
        if not panels:
            raise ValueError("frame payload 至少需要一个 panel。")
        if self.ax is not None:
            if len(panels) != 1:
                raise ValueError("外部坐标轴只支持单 panel 渲染。")
            fig = self.ax.figure
            axes = (self.ax,)
            self._draw_panel(self.ax, panels[0])
            fig.tight_layout()
            return PlotResult(raw=fig, backend=backend, figure=fig, axes=axes)

        if len(panels) == 1:
            fig, axis = plt.subplots()
            self._draw_panel(axis, panels[0])
            fig.tight_layout()
            return PlotResult(raw=fig, backend=backend, figure=fig, axes=(axis,))

        fig, axes_obj = plt.subplots(len(panels), 1, sharex=False)
        axes = tuple(np.atleast_1d(axes_obj).tolist())
        for axis, panel in zip(axes, panels, strict=True):
            self._draw_panel(axis, panel)
        fig.tight_layout()
        return PlotResult(raw=fig, backend=backend, figure=fig, axes=axes)

    def _draw_panel(self, ax: object, panel: FramePanelPayload) -> None:
        self.axis_frame.apply(ax)
        for line in panel.series:
            kwargs = dict(panel.style)
            kwargs.update(line.style)
            if line.label is not None:
                kwargs.setdefault("label", line.label)
            ax.plot(_coerce_x(line), _coerce_array(line.y), **kwargs)
        if panel.title:
            ax.set_title(panel.title)
        ax.set_xlabel(_with_unit(panel.x_label or "x", panel.x_unit))
        ax.set_ylabel(_with_unit(panel.y_label or "y", panel.y_unit))
        ax.set_xscale(panel.x_scale)
        ax.set_yscale(panel.y_scale)
        if panel.legend and any(line.label for line in panel.series):
            ax.legend()


class OneThirdOctavePlotter:
    """三分之一倍频程绘图器。"""

    def __init__(
        self,
        ax: object | None = None,
        *,
        axis_frame: AxisFrame | None = None,
        band_spec: OctaveBandSpec | None = None,
    ) -> None:
        self.ax = ax
        self.axis_frame = axis_frame or AxisFrame.default()
        self.band_spec = band_spec or OctaveBandSpec.from_default_table(lower_frequency=1.0, upper_frequency=80.0)

    def render(
        self,
        payload: OctavePlotPayload,
        *,
        backend: PlotBackend = PlotBackend.MATPLOTLIB,
    ) -> PlotResult:
        """渲染倍频程 payload。"""

        if backend is not PlotBackend.MATPLOTLIB:
            raise ValueError(f"不支持的绘图后端: {backend}")
        plt = _ensure_matplotlib()
        if self.ax is None:
            fig, ax = plt.subplots()
        else:
            ax = self.ax
            fig = ax.figure
        self.axis_frame.apply(ax)
        for line in (*payload.samples, *payload.envelopes, *payload.limits):
            if line.x is not None:
                self.band_spec.validate_segment(_coerce_array(line.x))
        for line in payload.samples:
            self._plot_line(ax, line, default_style={"linewidth": 0.8, "marker": "o", "markersize": 2})
        for line in payload.envelopes:
            self._plot_line(ax, line, default_style={"linewidth": 1.0})
        for line in payload.limits:
            self._plot_line(ax, line, default_style={"linewidth": 1.0, "linestyle": "--"})
        ax.set_xscale("log")
        ax.set_xlabel(_with_unit(payload.x_label or "freq", payload.x_unit))
        ax.set_ylabel(_with_unit(payload.y_label or "level", payload.y_unit))
        if payload.title:
            ax.set_title(payload.title)
        xticks = self._resolve_xticks(payload)
        if xticks.size:
            ax.set_xticks(xticks)
            ax.set_xticklabels([_format_axis_number(value) for value in xticks])
        if payload.legend and ax.get_legend_handles_labels()[1]:
            ax.legend()
        fig.tight_layout()
        return PlotResult(raw=fig, backend=backend, figure=fig, axes=(ax,))

    def _plot_line(self, ax: object, line: PlotLinePayload, *, default_style: Mapping[str, object]) -> None:
        kwargs = dict(default_style)
        kwargs.update(line.style)
        if line.label is not None:
            kwargs.setdefault("label", line.label)
        ax.plot(_coerce_array(line.x), _coerce_array(line.y), **kwargs)

    def _resolve_xticks(self, payload: OctavePlotPayload) -> np.ndarray:
        all_freqs: list[np.ndarray] = []
        for line in (*payload.samples, *payload.envelopes, *payload.limits):
            if line.x is not None:
                all_freqs.append(_coerce_array(line.x))
        if not all_freqs:
            return np.array([], dtype=float)
        merged = np.unique(np.concatenate(all_freqs))
        return merged


class StoryValuePlotter:
    """楼层/剖面值绘图器。"""

    def __init__(self, ax: object | None = None, *, axis_frame: AxisFrame | None = None) -> None:
        self.ax = ax
        self.axis_frame = axis_frame or AxisFrame.default()

    def render(
        self,
        payload: StoryValuePayload,
        *,
        backend: PlotBackend = PlotBackend.MATPLOTLIB,
    ) -> PlotResult:
        """渲染楼层/剖面值 payload。"""

        if backend is not PlotBackend.MATPLOTLIB:
            raise ValueError(f"不支持的绘图后端: {backend}")
        plt = _ensure_matplotlib()
        if self.ax is None:
            fig, ax = plt.subplots()
        else:
            ax = self.ax
            fig = ax.figure
        self.axis_frame.apply(ax)
        for series in payload.samples:
            self._plot_story_series(ax, series, default_style={"linewidth": 0.8, "marker": "o", "markersize": 3})
        for series in payload.stats:
            self._plot_story_series(ax, series, default_style={"linewidth": 1.2, "marker": "s", "markersize": 4})
        for limit in payload.limits:
            kwargs = {"linewidth": 1.0, "linestyle": "--"}
            kwargs.update(limit.style)
            ax.axvline(limit.value, label=limit.label, **kwargs)
        if payload.title:
            ax.set_title(payload.title)
        ax.set_xlabel(_with_unit(payload.x_label or "value", payload.x_unit))
        ax.set_ylabel(_with_unit(payload.y_label or "level", payload.y_unit))
        levels = self._collect_levels(payload)
        if levels.size:
            ax.set_yticks(levels)
            if payload.tick_labels:
                ax.set_yticklabels([payload.tick_labels.get(float(level), str(level)) for level in levels])
        if payload.legend and ax.get_legend_handles_labels()[1]:
            ax.legend()
        fig.tight_layout()
        return PlotResult(raw=fig, backend=backend, figure=fig, axes=(ax,))

    def _plot_story_series(
        self,
        ax: object,
        series: StorySeriesPayload,
        *,
        default_style: Mapping[str, object],
    ) -> None:
        kwargs = dict(default_style)
        kwargs.update(series.style)
        if series.label is not None:
            kwargs.setdefault("label", series.label)
        ax.plot(_coerce_array(series.values), _coerce_array(series.levels), **kwargs)

    def _collect_levels(self, payload: StoryValuePayload) -> np.ndarray:
        levels: list[np.ndarray] = []
        for series in (*payload.samples, *payload.stats):
            levels.append(_coerce_array(series.levels))
        if not levels:
            return np.array([], dtype=float)
        return np.unique(np.concatenate(levels))


def _coerce_array(values: object) -> np.ndarray:
    return np.asarray(values, dtype=float).flatten()


def _coerce_x(line: PlotLinePayload) -> np.ndarray:
    if line.x is None:
        return np.arange(_coerce_array(line.y).shape[0], dtype=float)
    return _coerce_array(line.x)


def _with_unit(label: str, unit: str | None) -> str:
    if unit:
        return f"{label} [{unit}]"
    return label


def _format_axis_number(num: float) -> str:
    as_int = int(num)
    if abs(num - as_int) < 1e-9:
        return str(as_int)
    return str(num).rstrip("0").rstrip(".")


__all__ = [
    "AxisFrame",
    "FramePlotter",
    "OctaveBandSpec",
    "OneThirdOctavePlotter",
    "StoryValuePlotter",
]
