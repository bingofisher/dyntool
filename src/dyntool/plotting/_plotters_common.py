"""plotter 内部共享的统计与样式支持。"""

from __future__ import annotations

from typing import Any, Mapping, TypeAlias
import warnings

import numpy as np

from .types import PlotStatMetric

StatMetricInput: TypeAlias = PlotStatMetric | str

_BOX_STYLE_GROUPS: dict[str, tuple[str, ...]] = {
    "box": ("facecolor", "edgecolor", "linewidth", "linestyle"),
    "whisker": ("color", "linewidth", "linestyle"),
    "cap": ("color", "linewidth", "linestyle"),
    "median": ("color", "linewidth", "linestyle"),
    "mean": ("color", "linewidth", "linestyle"),
    "flier": ("marker", "markerfacecolor", "markeredgecolor", "markersize"),
}
_BOX_STYLE_DEFAULTS: dict[str, dict[str, Any]] = {
    "box": {"facecolor": "#dddddd", "edgecolor": "black", "linewidth": 0.8, "linestyle": "-"},
    "whisker": {"color": "black", "linewidth": 0.8, "linestyle": "-"},
    "cap": {"color": "black", "linewidth": 0.8, "linestyle": "-"},
    "median": {"color": "black", "linewidth": 0.8, "linestyle": "-"},
    "mean": {"color": "blue", "linewidth": 1.5, "linestyle": "-"},
    "flier": {
        "marker": "o",
        "markerfacecolor": "red",
        "markeredgecolor": "red",
        "markersize": 4,
        "linestyle": "none",
    },
}
_STAT_STYLE_DEFAULTS: dict[PlotStatMetric, dict[str, Any]] = {
    PlotStatMetric.MEAN: {"color": "blue", "linewidth": 1.5, "linestyle": "-"},
    PlotStatMetric.MEDIAN: {"color": "black", "linewidth": 1.2, "linestyle": "-"},
    PlotStatMetric.MIN: {"color": "gray", "linewidth": 1.0, "linestyle": "--"},
    PlotStatMetric.MAX: {"color": "gray", "linewidth": 1.0, "linestyle": "--"},
    PlotStatMetric.Q1: {"color": "dimgray", "linewidth": 1.0, "linestyle": "-."},
    PlotStatMetric.Q3: {"color": "dimgray", "linewidth": 1.0, "linestyle": "-."},
}


def normalize_stat_metric(metric: StatMetricInput) -> PlotStatMetric:
    """规范化统计量输入。"""

    if isinstance(metric, PlotStatMetric):
        return metric
    return PlotStatMetric(str(metric).strip().lower())


def stat_label(metric: PlotStatMetric, overrides: Mapping[str, str] | None = None) -> str:
    """返回统计曲线标签。"""

    if overrides is None:
        return metric.label
    return str(overrides.get(metric.value, metric.label))


def compute_statistic(values: np.ndarray, metric: PlotStatMetric) -> np.ndarray:
    """按列计算统计量。"""

    all_nan_rows = ~np.isfinite(values).any(axis=1)
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="Mean of empty slice", category=RuntimeWarning)
        warnings.filterwarnings("ignore", message="All-NaN slice encountered", category=RuntimeWarning)
        if metric == PlotStatMetric.MEAN:
            result = np.nanmean(values, axis=1)
        elif metric == PlotStatMetric.MEDIAN:
            result = np.nanmedian(values, axis=1)
        elif metric == PlotStatMetric.MIN:
            result = np.nanmin(values, axis=1)
        elif metric == PlotStatMetric.MAX:
            result = np.nanmax(values, axis=1)
        elif metric == PlotStatMetric.Q1:
            result = np.nanquantile(values, 0.25, axis=1)
        elif metric == PlotStatMetric.Q3:
            result = np.nanquantile(values, 0.75, axis=1)
        else:
            raise ValueError(f"不支持的统计指标: {metric}")
    result = np.asarray(result, dtype=float)
    result[all_nan_rows] = np.nan
    return result


def normalize_boxplot_style(style: Mapping[str, Any] | None = None) -> dict[str, dict[str, Any]]:
    """将扁平样式映射解析为 ``Axes.boxplot`` 的 ``*props``。"""

    normalized = {group: dict(defaults) for group, defaults in _BOX_STYLE_DEFAULTS.items()}
    if style is None:
        return normalized
    for raw_key, raw_value in style.items():
        if "." not in raw_key:
            continue
        group, prop = raw_key.split(".", 1)
        allowed = _BOX_STYLE_GROUPS.get(group)
        if allowed is None or prop not in allowed:
            continue
        normalized[group][prop] = raw_value
    return normalized


__all__ = [
    "StatMetricInput",
    "_STAT_STYLE_DEFAULTS",
    "compute_statistic",
    "normalize_boxplot_style",
    "normalize_stat_metric",
    "stat_label",
]
