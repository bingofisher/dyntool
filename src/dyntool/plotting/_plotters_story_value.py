"""story/value plotter。"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

import numpy as np
from matplotlib.axes import Axes

from ._axis_config_adapter import apply_story_value_axis_config, resolve_axis_config
from ._plotters_base import PlotterBase
from ._plotters_common import StatMetricInput, _STAT_STYLE_DEFAULTS, compute_statistic, stat_label
from .axis_config import AxisConfig
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

    def __init__(
        self,
        ax: Axes | None = None,
        *,
        theme: PlotTheme | None = None,
        axis_config: AxisConfig | None = None,
    ) -> None:
        """构造正式 story-value plotter。"""

        super().__init__(ax=ax, theme=theme)
        self._axis_config = axis_config

    def plot_dataset(
        self,
        dataset: PlotDataset,
        *,
        categories: Sequence[PlotCategory | str] | None = None,
        names: Sequence[str] | None = None,
        ax: Axes | None = None,
        legend_options: Mapping[str, Any] | None = None,
        axis_config: AxisConfig | None = None,
        stats: Sequence[StatMetricInput] | None = None,
        stat_label_overrides: Mapping[str, str] | None = None,
    ) -> PlotResult:
        """绑定数据集并执行正式绘图主链。"""

        self.set_dataset(dataset)
        return self._plot_dataset(
            dataset,
            categories=categories,
            names=names,
            ax=ax,
            legend_options=legend_options,
            axis_config=axis_config,
            stats=stats,
            stat_label_overrides=stat_label_overrides,
        )

    def _plot_dataset(
        self,
        dataset: PlotDataset,
        *,
        categories: Sequence[PlotCategory | str] | None = None,
        names: Sequence[str] | None = None,
        ax: Axes | None = None,
        legend_options: Mapping[str, Any] | None = None,
        axis_config: AxisConfig | None = None,
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
        resolved_axis_config = resolve_axis_config(
            theme_axis_config=self._theme.axis_config if self._theme is not None else None,
            plotter_axis_config=self._axis_config,
            runtime_axis_config=axis_config,
        )
        if axis.size and (resolved_axis_config is None or resolved_axis_config.y is None):
            target_ax.set_yticks(axis)
        apply_story_value_axis_config(
            target_ax,
            dataset=dataset,
            keys=keys,
            axis_config=resolved_axis_config,
        )
        self._apply_tick_label_options(target_ax)
        self._apply_legend(target_ax, legend_options=legend_options)
        self._finalize_figure(fig)
        return PlotResult(raw=fig, figure=fig, axes=(target_ax,))


__all__ = ["StoryValuePlotter"]
