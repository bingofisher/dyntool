"""时程序列频谱与评价相关的内部辅助函数。"""

from __future__ import annotations

from typing import Any

from ..constants import get_default_unit_system, resolve_unit_system
from ...compute.metrics import (
    fdmvl_from_accel,
    fpvdv_from_accel,
    otovl_from_accel,
    respspec_from_accel,
    zvl_from_accel,
)
from ...compute.signals import fft_with_phase


def calc_fft_with_phase_time_series(
    series: Any,
    *,
    output_unit_system: Any | None = None,
) -> tuple[Any, Any, Any]:
    """计算 FFT 并按目标单位返回频率、幅值和相位。"""

    output_units = resolve_unit_system(output_unit_system)
    data = series.get_value(unit=series._base_value_unit())
    if data.ndim > 1:
        data = series._value_array_1d(unit=series._base_value_unit())
    return fft_with_phase(
        data,
        dt=series.dt,
        value_unit=series._base_value_unit(),
        output_value_unit=series.value_unit,
        output_frequency_unit=output_units.frequency,
        output_phase_unit=output_units.phase,
    )


def calc_freqspec_time_series(
    series: Any,
    *,
    output_unit_system: Any | None = None,
) -> Any:
    """计算通用频谱对象。"""

    from .frequency_spectrum import FreqSpec

    units = output_unit_system or get_default_unit_system()
    freqs, mag, phase = calc_fft_with_phase_time_series(series, output_unit_system=units)
    return FreqSpec.from_compute_result(
        {
            "freq": freqs,
            "amp": mag,
            "pha": phase,
            "units": {
                "freq": units.frequency,
                "amp": series.value_unit,
                "phase": units.phase,
            },
            "unit_system": units,
        },
        unit_system=units,
    )


def calc_fft_amp_series_from_accel(
    series: Any,
    *,
    output_unit_system: Any | None = None,
) -> Any:
    """计算加速度幅值频谱。"""

    from .frequency_spectrum import FreqAmpSeries

    units = output_unit_system or get_default_unit_system()
    freqs, mag = series.calc_fft(output_unit_system=units)
    return FreqAmpSeries.from_data(
        freqs,
        mag,
        units={"freq": units.frequency, "amp": series.value_unit},
        unit_system=units,
    )


def calc_fft_phase_series_from_accel(
    series: Any,
    *,
    output_unit_system: Any | None = None,
) -> Any:
    """计算加速度相位频谱。"""

    from .frequency_spectrum import FreqPhaSeries

    units = output_unit_system or get_default_unit_system()
    freqs, _, phase = calc_fft_with_phase_time_series(series, output_unit_system=units)
    return FreqPhaSeries.from_data(
        freqs,
        phase,
        units={"freq": units.frequency, "phase": units.phase},
        unit_system=units,
    )


def calc_freqspec_from_accel_series(
    series: Any,
    *,
    output_unit_system: Any | None = None,
) -> Any:
    """计算加速度组合频谱对象。"""

    from .frequency_spectrum import FreqSpec

    units = output_unit_system or get_default_unit_system()
    freqs, mag, phase = calc_fft_with_phase_time_series(series, output_unit_system=units)
    return FreqSpec.from_data(
        freqs,
        amp=mag,
        pha=phase,
        units={
            "freq": units.frequency,
            "amp": series.value_unit,
            "phase": units.phase,
        },
        unit_system=units,
    )


def calc_respspec_from_accel_series(
    series: Any,
    *,
    method: Any,
    calc_unit_system: Any | None = None,
    output_unit_system: Any | None = None,
    periods: Any | None = None,
) -> Any:
    """按显式单位规则由加速度计算响应谱。"""

    from .response_spectrum import RespSpec

    calc_units = calc_unit_system or get_default_unit_system()
    out_units = output_unit_system or get_default_unit_system()
    result = respspec_from_accel(
        series.get_value(unit=calc_units.acceleration),
        series.dt,
        periods=periods,
        method=method,
        accel_unit=calc_units.acceleration,
        calc_unit_system=calc_units,
        output_unit_system=out_units,
    )
    return RespSpec.from_compute_result(result, unit_system=out_units)


