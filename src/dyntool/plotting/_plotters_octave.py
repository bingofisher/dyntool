"""倍频程 plotter 与其内部支持。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd
from matplotlib.axes import Axes

from ._axis_config_adapter import apply_octave_axis_config, resolve_axis_config
from ._plotters_base import PlotterBase
from ._plotters_common import StatMetricInput, _STAT_STYLE_DEFAULTS, compute_statistic, stat_label
from .axis_config import AxisConfig
from .config import PlotTheme
from .dataset import PlotCategory, PlotDataset
from .types import PlotResult, PlotterKind

_ASSETS_DIR = Path(__file__).resolve().parent / "assets"


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
        """读取倍频程真值表。"""

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
        """基于默认真值表构造频带规格。"""

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
        """返回指定频带号的中心频率。"""

        reference_band_number = self._derive_reference_band_number(self.band_octaves, self.reference_frequency)
        exponent = (int(band_number) - reference_band_number) * self.band_octaves
        return float(self.reference_frequency * (self.OCTAVE_RATIO**exponent))

    def band_numbers_from_range(
        self,
        lower_frequency: float | None = None,
        upper_frequency: float | None = None,
    ) -> list[int]:
        """按频率范围推导连续频带号。"""

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
        """校验频率数组是否可映射到连续倍频程频带。"""

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

    @staticmethod
    def _default_band_spec() -> OctaveBandSpec:
        """返回正式三分之一倍频程绘图使用的内部频带规格。"""

        return OctaveBandSpec.from_default_table(lower_frequency=1.0, upper_frequency=80.0)

    def __init__(
        self,
        ax: Axes | None = None,
        *,
        theme: PlotTheme | None = None,
        axis_config: AxisConfig | None = None,
    ) -> None:
        """构造正式三分之一倍频程 plotter。"""

        super().__init__(ax=ax, theme=theme)
        self._band_spec = self._default_band_spec()
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
        freqs = dataset._axis_values()
        self._band_spec.validate_segment(freqs)
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
                    compute_statistic(sample_matrix, metric),
                    label=stat_label(metric, stat_label_overrides),
                    **_STAT_STYLE_DEFAULTS[metric],
                )
        axis_unit = self._resolve_axis_unit(dataset, keys)
        value_unit = self._resolve_value_unit(dataset, keys)
        self._set_axis_labels_if_missing(
            target_ax,
            xlabel=self.with_unit(self.default_x_label, axis_unit),
            ylabel=self.with_unit(self.default_y_label, value_unit),
        )
        resolved_axis_config = resolve_axis_config(
            theme_axis_config=self._theme.axis_config if self._theme is not None else None,
            plotter_axis_config=self._axis_config,
            runtime_axis_config=axis_config,
        )
        apply_octave_axis_config(
            target_ax,
            dataset=dataset,
            keys=keys,
            freqs=freqs,
            x_positions=x_positions,
            axis_config=resolved_axis_config,
        )
        self._apply_tick_label_options(target_ax)
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


__all__ = ["OctaveBandSpec", "OneThirdOctavePlotter"]
