"""时程序列时间域变换相关的内部辅助函数。"""

from __future__ import annotations

from typing import Any

import numpy as np

from ..constants import convert_array
from ...compute.signals import (
    BaselineMethod,
    FilterKind,
    baseline_correct,
    filter_signal,
    truncate,
)


def _rebuild_from_second_axis(series: Any, value: np.ndarray, *, time_in_second: np.ndarray) -> Any:
    """按秒单位时间轴重建与原对象同类的新时程序列。"""

    return series.__class__._from_base_data(
        value,
        time=convert_array(
            time_in_second,
            from_unit="second",
            to_unit=series.axis_unit,
        ),
        units=series.current_units(),
    )


def _rebuild_from_base_axis(series: Any, value: np.ndarray) -> Any:
    """按对象当前基础时间轴重建与原对象同类的新时程序列。"""

    return series.__class__._from_base_data(
        value,
        time=series._base_axis_values(),
        units=series.current_units(),
    )


def truncate_time_series(series: Any, start: float, end: float) -> Any:
    """按秒为单位裁剪时程。"""

    axis_new, value_new = truncate(
        series.get_axis(unit="second"),
        series._base_value_values(),
        start,
        end,
    )
    return _rebuild_from_second_axis(series, value_new, time_in_second=axis_new)


def resample_uniform_time_series(
    series: Any,
    *,
    target_dt: float,
    start: float | None = None,
    end: float | None = None,
    method: str = "linear",
) -> Any:
    """重采样到显式给定的等间距时间轴。"""

    if target_dt <= 0:
        raise ValueError("target_dt must be positive.")
    if method != "linear":
        raise ValueError("当前仅支持 linear 重采样。")
    base_time = series.get_axis(unit="second")
    if len(base_time) < 2:
        raise ValueError("至少需要两个时间点才能重采样。")
    diffs = np.diff(base_time)
    if np.any(diffs <= 0):
        raise ValueError("时间轴必须严格递增后才能重采样。")
    start_time = float(base_time[0] if start is None else start)
    end_time = float(base_time[-1] if end is None else end)
    if end_time <= start_time:
        raise ValueError("end must be greater than start.")
    count = int(np.floor((end_time - start_time) / target_dt)) + 1
    if count < 2:
        raise ValueError("重采样后的时间轴至少需要两个采样点。")
    resampled_time = start_time + target_dt * np.arange(count, dtype=np.float64)
    base_value = series._base_value_values()
    if base_value.ndim == 1:
        resampled_value = np.interp(resampled_time, base_time, base_value)
    elif base_value.ndim == 2:
        resampled_value = np.column_stack(
            [np.interp(resampled_time, base_time, base_value[:, idx]) for idx in range(base_value.shape[1])]
        )
    else:
        raise ValueError("value only supports 1D or 2D arrays.")
    return _rebuild_from_second_axis(series, resampled_value, time_in_second=resampled_time)


def resample_like_time_series(series: Any, other: Any, *, method: str = "linear") -> Any:
    """按目标时程的时间轴执行重采样。"""

    other.require_uniform_time()
    info = other.sampling_info()
    dt = info["dt"]
    start = info["start"]
    end = info["end"]
    if not isinstance(dt, float) or not isinstance(start, float) or not isinstance(end, float):
        raise ValueError("目标时间轴信息不足，无法执行重采样。")
    return resample_uniform_time_series(
        series,
        target_dt=dt,
        start=start,
        end=end,
        method=method,
    )


def baseline_correct_time_series(
    series: Any,
    *,
    method: BaselineMethod | str = BaselineMethod.LINEAR,
    order: int = 1,
) -> Any:
    """执行基线修正，并保持当前单位不变。"""

    corrected = baseline_correct(series._base_value_values(), method=method, order=order)
    return _rebuild_from_base_axis(series, corrected)


def filter_time_series(
    series: Any,
    *,
    kind: FilterKind,
    freq: float,
    order: int = 4,
    f_high: float | None = None,
) -> Any:
    """执行滤波，并保持当前单位不变。"""

    filtered = filter_signal(
        series._base_value_values(),
        fs=1.0 / series.dt,
        kind=kind,
        freq=freq,
        f_high=f_high,
        order=order,
    )
    return _rebuild_from_base_axis(series, filtered)


__all__ = [
    "baseline_correct_time_series",
    "filter_time_series",
    "resample_like_time_series",
    "resample_uniform_time_series",
    "truncate_time_series",
]
