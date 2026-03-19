"""计算模板流水线。"""

from __future__ import annotations

from typing import Any, Iterable, Protocol

import numpy as np

from .context import ComputeContext
from .flow import ComputeFlow
from .metrics import respspec_from_accel
from .signals import (
    BaselineMethod,
    FilterKind,
    baseline_correct,
    fft_with_phase,
    filter_signal,
    truncate,
)


class _AccelLike(Protocol):
    """加速度样本的最小协议。"""

    dt: float

    def get_axis(self) -> np.ndarray: ...

    def get_value(self) -> np.ndarray: ...

    def current_units(self) -> dict[str, str]: ...


def _is_accel_like(accel: Any) -> bool:
    return all(hasattr(accel, name) for name in ("get_axis", "get_value", "dt", "current_units"))


def _coerce_accel(
    accel: Any | np.ndarray | list[float], dt: float | None
) -> tuple[np.ndarray, np.ndarray, float, dict[str, str]]:
    if _is_accel_like(accel):
        current_units = accel.current_units()
        axis = np.asarray(accel.get_axis())
        value = np.asarray(accel.get_value())
        return axis, value, accel.dt, current_units
    if dt is None:
        raise TypeError("当输入为数组时必须提供 dt")
    value = np.asarray(accel, dtype=float)
    axis = np.arange(value.size, dtype=float) * float(dt)
    return axis, value, float(dt), {"time": "second", "value": "meter/second**2"}


def accel_preprocess_template(
    accel: Any | np.ndarray | list[float],
    *,
    dt: float | None = None,
    context: ComputeContext | None = None,
    truncate_range: tuple[float, float] | None = None,
    baseline_method: BaselineMethod | str | None = None,
    highpass: float | None = None,
    lowpass: float | None = None,
    bandpass: tuple[float, float] | None = None,
    filter_order: int = 4,
) -> ComputeFlow:
    """加速度预处理模板。"""

    ctx = context or ComputeContext()
    axis, value, dt_val, _ = _coerce_accel(accel, dt)
    flow = ComputeFlow(_result={"axis": axis, "value": value, "dt": dt_val}, context=ctx)
    flow.add_artifact("input", {"axis": axis, "value": value})

    if truncate_range is not None:
        axis, value = truncate(axis, value, truncate_range[0], truncate_range[1])
        flow.add_artifact("truncate", {"axis": axis, "value": value})

    if baseline_method is not None:
        value = baseline_correct(value, method=baseline_method)
        flow.add_artifact("baseline", {"value": value})

    fs = 1.0 / dt_val
    if highpass is not None:
        value = filter_signal(
            value,
            fs=fs,
            kind=FilterKind.HIGHPASS,
            freq=highpass,
            order=filter_order,
        )
        flow.add_artifact("highpass", {"value": value, "freq": highpass})
    if lowpass is not None:
        value = filter_signal(
            value,
            fs=fs,
            kind=FilterKind.LOWPASS,
            freq=lowpass,
            order=filter_order,
        )
        flow.add_artifact("lowpass", {"value": value, "freq": lowpass})
    if bandpass is not None:
        value = filter_signal(
            value,
            fs=fs,
            kind=FilterKind.BANDPASS,
            freq=bandpass[0],
            f_high=bandpass[1],
            order=filter_order,
        )
        flow.add_artifact(
            "bandpass",
            {"value": value, "f_low": bandpass[0], "f_high": bandpass[1]},
        )

    flow.set_result({"axis": axis, "value": value, "dt": dt_val}, action="preprocess_done")
    flow.add_metric("sample_count", float(value.size))
    return flow


def freq_eval_template(
    accel: Any | np.ndarray | list[float],
    *,
    dt: float | None = None,
    context: ComputeContext | None = None,
) -> ComputeFlow:
    """频谱分析模板。"""

    ctx = context or ComputeContext()
    axis, value, dt_val, units = _coerce_accel(accel, dt)
    if _is_accel_like(accel) and hasattr(accel, "calc_freqspec"):
        freqspec = accel.calc_freqspec(output_unit_system=ctx.output_unit_system)
    else:
        freq, amp, phase = fft_with_phase(
            value,
            dt=dt_val,
            value_unit=units["value"],
            output_value_unit=units["value"],
            output_frequency_unit=ctx.output_unit_system.frequency,
            output_phase_unit=ctx.output_unit_system.phase,
        )
        freqspec = {
            "freq": freq,
            "amp": amp,
            "phase": phase,
            "units": {
                "freq": ctx.output_unit_system.frequency,
                "amp": units["value"],
                "phase": ctx.output_unit_system.phase,
            },
        }
    flow = ComputeFlow(_result=freqspec, context=ctx)
    flow.add_artifact("accel", {"axis": axis, "value": value})
    flow.add_artifact("freqspec", freqspec)
    flow.add_metric("fft_points", float(value.size))
    return flow


def resp_eval_template(
    accel: Any | np.ndarray | list[float],
    *,
    dt: float | None = None,
    context: ComputeContext | None = None,
) -> ComputeFlow:
    """反应谱分析模板。"""

    ctx = context or ComputeContext()
    axis, value, dt_val, units = _coerce_accel(accel, dt)
    if _is_accel_like(accel) and hasattr(accel, "calc_respspec_bundle"):
        respspec = accel.calc_respspec_bundle(output_unit_system=ctx.output_unit_system)
    else:
        respspec = respspec_from_accel(
            value,
            dt_val,
            accel_unit=units["value"],
            calc_unit_system=ctx.calc_unit_system,
            output_unit_system=ctx.output_unit_system,
        )
    flow = ComputeFlow(_result=respspec, context=ctx)
    flow.add_artifact("respspec", respspec)
    return flow


def sample_batch_template(
    items: Iterable[Any],
    *,
    runner: Any,
    context: ComputeContext | None = None,
) -> ComputeFlow:
    """样本批处理模板。"""

    ctx = context or ComputeContext()
    results = [runner(item, context=ctx) for item in items]
    flow = ComputeFlow(_result=results, context=ctx)
    flow.add_metric("batch_size", float(len(results)))
    return flow


__all__ = [
    "accel_preprocess_template",
    "freq_eval_template",
    "resp_eval_template",
    "sample_batch_template",
]
