"""箱型图 plotter。"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

import numpy as np
from matplotlib.axes import Axes

from ._plotters_base import PlotterBase
from ._plotters_common import StatMetricInput, normalize_boxplot_style, stat_label
from .config import PlotTheme
from .dataset import PlotCategory, PlotDataset
from .types import PlotResult, PlotStatMetric, PlotterKind


class BoxPlotter(PlotterBase):
    """基于 ``PlotDataset`` 的箱型图 plotter。"""

    plotter_kind = PlotterKind.BOX
    default_x_label = "group"
    default_y_label = "value"
    category_order = (PlotCategory.SAMPLE.value,)
    default_legend_options = {"loc": "best"}

    def __init__(self, ax: Axes | None = None, *, theme: PlotTheme | None = None) -> None:
        """构造正式箱线图 plotter。"""

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
        style_defaults: Mapping[str, Any] | None = None,
        stat_label_overrides: Mapping[str, str] | None = None,
    ) -> PlotResult:
        keys = [item.as_tuple() for item in self._sorted_keys(dataset, categories=categories, names=names)]
        sample_keys = self._sample_keys(keys)
        if not sample_keys:
            raise ValueError("箱型图至少需要一列 SAMPLE 数据。")

        sample_values = [self._finite_sample_values(dataset, key) for key in sample_keys]
        if not any(values.size > 0 for values in sample_values):
            raise ValueError("箱型图至少需要一组非空样本。")
        if any(values.size == 0 for values in sample_values):
            raise ValueError("箱型图的每个 SAMPLE 列都必须包含至少一个有效样本。")

        fig, target_ax = self._resolve_target_axes(ax)
        self._apply_axis_frame(target_ax)
        positions = np.arange(1, len(sample_keys) + 1, dtype=float)
        stat_metrics = self._resolve_stat_metrics(stats)
        base_style = normalize_boxplot_style(style_defaults)
        boxplot = target_ax.boxplot(
            sample_values,
            positions=positions,
            widths=0.55,
            patch_artist=True,
            showmeans=PlotStatMetric.MEAN in stat_metrics,
            meanline=True,
            boxprops=base_style["box"],
            whiskerprops=base_style["whisker"],
            capprops=base_style["cap"],
            medianprops=base_style["median"],
            meanprops=base_style["mean"],
            flierprops=base_style["flier"],
        )
        self._apply_per_sample_box_styles(
            dataset,
            sample_keys,
            boxplot,
            style_defaults=style_defaults,
        )
        target_ax.set_xticks(positions)
        target_ax.set_xticklabels([self._sample_label(dataset, key) for key in sample_keys])
        value_unit = self._resolve_value_unit(dataset, sample_keys)
        self._set_axis_labels_if_missing(
            target_ax,
            xlabel=self.default_x_label,
            ylabel=self.with_unit(self.default_y_label, value_unit),
        )
        self._register_box_stat_proxies(
            target_ax,
            stat_metrics=stat_metrics,
            style_defaults=style_defaults,
            stat_label_overrides=stat_label_overrides,
        )
        self._apply_legend(target_ax, legend_options=legend_options)
        self._finalize_figure(fig)
        artists = (
            tuple(boxplot.get("boxes", ()))
            + tuple(boxplot.get("whiskers", ()))
            + tuple(boxplot.get("caps", ()))
            + tuple(boxplot.get("medians", ()))
            + tuple(boxplot.get("means", ()))
            + tuple(boxplot.get("fliers", ()))
        )
        return PlotResult(raw=fig, figure=fig, axes=(target_ax,), artists=artists)

    @staticmethod
    def _finite_sample_values(dataset: PlotDataset, key: tuple[str, str]) -> np.ndarray:
        values = np.asarray(dataset._column_values(key), dtype=float)
        return values[np.isfinite(values)]

    @staticmethod
    def _sample_label(dataset: PlotDataset, key: tuple[str, str]) -> str:
        label = dataset._column_meta(key)["label"]
        return str(label) if label else key[1]

    def _apply_per_sample_box_styles(
        self,
        dataset: PlotDataset,
        sample_keys: Sequence[tuple[str, str]],
        boxplot: Mapping[str, Sequence[Any]],
        *,
        style_defaults: Mapping[str, Any] | None,
    ) -> None:
        boxes = tuple(boxplot.get("boxes", ()))
        whiskers = tuple(boxplot.get("whiskers", ()))
        caps = tuple(boxplot.get("caps", ()))
        medians = tuple(boxplot.get("medians", ()))
        means = tuple(boxplot.get("means", ()))
        fliers = tuple(boxplot.get("fliers", ()))
        for index, key in enumerate(sample_keys):
            raw_style = dataset._column_meta(key)["style"]
            merged = dict(style_defaults or {})
            if isinstance(raw_style, Mapping):
                merged.update(raw_style)
            resolved = normalize_boxplot_style(merged)
            if index < len(boxes):
                self._apply_line_or_patch_style(boxes[index], resolved["box"])
            for offset in range(2):
                whisker_idx = index * 2 + offset
                if whisker_idx < len(whiskers):
                    self._apply_line_or_patch_style(whiskers[whisker_idx], resolved["whisker"])
                if whisker_idx < len(caps):
                    self._apply_line_or_patch_style(caps[whisker_idx], resolved["cap"])
            if index < len(medians):
                self._apply_line_or_patch_style(medians[index], resolved["median"])
            if index < len(means):
                self._apply_line_or_patch_style(means[index], resolved["mean"])
            if index < len(fliers):
                self._apply_line_or_patch_style(fliers[index], resolved["flier"])

    @staticmethod
    def _apply_line_or_patch_style(artist: Any, style: Mapping[str, Any]) -> None:
        setter_map = {
            "facecolor": "set_facecolor",
            "edgecolor": "set_edgecolor",
            "linewidth": "set_linewidth",
            "linestyle": "set_linestyle",
            "color": "set_color",
            "marker": "set_marker",
            "markerfacecolor": "set_markerfacecolor",
            "markeredgecolor": "set_markeredgecolor",
            "markersize": "set_markersize",
        }
        for key, value in style.items():
            setter_name = setter_map.get(key)
            if setter_name is None or value is None or not hasattr(artist, setter_name):
                continue
            getattr(artist, setter_name)(value)

    def _register_box_stat_proxies(
        self,
        ax: Axes,
        *,
        stat_metrics: Sequence[PlotStatMetric],
        style_defaults: Mapping[str, Any] | None,
        stat_label_overrides: Mapping[str, str] | None,
    ) -> None:
        base_style = normalize_boxplot_style(style_defaults)
        for metric in stat_metrics:
            label = stat_label(metric, stat_label_overrides)
            if metric == PlotStatMetric.MEAN:
                props = base_style["mean"]
                self._register_proxy_artist(
                    ax,
                    label=label,
                    style={
                        "color": props.get("color"),
                        "linewidth": props.get("linewidth"),
                        "linestyle": props.get("linestyle"),
                    },
                )
                continue
            if metric == PlotStatMetric.MEDIAN:
                props = base_style["median"]
                self._register_proxy_artist(
                    ax,
                    label=label,
                    style={
                        "color": props.get("color"),
                        "linewidth": props.get("linewidth"),
                        "linestyle": props.get("linestyle"),
                    },
                )
                continue
            if metric in {PlotStatMetric.Q1, PlotStatMetric.Q3}:
                props = base_style["box"]
                self._register_proxy_artist(
                    ax,
                    label=label,
                    style={
                        "color": props.get("edgecolor"),
                        "linewidth": props.get("linewidth"),
                        "linestyle": props.get("linestyle"),
                    },
                )
                continue
            props = base_style["whisker"]
            self._register_proxy_artist(
                ax,
                label=label,
                style={
                    "color": props.get("color"),
                    "linewidth": props.get("linewidth"),
                    "linestyle": props.get("linestyle"),
                },
            )


__all__ = ["BoxPlotter"]
