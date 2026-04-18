"""plotting 正式轴配置到内部 helper 的适配层。"""

from __future__ import annotations

from typing import Sequence

import numpy as np
from matplotlib.axes import Axes

from ._axes_formatters import DiscreteAxisFormatter
from ._axes_helpers import AxisHelper
from .axis_config import AxisConfig, ContinuousAxisSpec, OctaveAxisSpec
from .dataset import PlotDataset


def resolve_axis_config(
    *,
    theme_axis_config: AxisConfig | None,
    plotter_axis_config: AxisConfig | None,
    runtime_axis_config: AxisConfig | None,
) -> AxisConfig | None:
    """按正式优先级合并轴配置。"""

    return AxisConfig.merge(theme_axis_config, plotter_axis_config, runtime_axis_config)


def apply_frame_axis_config(
    ax: Axes,
    *,
    dataset: PlotDataset,
    keys: Sequence[tuple[str, str]],
    axis_config: AxisConfig | None,
) -> None:
    """对 FramePlotter 应用正式轴配置。"""

    if axis_config is None:
        return
    helper = AxisHelper(ax)
    if axis_config.x is not None:
        if not isinstance(axis_config.x, ContinuousAxisSpec):
            raise ValueError("FramePlotter 仅支持 continuous 类型的 x 轴配置。")
        helper.format_axis(
            side="bottom",
            mode="continuous",
            data=dataset._axis_values(),
            **_continuous_kwargs(axis_config.x),
        )
    if axis_config.y is not None:
        if not isinstance(axis_config.y, ContinuousAxisSpec):
            raise ValueError("FramePlotter 仅支持 continuous 类型的 y 轴配置。")
        helper.format_axis(
            side="left",
            mode="continuous",
            data=_collect_column_values(dataset, keys),
            **_continuous_kwargs(axis_config.y),
        )


def apply_story_value_axis_config(
    ax: Axes,
    *,
    dataset: PlotDataset,
    keys: Sequence[tuple[str, str]],
    axis_config: AxisConfig | None,
) -> None:
    """对 StoryValuePlotter 应用正式轴配置。"""

    if axis_config is None:
        return
    helper = AxisHelper(ax)
    if axis_config.x is not None:
        if not isinstance(axis_config.x, ContinuousAxisSpec):
            raise ValueError("StoryValuePlotter 仅支持 continuous 类型的 x 轴配置。")
        helper.format_axis(
            side="bottom",
            mode="continuous",
            data=_collect_column_values(dataset, keys),
            **_continuous_kwargs(axis_config.x),
        )
    if axis_config.y is not None:
        if not isinstance(axis_config.y, ContinuousAxisSpec):
            raise ValueError("StoryValuePlotter 仅支持 continuous 类型的 y 轴配置。")
        helper.format_axis(
            side="left",
            mode="continuous",
            data=dataset._axis_values(),
            **_continuous_kwargs(axis_config.y),
        )


def apply_octave_axis_config(
    ax: Axes,
    *,
    dataset: PlotDataset,
    keys: Sequence[tuple[str, str]],
    freqs: np.ndarray,
    x_positions: np.ndarray,
    axis_config: AxisConfig | None,
) -> None:
    """对 OneThirdOctavePlotter 应用正式轴配置。"""

    helper = AxisHelper(ax)
    if axis_config is None or axis_config.x is None:
        formatter = DiscreteAxisFormatter.from_number_values(positions=x_positions, values=freqs)
        helper.format_axis(
            side="bottom",
            mode="discrete",
            positions=formatter.positions,
            labels=formatter.labels,
            show_every=formatter.show_every,
        )
        ax.tick_params(axis="x", which="minor", labelbottom=False, labeltop=False)
    else:
        if not isinstance(axis_config.x, OctaveAxisSpec):
            raise ValueError("OneThirdOctavePlotter 仅支持 octave 类型的 x 轴配置。")
        if axis_config.x.positions is not None and axis_config.x.labels is not None:
            positions = axis_config.x.positions
            labels = axis_config.x.labels
            show_every = axis_config.x.show_every
        else:
            formatter = DiscreteAxisFormatter.from_number_values(
                positions=x_positions,
                values=freqs,
                show_every=axis_config.x.show_every,
            )
            positions = formatter.positions
            labels = formatter.labels
            show_every = formatter.show_every
        helper.format_axis(
            side="bottom",
            mode="discrete",
            positions=positions,
            labels=labels,
            show_every=show_every,
        )
        ax.tick_params(axis="x", which="minor", labelbottom=False, labeltop=False)

    if axis_config is not None and axis_config.y is not None:
        if not isinstance(axis_config.y, ContinuousAxisSpec):
            raise ValueError("OneThirdOctavePlotter 仅支持 continuous 类型的 y 轴配置。")
        helper.format_axis(
            side="left",
            mode="continuous",
            data=_collect_column_values(dataset, keys),
            **_continuous_kwargs(axis_config.y),
        )


def _collect_column_values(dataset: PlotDataset, keys: Sequence[tuple[str, str]]) -> np.ndarray:
    series_list = [dataset._column_values(key).astype(float) for key in keys]
    if not series_list:
        return np.asarray([], dtype=float)
    return np.concatenate(series_list)


def _continuous_kwargs(spec: ContinuousAxisSpec) -> dict[str, object]:
    return {
        "ticks": spec.ticks,
        "major_step": spec.major_step,
        "num_segments": spec.num_segments,
        "tick_min": spec.tick_min,
        "tick_max": spec.tick_max,
        "minor_step": spec.minor_step,
        "include_zero": spec.include_zero,
        "baseline": spec.baseline,
        "height_ratio": spec.height_ratio,
        "decimals": spec.decimals,
        "trim_trailing_zeros": spec.trim_trailing_zeros,
        "scientific": spec.scientific,
        "scientific_fontsize": spec.scientific_fontsize,
        "scientific_exponent": spec.scientific_exponent,
        "scientific_offset_x": spec.scientific_offset_x,
        "scientific_offset_y": spec.scientific_offset_y,
    }


__all__ = [
    "apply_frame_axis_config",
    "apply_octave_axis_config",
    "apply_story_value_axis_config",
    "resolve_axis_config",
]
