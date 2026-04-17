"""story/value plotter。"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

import numpy as np
from matplotlib.axes import Axes

from ._plotters_base import PlotterBase
from ._plotters_common import StatMetricInput, _STAT_STYLE_DEFAULTS, compute_statistic, stat_label
from .config import PlotTheme
from .dataset import PlotCategory, PlotDataset
from .types import PlotResult, PlotterKind


class StoryValuePlotter(PlotterBase):
    """楼层或剖面值绘图器。"""

    plotter_kind = PlotterKind.STORY_VALUE
    default_x_label = "value"
    default_y_label = "story"
    category_order = (
        PlotCategory.SAMPLE.value,
        PlotCategory.STAT.value,
        PlotCategory.LIMIT.value,
    )
    default_legend_options = {"loc": "best"}

    def __init__(self, ax: Axes | None = None, *, theme: PlotTheme | None = None) -> None:
        """构造正式 story-value plotter。"""

        super().__init__(ax=ax, theme=theme)

    def _plot_dataset(
        self,
        dataset: PlotDataset,
        *,
        categories: Sequence[PlotCategory | str] | None = None,
        names: Sequence[str] | None = None,
        ax: Axes | None = None,
        legend_options: Mapping[str, Any] | None = None,
        stats: Sequence[StatMetricInput] | None = None,
        stat_label_overrides: Mapping[str, str] | None = None,
    ) -> PlotResult:
        keys = [item.as_tuple() for item in self._sorted_keys(dataset, categories=categories, names=names)]
        if not keys:
            raise ValueError("当前 PlotDataset 中没有匹配的曲线可供绘制。")
        fig, target_ax = self._resolve_target_axes(ax)
        self._apply_axis_frame(target_ax)
        axis = dataset._axis_values()
        for key in keys:
            column = dataset._column_values(key)
            if key[0] == PlotCategory.LIMIT.value and np.unique(column).size == 1:
                style = self._resolve_style(
                    dataset,
                    key,
                    default_style={"linewidth": 1.0, "linestyle": "--"},
                    artist_method="axhline",
                )
                target_ax.axvline(float(column[0]), **style)
                continue
            default_style = (
                {"linewidth": 1.2, "marker": "s", "markersize": 4}
                if key[0] == PlotCategory.STAT.value
                else {"linewidth": 0.8, "marker": "o", "markersize": 3}
            )
            style = self._resolve_style(dataset, key, default_style=default_style)
            target_ax.plot(column, axis, **style)
        sample_keys = self._sample_keys(keys)
        stat_metrics = self._resolve_stat_metrics(stats)
        if stat_metrics and sample_keys:
            sample_matrix = self._sample_matrix(dataset, sample_keys)
            for metric in stat_metrics:
                target_ax.plot(
                    compute_statistic(sample_matrix, metric),
                    axis,
                    label=stat_label(metric, stat_label_overrides),
                    **_STAT_STYLE_DEFAULTS[metric],
                )
        axis_unit = self._resolve_axis_unit(dataset, keys)
        value_unit = self._resolve_value_unit(dataset, keys)
        self._set_axis_labels_if_missing(
            target_ax,
            xlabel=self.with_unit(self.default_x_label, value_unit),
            ylabel=self.with_unit(self.default_y_label, axis_unit),
        )
        if axis.size:
            target_ax.set_yticks(axis)
        self._apply_legend(target_ax, legend_options=legend_options)
        self._finalize_figure(fig)
        return PlotResult(raw=fig, figure=fig, axes=(target_ax,))


__all__ = ["StoryValuePlotter"]
