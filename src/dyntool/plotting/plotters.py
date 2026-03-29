"""plotter-first 正式绘图器。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence, TypeAlias
import warnings

import numpy as np
import pandas as pd
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from numpy.typing import ArrayLike

from ..domain.limits.base import LimitModelBase
from ..domain.models.base import DataModelBase
from .axes import AxisFrame, AxisHelper, DiscreteAxisFormatter, GridFrame, LegendHelper
from .dataset import PlotCategory, PlotDataset
from .types import PlotResult, PlotStatMetric, PlotterKind

_ASSETS_DIR = Path(__file__).resolve().parent / "assets"
PlotInput: TypeAlias = (
    PlotDataset | pd.DataFrame | np.ndarray | tuple[ArrayLike, ArrayLike] | DataModelBase | LimitModelBase
)

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


def _normalize_stat_metric(metric: StatMetricInput) -> PlotStatMetric:
    if isinstance(metric, PlotStatMetric):
        return metric
    return PlotStatMetric(str(metric).strip().lower())


def _stat_label(metric: PlotStatMetric, overrides: Mapping[str, str] | None = None) -> str:
    if overrides is None:
        return metric.label
    return str(overrides.get(metric.value, metric.label))


def _compute_statistic(values: np.ndarray, metric: PlotStatMetric) -> np.ndarray:
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
    """将 BoxPlotter 的扁平命名空间样式解析为 ``Axes.boxplot`` 的 ``*props``。"""

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
        table = PlotterBase.read_csv_table(path)
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
        """基于内置真值表构建频带规格。"""

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
        """校验一段频率数组是否可映射到连续倍频程频带。"""

        values = PlotterBase.coerce_array(freqs)
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


class PlotterBase:
    """plotter-first 绘图主入口基类。"""

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
        axis_frame: AxisFrame | None = None,
        grid_frame: GridFrame | None = None,
    ) -> None:
        self._default_ax = ax
        self._axis_frame = axis_frame or AxisFrame.default()
        self._grid_frame = grid_frame
        self._dataset: PlotDataset | None = None

    @property
    def ax(self) -> Axes | None:
        """返回默认绑定的 ``Axes``。"""

        return self._default_ax

    @ax.setter
    def ax(self, value: Axes | None) -> None:
        """设置默认绑定的 ``Axes``。"""

        self._default_ax = value

    @property
    def axis_frame(self) -> AxisFrame:
        """返回默认轴样式配置。"""

        return self._axis_frame

    @axis_frame.setter
    def axis_frame(self, value: AxisFrame | None) -> None:
        """设置默认轴样式配置。

        Notes:
            样式会在真正绘制到目标 ``Axes`` 时再次应用。若当前已经绑定默认 ``Axes``，
            这里会先对默认轴立即应用一次，便于交互场景快速预览。
        """

        self._axis_frame = value or AxisFrame.default()
        if self._default_ax is not None:
            self._axis_frame.apply(self._default_ax)

    @property
    def grid_frame(self) -> GridFrame | None:
        """返回默认网格样式配置。"""

        return self._grid_frame

    @grid_frame.setter
    def grid_frame(self, value: GridFrame | None) -> None:
        """设置默认网格样式配置。"""

        self._grid_frame = value
        if self._default_ax is not None and self._grid_frame is not None:
            self._grid_frame.apply(self._default_ax)

    @staticmethod
    def ensure_matplotlib() -> Any:
        """按需导入 matplotlib。"""

        import matplotlib.pyplot as plt

        return plt

    @staticmethod
    def read_csv_table(path: str | Path) -> pd.DataFrame:
        """读取 plotting 使用的 CSV 表。"""

        return pd.read_csv(path, encoding="utf-8")

    @staticmethod
    def coerce_array(values: ArrayLike) -> np.ndarray:
        """把输入规范为一维浮点数组。"""

        return np.asarray(values, dtype=float).flatten()

    @staticmethod
    def with_unit(label: str, unit: str | None) -> str:
        """拼接坐标轴标签和单位。"""

        return f"{label} [{unit}]" if unit else label

    @staticmethod
    def merge_style(*style_sources: Mapping[str, Any], label: str | None = None) -> dict[str, Any]:
        """按优先级合并样式。"""

        merged: dict[str, Any] = {}
        for source in style_sources:
            merged.update(source)
        if label is not None:
            merged["label"] = label
        return merged

    def set_dataset(self, dataset: PlotDataset) -> None:
        """设置当前 plotter 持有的数据集。"""

        self._dataset = dataset

    def get_dataset(self) -> PlotDataset:
        """返回当前 plotter 持有的数据集。"""

        if self._dataset is None:
            raise ValueError("当前 plotter 尚未绑定 PlotDataset。")
        return self._dataset

    def add(
        self,
        data: PlotInput | None = None,
        *,
        axis: ArrayLike | None = None,
        value: ArrayLike | None = None,
        name: str | None = None,
        category: PlotCategory | str | None = None,
        label: str | None = None,
        names: Sequence[str] | None = None,
    ) -> PlotDataset:
        """向当前 plotter 追加输入数据。"""

        dataset = self._coerce_dataset(
            data,
            axis=axis,
            value=value,
            name=name,
            category=category,
            label=label,
            names=names,
        )
        if self._dataset is None:
            self._dataset = dataset
        else:
            self._dataset._extend(dataset)
        return self._dataset

    def plot(
        self,
        *,
        categories: Sequence[PlotCategory | str] | None = None,
        names: Sequence[str] | None = None,
        ax: Axes | None = None,
        legend_options: Mapping[str, Any] | None = None,
        **plot_options: Any,
    ) -> PlotResult:
        """绘制当前持有的数据集。"""

        return self.plot_dataset(
            self.get_dataset(),
            categories=categories,
            names=names,
            ax=ax,
            legend_options=legend_options,
            **plot_options,
        )

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
        """绘制显式提供的数据集。"""

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

    def _coerce_dataset(
        self,
        data: PlotInput | None,
        *,
        axis: ArrayLike | None = None,
        value: ArrayLike | None = None,
        name: str | None = None,
        category: PlotCategory | str | None = None,
        label: str | None = None,
        names: Sequence[str] | None = None,
    ) -> PlotDataset:
        if axis is not None or value is not None:
            if axis is None or value is None:
                raise ValueError("axis 和 value 需要同时提供。")
            return PlotDataset.from_axis_value(
                axis=axis,
                value=value,
                name=name or "series-1",
                category=category or self.default_category,
                label=label,
            )
        if isinstance(data, PlotDataset):
            return data
        if isinstance(data, pd.DataFrame):
            return PlotDataset.from_dataframe(data, category=category)
        if isinstance(data, np.ndarray):
            return PlotDataset.from_array2d(
                data,
                category=category or self.default_category,
                names=names,
            )
        if isinstance(data, tuple) and len(data) == 2:
            return PlotDataset.from_axis_value(
                axis=data[0],
                value=data[1],
                name=name or "series-1",
                category=category or self.default_category,
                label=label,
            )
        if isinstance(data, LimitModelBase):
            return PlotDataset.from_limit(
                data,
                name=name,
                category=category or PlotCategory.LIMIT,
                label=label,
            )
        if isinstance(data, DataModelBase):
            return PlotDataset.from_model(
                data,
                name=name,
                category=category or self.default_category,
                label=label,
            )
        raise TypeError(f"不支持的绘图输入类型: {type(data).__name__}")

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
    ) -> dict[str, Any]:
        meta = dataset._column_meta(key)
        raw_style = meta["style"]
        style_map = raw_style if isinstance(raw_style, Mapping) else {}
        label_value = meta["label"]
        label = str(label_value) if label_value else key[1]
        return self.merge_style(default_style, style_map, label=label)

    def _finalize_figure(self, fig: Figure) -> None:
        """在内部创建 figure 时做收尾布局。"""

        if self._default_ax is None and hasattr(fig, "tight_layout"):
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", message="Glyph .* missing from font", category=UserWarning)
                fig.tight_layout()

    def _resolve_target_axes(self, provided_ax: Axes | None) -> tuple[Figure, Axes]:
        plt = self.ensure_matplotlib()
        if provided_ax is not None:
            return provided_ax.figure, provided_ax
        if self._default_ax is not None:
            return self._default_ax.figure, self._default_ax
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

    def _apply_legend(
        self,
        ax: Axes,
        *,
        legend_options: Mapping[str, Any] | None,
    ) -> None:
        if legend_options is None:
            return

        options = dict(self.default_legend_options or {})
        options.update(legend_options)

        handles, labels = self._collect_visible_legend_items(ax)
        if not handles:
            return
        helper = LegendHelper(ax)
        helper.apply(legend_options=options, handles=handles, labels=labels)

    def _resolve_stat_metrics(self, stats: Sequence[StatMetricInput] | None) -> tuple[PlotStatMetric, ...]:
        if not stats:
            return tuple()
        return tuple(_normalize_stat_metric(item) for item in stats)

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


class FramePlotter(PlotterBase):
    """通用二维曲线绘图器。"""

    plotter_kind = PlotterKind.FRAME
    default_x_label = "x"
    default_y_label = "value"
    category_order = (
        PlotCategory.SAMPLE.value,
        PlotCategory.ENVELOPE.value,
        PlotCategory.STAT.value,
        PlotCategory.LIMIT.value,
    )
    default_legend_options = {"loc": "best"}

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
        axis_values = dataset._axis_values()
        for key in keys:
            style = self._resolve_style(dataset, key, default_style={})
            target_ax.plot(axis_values, dataset._column_values(key), **style)
        sample_keys = self._sample_keys(keys)
        stat_metrics = self._resolve_stat_metrics(stats)
        if stat_metrics and sample_keys:
            sample_matrix = self._sample_matrix(dataset, sample_keys)
            for metric in stat_metrics:
                target_ax.plot(
                    axis_values,
                    _compute_statistic(sample_matrix, metric),
                    label=_stat_label(metric, stat_label_overrides),
                    **_STAT_STYLE_DEFAULTS[metric],
                )
        axis_unit = self._resolve_axis_unit(dataset, keys)
        value_unit = self._resolve_value_unit(dataset, keys)
        self._set_axis_labels_if_missing(
            target_ax,
            xlabel=self.with_unit(self.default_x_label, axis_unit),
            ylabel=self.with_unit(self.default_y_label, value_unit),
        )
        self._apply_legend(target_ax, legend_options=legend_options)
        self._finalize_figure(fig)
        return PlotResult(raw=fig, figure=fig, axes=(target_ax,))


class _LegacyBoxPlotter(PlotterBase):
    """基于 ``PlotDataset`` 的箱型图绘图器。"""

    plotter_kind = PlotterKind.BOX
    default_x_label = "group"
    default_y_label = "value"
    category_order = (
        PlotCategory.SAMPLE.value,
        PlotCategory.LIMIT.value,
    )
    default_legend_options = {"loc": "best"}

    def _plot_dataset(
        self,
        dataset: PlotDataset,
        *,
        categories: Sequence[PlotCategory | str] | None = None,
        names: Sequence[str] | None = None,
        ax: Axes | None = None,
        legend_options: Mapping[str, Any] | None = None,
    ) -> PlotResult:
        keys = [item.as_tuple() for item in self._sorted_keys(dataset, categories=categories, names=names)]
        if not keys:
            raise ValueError("当前 PlotDataset 中没有匹配的箱型图数据。")

        sample_keys = [key for key in keys if key[0] == PlotCategory.SAMPLE.value]
        if not sample_keys:
            raise ValueError("箱型图至少需要一组 SAMPLE 数据。")
        limit_keys = [key for key in keys if key[0] == PlotCategory.LIMIT.value]

        sample_values = [self._finite_sample_values(dataset, key) for key in sample_keys]
        if not any(values.size > 0 for values in sample_values):
            raise ValueError("箱型图至少需要一组非空样本。")
        if any(values.size == 0 for values in sample_values):
            raise ValueError("箱型图的每个 SAMPLE 列都必须包含至少一个有效样本。")

        fig, target_ax = self._resolve_target_axes(ax)
        self._apply_axis_frame(target_ax)

        positions = np.arange(1, len(sample_keys) + 1, dtype=float)
        boxplot = target_ax.boxplot(
            sample_values,
            positions=positions,
            widths=0.55,
            patch_artist=True,
            showmeans=True,
            meanline=True,
            boxprops={"facecolor": "#dddddd", "edgecolor": "black", "linewidth": 0.8},
            whiskerprops={"color": "black", "linewidth": 0.8},
            capprops={"color": "black", "linewidth": 0.8},
            medianprops={"color": "black", "linewidth": 0.8},
            meanprops={"color": "blue", "linewidth": 1.5, "linestyle": "-"},
            flierprops={
                "marker": "o",
                "markerfacecolor": "red",
                "markeredgecolor": "red",
                "markersize": 4,
                "linestyle": "none",
            },
        )

        target_ax.set_xticks(positions)
        target_ax.set_xticklabels([self._sample_label(dataset, key) for key in sample_keys])

        limit_artists = tuple(self._plot_limit_lines(target_ax, dataset, limit_keys))
        value_unit = self._resolve_value_unit(dataset, sample_keys + limit_keys)
        self._set_axis_labels_if_missing(
            target_ax,
            xlabel=self.default_x_label,
            ylabel=self.with_unit(self.default_y_label, value_unit),
        )
        self._apply_box_legend(target_ax, dataset, limit_keys, legend_options=legend_options)
        self._finalize_figure(fig)

        artists = (
            tuple(boxplot.get("boxes", ()))
            + tuple(boxplot.get("whiskers", ()))
            + tuple(boxplot.get("caps", ()))
            + tuple(boxplot.get("medians", ()))
            + tuple(boxplot.get("means", ()))
            + tuple(boxplot.get("fliers", ()))
            + limit_artists
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

    def _plot_limit_lines(
        self,
        ax: Axes,
        dataset: PlotDataset,
        limit_keys: Sequence[tuple[str, str]],
    ) -> list[Line2D]:
        artists: list[Line2D] = []
        for key in limit_keys:
            value = self._resolve_limit_value(dataset, key)
            style = self._resolve_style(
                dataset,
                key,
                default_style={"linewidth": 1.0, "linestyle": "--", "color": "darkorange"},
            )
            artists.append(ax.axhline(value, **style))
        return artists

    @staticmethod
    def _resolve_limit_value(dataset: PlotDataset, key: tuple[str, str]) -> float:
        raw_values = np.asarray(dataset._column_values(key), dtype=float)
        finite_values = raw_values[np.isfinite(raw_values)]
        if finite_values.size == 0:
            raise ValueError("限值线必须是单一数值水平线。")
        first = float(finite_values[0])
        if not np.allclose(finite_values, first):
            raise ValueError("限值线必须是单一数值水平线。")
        return first

    def _apply_box_legend(
        self,
        ax: Axes,
        dataset: PlotDataset,
        limit_keys: Sequence[tuple[str, str]],
        *,
        legend_options: Mapping[str, Any] | None,
    ) -> None:
        if legend_options is None:
            return

        options = dict(self.default_legend_options or {})
        options.update(legend_options)

        handles: list[Line2D] = [
            Line2D([0], [0], color="blue", linewidth=1.5, linestyle="-", label="均值"),
            Line2D(
                [0],
                [0],
                color="red",
                marker="o",
                linestyle="none",
                markersize=4,
                label="异常值",
            ),
        ]
        labels = ["均值", "异常值"]

        for key in limit_keys:
            meta = dataset._column_meta(key)
            style = meta["style"] if isinstance(meta["style"], Mapping) else {}
            label = str(meta["label"]) if meta["label"] else key[1]
            handles.append(
                Line2D(
                    [0],
                    [0],
                    color=str(style.get("color", "darkorange")),
                    linewidth=float(style.get("linewidth", 1.0)),
                    linestyle=str(style.get("linestyle", "--")),
                    label=label,
                )
            )
            labels.append(label)

        helper = LegendHelper(ax)
        helper.apply(legend_options=options, handles=handles, labels=labels)


class BoxPlotter(PlotterBase):
    """基于 ``PlotDataset`` 的箱型图 plotter。

    Public API:
        - 输入仍为 ``PlotDataset``，每个 ``SAMPLE`` 列对应一个箱体组。
        - 样式来源于列级 ``style`` 元数据，可通过
          ``PlotDataset.from_axis_value(..., style=...)``、
          ``PlotDataset.add_axis_value(..., style=...)``、
          ``PlotDataset.set_style(...)`` 写入。
        - ``style_defaults`` 允许在 plotter 级提供箱型图默认样式，再由列级 ``style`` 覆盖。

    支持的样式键:
        - ``box.facecolor`` / ``box.edgecolor`` / ``box.linewidth`` / ``box.linestyle``
        - ``whisker.color`` / ``whisker.linewidth`` / ``whisker.linestyle``
        - ``cap.color`` / ``cap.linewidth`` / ``cap.linestyle``
        - ``median.color`` / ``median.linewidth`` / ``median.linestyle``
        - ``mean.color`` / ``mean.linewidth`` / ``mean.linestyle``
        - ``flier.marker`` / ``flier.markerfacecolor`` / ``flier.markeredgecolor`` / ``flier.markersize``

    映射关系:
        - ``box.*`` -> ``Axes.boxplot(..., boxprops=...)``
        - ``whisker.*`` -> ``Axes.boxplot(..., whiskerprops=...)``
        - ``cap.*`` -> ``Axes.boxplot(..., capprops=...)``
        - ``median.*`` -> ``Axes.boxplot(..., medianprops=...)``
        - ``mean.*`` -> ``Axes.boxplot(..., meanprops=...)``
        - ``flier.*`` -> ``Axes.boxplot(..., flierprops=...)``
    """

    plotter_kind = PlotterKind.BOX
    default_x_label = "group"
    default_y_label = "value"
    category_order = (PlotCategory.SAMPLE.value,)
    default_legend_options = {"loc": "best"}

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
            label = _stat_label(metric, stat_label_overrides)
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


class OneThirdOctavePlotter(PlotterBase):
    """三分之一倍频程绘图器。"""

    plotter_kind = PlotterKind.ONE_THIRD_OCTAVE
    default_x_label = "freq"
    default_y_label = "level"
    category_order = (
        PlotCategory.SAMPLE.value,
        PlotCategory.ENVELOPE.value,
        PlotCategory.LIMIT.value,
    )
    default_legend_options = {"loc": "best"}

    def __init__(
        self,
        ax: Axes | None = None,
        *,
        axis_frame: AxisFrame | None = None,
        grid_frame: GridFrame | None = None,
        band_spec: OctaveBandSpec | None = None,
    ) -> None:
        super().__init__(ax=ax, axis_frame=axis_frame, grid_frame=grid_frame)
        self.band_spec = band_spec or OctaveBandSpec.from_default_table(lower_frequency=1.0, upper_frequency=80.0)

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
        freqs = dataset._axis_values()
        self.band_spec.validate_segment(freqs)
        fig, target_ax = self._resolve_target_axes(ax)
        self._apply_axis_frame(target_ax)
        x_positions = np.arange(freqs.shape[0], dtype=float)
        for key in keys:
            default_style = self._default_style_for_category(key[0])
            style = self._resolve_style(dataset, key, default_style=default_style)
            target_ax.plot(x_positions, dataset._column_values(key), **style)
        sample_keys = self._sample_keys(keys)
        stat_metrics = self._resolve_stat_metrics(stats)
        if stat_metrics and sample_keys:
            sample_matrix = self._sample_matrix(dataset, sample_keys)
            for metric in stat_metrics:
                target_ax.plot(
                    x_positions,
                    _compute_statistic(sample_matrix, metric),
                    label=_stat_label(metric, stat_label_overrides),
                    **_STAT_STYLE_DEFAULTS[metric],
                )
        axis_unit = self._resolve_axis_unit(dataset, keys)
        value_unit = self._resolve_value_unit(dataset, keys)
        self._set_axis_labels_if_missing(
            target_ax,
            xlabel=self.with_unit(self.default_x_label, axis_unit),
            ylabel=self.with_unit(self.default_y_label, value_unit),
        )
        helper = AxisHelper(target_ax)
        formatter = DiscreteAxisFormatter.from_number_values(positions=x_positions, values=freqs)
        helper.format_axis(
            side="bottom",
            mode="discrete",
            positions=formatter.positions,
            labels=formatter.labels,
            show_every=formatter.show_every,
        )
        target_ax.tick_params(axis="x", which="minor", labelbottom=False, labeltop=False)
        self._apply_legend(target_ax, legend_options=legend_options)
        self._finalize_figure(fig)
        return PlotResult(raw=fig, figure=fig, axes=(target_ax,))

    @staticmethod
    def _default_style_for_category(category: str) -> Mapping[str, Any]:
        if category == PlotCategory.LIMIT.value:
            return {"color": "orange", "linewidth": 2.0, "linestyle": "--"}
        if category == PlotCategory.ENVELOPE.value:
            return {"color": "blue", "linewidth": 2.0, "marker": "o", "markersize": 6}
        return {
            "color": "lightgray",
            "linewidth": 0.8,
            "marker": "o",
            "markersize": 2,
            "alpha": 0.9,
        }


class StoryValuePlotter(PlotterBase):
    """楼层或剖面值绘图器。"""

    plotter_kind = PlotterKind.STORY_VALUE
    default_x_label = "value"
    default_y_label = "level"
    category_order = (
        PlotCategory.SAMPLE.value,
        PlotCategory.STAT.value,
        PlotCategory.LIMIT.value,
    )
    default_legend_options = {"loc": "best"}

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
                style = self._resolve_style(dataset, key, default_style={"linewidth": 1.0, "linestyle": "--"})
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
                    _compute_statistic(sample_matrix, metric),
                    axis,
                    label=_stat_label(metric, stat_label_overrides),
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


__all__ = [
    "BoxPlotter",
    "FramePlotter",
    "OctaveBandSpec",
    "OneThirdOctavePlotter",
    "PlotterBase",
    "StoryValuePlotter",
]
