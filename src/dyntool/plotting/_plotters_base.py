"""plotter 内部共享基类。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence
import warnings

import numpy as np
import pandas as pd
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from numpy.typing import ArrayLike

from ._axes_frame import AxisFrame, GridFrame
from ._axes_helpers import LegendHelper
from ._plotters_common import StatMetricInput, normalize_stat_metric
from .config import PlotTheme
from .dataset import PlotCategory, PlotDataset
from .types import PlotResult, PlotStatMetric, PlotterKind


class PlotterBase:
    """plotter-first 正式绘图入口基类。"""

    plotter_kind: PlotterKind | None = None
    default_category = PlotCategory.SAMPLE
    default_x_label = "x"
    default_y_label = "value"
    category_order: tuple[str, ...] = ()
    default_legend_options: Mapping[str, Any] | None = None

    def __init__(
        self,
        ax: Axes | None = None,
        *,
        theme: PlotTheme | None = None,
        _axis_frame: AxisFrame | None = None,
        _grid_frame: GridFrame | None = None,
    ) -> None:
        self._default_ax = ax
        self._theme = theme
        # axis/grid frame 仅供 plotting 内部组合使用，不进入正式公开面。
        self._axis_frame = _axis_frame or (theme._build_axis_frame() if theme is not None else AxisFrame.default())
        self._grid_frame = (
            _grid_frame if _grid_frame is not None else (theme._build_grid_frame() if theme is not None else None)
        )
        self._dataset: PlotDataset | None = None

    @property
    def ax(self) -> Axes | None:
        """返回默认绑定的 ``Axes``。"""

        return self._default_ax

    @ax.setter
    def ax(self, value: Axes | None) -> None:
        self._default_ax = value

    def _set_axis_frame(self, value: AxisFrame | None) -> None:
        """更新内部轴框配置并在必要时立即应用。"""

        self._axis_frame = value or AxisFrame.default()
        if self._default_ax is not None:
            self._axis_frame.apply(self._default_ax)

    def _set_grid_frame(self, value: GridFrame | None) -> None:
        """更新内部网格框配置并在必要时立即应用。"""

        self._grid_frame = value
        if self._default_ax is not None and self._grid_frame is not None:
            self._grid_frame.apply(self._default_ax)

    @staticmethod
    def ensure_matplotlib() -> Any:
        """按需导入并返回 ``matplotlib.pyplot``。"""

        import matplotlib.pyplot as plt

        return plt

    @staticmethod
    def read_csv_table(path: str | Path) -> pd.DataFrame:
        """以 UTF-8 读取 CSV 表。"""

        return pd.read_csv(path, encoding="utf-8")

    @staticmethod
    def coerce_array(values: ArrayLike) -> np.ndarray:
        """将输入转换为一维 ``float`` 数组。"""

        return np.asarray(values, dtype=float).flatten()

    @staticmethod
    def with_unit(label: str, unit: str | None) -> str:
        """按需在标签后附加单位。"""

        return f"{label} [{unit}]" if unit else label

    @staticmethod
    def merge_style(*style_sources: Mapping[str, Any], label: str | None = None) -> dict[str, Any]:
        """按顺序合并样式映射。"""

        merged: dict[str, Any] = {}
        for source in style_sources:
            merged.update(source)
        if label is not None:
            merged["label"] = label
        return merged

    def set_dataset(self, dataset: PlotDataset) -> None:
        """绑定当前绘图使用的 ``PlotDataset``。"""

        self._dataset = dataset

    def get_dataset(self) -> PlotDataset:
        """返回当前已绑定的 ``PlotDataset``。"""

        if self._dataset is None:
            raise ValueError("当前 plotter 尚未绑定 PlotDataset。")
        return self._dataset

    def plot_dataset(
        self,
        dataset: PlotDataset,
        *,
        categories: Sequence[PlotCategory | str] | None = None,
        names: Sequence[str] | None = None,
        ax: Axes | None = None,
        legend_options: Mapping[str, Any] | None = None,
        **plot_options: Any,
    ) -> PlotResult:
        """绑定数据集并执行正式绘图主链。"""

        self.set_dataset(dataset)
        return self._plot_dataset(
            dataset,
            categories=categories,
            names=names,
            ax=ax,
            legend_options=legend_options,
            **plot_options,
        )

    def _plot_dataset(
        self,
        dataset: PlotDataset,
        *,
        categories: Sequence[PlotCategory | str] | None = None,
        names: Sequence[str] | None = None,
        ax: Axes | None = None,
        legend_options: Mapping[str, Any] | None = None,
        **plot_options: Any,
    ) -> PlotResult:
        raise NotImplementedError

    def _sorted_keys(
        self,
        dataset: PlotDataset,
        *,
        categories: Sequence[PlotCategory | str] | None = None,
        names: Sequence[str] | None = None,
    ) -> list[tuple[str, str]]:
        keys = dataset._subset_columns(categories=categories, names=names)
        order_map = {value: idx for idx, value in enumerate(self.category_order)}
        return sorted(keys, key=lambda item: (order_map.get(item.category, len(order_map)), item.category, item.name))

    def _resolve_axis_unit(self, dataset: PlotDataset, keys: list[tuple[str, str]]) -> str | None:
        meta = dataset.meta_frame()
        units = {meta.loc[key, "axis_unit"] for key in keys if meta.loc[key, "axis_unit"]}
        return next(iter(units)) if len(units) == 1 else None

    def _resolve_value_unit(self, dataset: PlotDataset, keys: list[tuple[str, str]]) -> str | None:
        meta = dataset.meta_frame()
        units = {meta.loc[key, "value_unit"] for key in keys if meta.loc[key, "value_unit"]}
        return next(iter(units)) if len(units) == 1 else None

    def _resolve_style(
        self,
        dataset: PlotDataset,
        key: tuple[str, str],
        *,
        default_style: Mapping[str, Any],
        artist_method: str = "plot",
    ) -> dict[str, Any]:
        meta = dataset._column_meta(key)
        raw_style = meta["style"]
        style_map = raw_style if isinstance(raw_style, Mapping) else {}
        label_value = meta["label"]
        label = str(label_value) if label_value else key[1]
        theme_style = self._theme.artist_options(artist_method) if self._theme is not None else {}
        return self.merge_style(default_style, theme_style, style_map, label=label)

    def _finalize_figure(self, fig: Figure) -> None:
        if self._theme is not None:
            return
        if self._default_ax is None and hasattr(fig, "tight_layout"):
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", message="Glyph .* missing from font", category=UserWarning)
                fig.tight_layout()

    def _resolve_target_axes(self, provided_ax: Axes | None) -> tuple[Figure, Axes]:
        plt = self.ensure_matplotlib()
        if self._theme is not None:
            self._theme.apply_matplotlib()
        if provided_ax is not None:
            return provided_ax.figure, provided_ax
        if self._default_ax is not None:
            return self._default_ax.figure, self._default_ax
        if self._theme is not None:
            figure_options = self._theme.figure_options()
            fig = plt.figure(
                figsize=(
                    float(figure_options["width_cm"]) / 2.54,
                    float(figure_options["height_cm"]) / 2.54,
                ),
                dpi=int(figure_options["dpi"]),
            )
            ax = fig.add_axes(figure_options["add_axes_rect"])
            return fig, ax
        fig, ax = plt.subplots()
        return fig, ax

    def _apply_axis_frame(self, ax: Axes) -> None:
        self._axis_frame.apply(ax)
        if self._grid_frame is not None:
            self._grid_frame.apply(ax)

    def _set_axis_labels_if_missing(self, ax: Axes, *, xlabel: str, ylabel: str) -> None:
        if not ax.get_xlabel():
            ax.set_xlabel(xlabel)
        if not ax.get_ylabel():
            ax.set_ylabel(ylabel)

    def _collect_visible_legend_items(self, ax: Axes) -> tuple[list[Any], list[str]]:
        handles, labels = ax.get_legend_handles_labels()
        visible_handles: list[Any] = []
        visible_labels: list[str] = []
        for handle, label in zip(handles, labels, strict=True):
            if label == "_nolegend_":
                continue
            visible_handles.append(handle)
            visible_labels.append(label)
        return visible_handles, visible_labels

    def _apply_legend(self, ax: Axes, *, legend_options: Mapping[str, Any] | None) -> None:
        if legend_options is None:
            return

        options = dict(self.default_legend_options or {})
        if self._theme is not None:
            options.update(self._theme.legend_options())
        options.update(legend_options)

        handles, labels = self._collect_visible_legend_items(ax)
        if not handles:
            return
        helper = LegendHelper(ax)
        helper.apply(legend_options=options, handles=handles, labels=labels)

    def _resolve_stat_metrics(self, stats: Sequence[StatMetricInput] | None) -> tuple[PlotStatMetric, ...]:
        if not stats:
            return tuple()
        return tuple(normalize_stat_metric(item) for item in stats)

    def _sample_keys(self, keys: Sequence[tuple[str, str]]) -> list[tuple[str, str]]:
        return [key for key in keys if key[0] == PlotCategory.SAMPLE.value]

    def _sample_matrix(self, dataset: PlotDataset, sample_keys: Sequence[tuple[str, str]]) -> np.ndarray:
        if not sample_keys:
            raise ValueError("自动统计至少需要一列 SAMPLE 数据。")
        return np.column_stack([dataset._column_values(key) for key in sample_keys]).astype(float)

    def _register_proxy_artist(
        self,
        ax: Axes,
        *,
        label: str,
        style: Mapping[str, Any],
        marker_only: bool = False,
    ) -> Line2D:
        line_style = "none" if marker_only else str(style.get("linestyle", "-"))
        handle = Line2D(
            [],
            [],
            label=label,
            color=style.get("color"),
            linewidth=style.get("linewidth", 1.0),
            linestyle=line_style,
            marker=style.get("marker"),
            markerfacecolor=style.get("markerfacecolor"),
            markeredgecolor=style.get("markeredgecolor"),
            markersize=style.get("markersize"),
        )
        ax.add_line(handle)
        return handle


__all__ = ["PlotterBase"]
