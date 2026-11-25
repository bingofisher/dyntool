"""计算模板流水线。"""

from __future__ import annotations

from typing import Any, Iterable, Protocol

import numpy as np

from .context import ComputeContext
from .flow import ComputeFlow
from .units import convert_array, UnitSystem
from .metrics import _ResponseSpectrumRequest
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


class _AccelerationInput:
    """规范化数组与带单位输入；dt 和处理参数始终使用秒与 Hz。"""

    @staticmethod
    def read(
        accel: Any, dt: float | None, context: ComputeContext
    ) -> tuple[np.ndarray, np.ndarray, float, dict[str, str]]:
        """返回原输入值单位及 SI 时间轴，不借用可写输入数组。"""
        if _is_accel_like(accel):
            units = accel.current_units()
            axis = convert_array(accel.get_axis(), from_unit=units["time"], to_unit="second")
            value, interval = np.asarray(accel.get_value()), float(accel.dt)
        else:
            if dt is None:
                raise TypeError("当输入为数组时必须提供 dt（秒）")
            value, interval = np.asarray(accel, dtype=float), float(dt)
            units = {"time": "second", "value": context.input_unit_system.acceleration}
            if value.ndim not in (1, 2):
                raise ValueError("输入必须为时间序列或时间 × 通道数组")
            axis = np.arange(value.shape[0], dtype=float) * interval
        if not np.isfinite(interval) or interval <= 0:
            raise ValueError("采样间隔 dt 必须是有限正数，单位为秒")
        if value.ndim not in (1, 2):
            raise ValueError("输入必须为时间序列或时间 × 通道数组")
        return axis, value, interval, units

    @staticmethod
    def single_channel(value: np.ndarray) -> np.ndarray:
        """频谱和响应谱模板明确要求单通道。"""
        if value.ndim == 2 and value.shape[1] == 1:
            return value[:, 0]
        if value.ndim != 1:
            raise ValueError("频谱和响应谱模板只支持单通道，请先选择通道")
        return value


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
    axis, value, dt_val, units = _AccelerationInput.read(accel, dt, ctx)
    value = convert_array(value, from_unit=units["value"], to_unit=UnitSystem.si().acceleration)
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

    value = convert_array(value, from_unit=UnitSystem.si().acceleration, to_unit=ctx.output_unit_system.acceleration)
    flow.set_result(
        {
            "axis": axis,
            "value": value,
            "dt": dt_val,
            "units": {"time": "second", "value": ctx.output_unit_system.acceleration},
        },
        action="preprocess_done",
    )
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
    axis, value, dt_val, units = _AccelerationInput.read(accel, dt, ctx)
    if _is_accel_like(accel) and hasattr(accel, "calc_freqspec"):
        freqspec = accel.calc_freqspec(output_unit_system=ctx.output_unit_system if context is not None else None)
    else:
        freq, amp, phase = fft_with_phase(
            _AccelerationInput.single_channel(value),
            dt=dt_val,
            value_unit=units["value"],
            output_value_unit=ctx.output_unit_system.acceleration if context is not None else units["value"],
            output_frequency_unit=ctx.output_unit_system.frequency,
            output_phase_unit=ctx.output_unit_system.phase,
        )
        freqspec = {
            "freq": freq,
            "amp": amp,
            "phase": phase,
            "units": {
                "freq": ctx.output_unit_system.frequency,
                "amp": ctx.output_unit_system.acceleration if context is not None else units["value"],
                "phase": ctx.output_unit_system.phase,
            },
        }
    flow = ComputeFlow(_result=freqspec, context=ctx)
    flow.add_artifact("accel", {"axis": axis, "value": value, "units": units})
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
    axis, value, dt_val, units = _AccelerationInput.read(accel, dt, ctx)
    respspec = _ResponseSpectrumRequest(ctx.damping_ratio).solve(
        _AccelerationInput.single_channel(value),
        dt_val,
        accel_unit=units["value"],
        calc_unit_system=ctx.calc_unit_system,
        output_unit_system=ctx.output_unit_system,
    )
    if _is_accel_like(accel):
        respspec = accel._respspec_from_compute_result(
            respspec,
            {
                "dt": dt_val,
                "damping_ratio": ctx.damping_ratio,
                "calc_unit_system": ctx.calc_unit_system,
                "output_unit_system": ctx.output_unit_system,
            },
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