def calc_respspec_component_from_accel_series(
    series: Any,
    component: str,
    *,
    method: Any,
    calc_unit_system: Any | None = None,
    output_unit_system: Any | None = None,
    periods: Any | None = None,
) -> Any:
    """计算响应谱分量。"""

    bundle = calc_respspec_from_accel_series(
        series,
        method=method,
        calc_unit_system=calc_unit_system,
        output_unit_system=output_unit_system,
        periods=periods,
    )
    result = getattr(bundle, component, None)
    if result is None:
        raise ValueError(f"Response spectrum component {component!r} is unavailable.")
    return result


def eval_zvl_from_accel_series(
    series: Any,
    *,
    freq_range: tuple[float, float],
    weight_type: Any,
    time_windows: float,
    calc_unit_system: Any | None = None,
    output_unit_system: Any | None = None,
) -> Any:
    """根据加速度数据计算 Z 振级。"""

    from .vibration_evaluation import ZVLEval

    calc_units = calc_unit_system or get_default_unit_system()
    result = zvl_from_accel(
        series.get_value(unit=calc_units.acceleration),
        series.dt,
        freq_range=freq_range,
        weight_type=weight_type,
        time_windows=time_windows,
        accel_unit=calc_units.acceleration,
        calc_unit_system=calc_units,
        output_unit_system=output_unit_system,
    )
    return ZVLEval.from_compute_result(result)


def eval_otovl_from_accel_series(
    series: Any,
    *,
    freq_range: tuple[float, float],
    time_windows: float,
    calc_unit_system: Any | None = None,
    output_unit_system: Any | None = None,
) -> Any:
    """根据加速度数据计算三分之一倍频程振级。"""

    from .vibration_evaluation import OTOVLEval

    calc_units = calc_unit_system or get_default_unit_system()
    result = otovl_from_accel(
        series.get_value(unit=calc_units.acceleration),
        series.dt,
        freq_range=freq_range,
        time_windows=time_windows,
        accel_unit=calc_units.acceleration,
        calc_unit_system=calc_units,
        output_unit_system=output_unit_system,
    )
    return OTOVLEval.from_compute_result(result)


def eval_fpvdv_from_accel_series(
    series: Any,
    *,
    freq_range: tuple[float, float],
    nsup: int,
    calc_unit_system: Any | None = None,
    output_unit_system: Any | None = None,
) -> Any:
    """根据加速度数据计算 FPVDV。"""

    from .vibration_evaluation import FPVDVEval

    calc_units = calc_unit_system or get_default_unit_system()
    result = fpvdv_from_accel(
        series.get_value(unit=calc_units.acceleration),
        series.dt,
        freq_range=freq_range,
        nsup=nsup,
        accel_unit=calc_units.acceleration,
        calc_unit_system=calc_units,
        output_unit_system=output_unit_system,
    )
    return FPVDVEval.from_compute_result(result)


def eval_fdmvl_from_accel_series(
    series: Any,
    *,
    freq_range: tuple[float, float],
    calc_unit_system: Any | None = None,
    output_unit_system: Any | None = None,
) -> Any:
    """根据加速度数据计算 FDMVL。"""

    from .vibration_evaluation import FDMVLEval

    calc_units = calc_unit_system or get_default_unit_system()
    result = fdmvl_from_accel(
        series.get_value(unit=calc_units.acceleration),
        series.dt,
        freq_range=freq_range,
        accel_unit=calc_units.acceleration,
        calc_unit_system=calc_units,
        output_unit_system=output_unit_system,
    )
    return FDMVLEval.from_compute_result(result)


__all__ = [
    "calc_fft_amp_series_from_accel",
    "calc_fft_phase_series_from_accel",
    "calc_fft_with_phase_time_series",
    "calc_freqspec_from_accel_series",
    "calc_freqspec_time_series",
    "calc_respspec_component_from_accel_series",
    "calc_respspec_from_accel_series",
    "eval_fdmvl_from_accel_series",
    "eval_fpvdv_from_accel_series",
    "eval_otovl_from_accel_series",
    "eval_zvl_from_accel_series",
]
