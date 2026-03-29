"""振动评价与响应谱底层计算入口。"""

from __future__ import annotations

from typing import Any

import numpy as np

from .solvers import (
    FreqDivMaxVibLevelSolver,
    FourPowVibDoseValueSolver,
    LinearSequence,
    OneThirdOctaveVibLevelSolver,
    SDOFSolveMethod,
    SDOFSolver,
    WeightType,
    ZVibLevelSolver,
)
from .units import UnitSystem, convert_array, get_default_unit_system


def zvl_from_accel(
    accel_mag: np.ndarray,
    dt: float,
    *,
    freq_range: tuple[float, float] = (1.0, 80.0),
    weight_type: WeightType = WeightType.WK,
    time_windows: float = 1.0,
    accel_unit: str | None = None,
    calc_unit_system: UnitSystem | None = None,
    output_unit_system: UnitSystem | None = None,
) -> dict[str, Any]:
    """根据加速度时程计算 Z 振级。"""

    calc_units = calc_unit_system or get_default_unit_system()
    out_units = output_unit_system or get_default_unit_system()
    accel = convert_array(
        accel_mag,
        from_unit=accel_unit or calc_units.acceleration,
        to_unit=calc_units.acceleration,
    )
    solver = ZVibLevelSolver(
        accel=accel,
        fs=int(round(1.0 / dt)),
        freq_range=freq_range,
        weight_type=weight_type,
        time_windows=time_windows,
    )
    zvl, aw = solver.solve()
    return {
        "zvl": float(
            convert_array(
                np.asarray([zvl]),
                from_unit=calc_units.level,
                to_unit=out_units.level,
            ).flat[0]
        ),
        "aw": float(
            convert_array(
                np.asarray([aw]),
                from_unit=calc_units.weighted_acceleration,
                to_unit=out_units.weighted_acceleration,
            ).flat[0]
        ),
        "units": {"zvl": out_units.level, "aw": out_units.weighted_acceleration},
        "unit_system": out_units,
    }


def otovl_from_accel(
    accel_mag: np.ndarray,
    dt: float,
    *,
    freq_range: tuple[float, float] = (1.0, 80.0),
    time_windows: float = 1.0,
    accel_unit: str | None = None,
    calc_unit_system: UnitSystem | None = None,
    output_unit_system: UnitSystem | None = None,
) -> dict[str, Any]:
    """根据加速度时程计算 1/3 倍频程分频振级。"""

    calc_units = calc_unit_system or get_default_unit_system()
    out_units = output_unit_system or get_default_unit_system()
    accel = convert_array(
        accel_mag,
        from_unit=accel_unit or calc_units.acceleration,
        to_unit=calc_units.acceleration,
    )
    solver = OneThirdOctaveVibLevelSolver(
        accel=accel,
        fs=int(round(1.0 / dt)),
        freq_range=freq_range,
        time_windows=time_windows,
    )
    otovl_env, otovl_data = solver.solve()
    return {
        "freq": convert_array(
            solver.center_freqs,
            from_unit=calc_units.frequency,
            to_unit=out_units.frequency,
        ),
        "comps": convert_array(
            otovl_data,
            from_unit=calc_units.level,
            to_unit=out_units.level,
        ),
        "env": convert_array(
            otovl_env,
            from_unit=calc_units.level,
            to_unit=out_units.level,
        ),
        "units": {
            "freq": out_units.frequency,
            "comps": out_units.level,
            "env": out_units.level,
        },
        "unit_system": out_units,
    }


def fdmvl_from_accel(
    accel_mag: np.ndarray,
    dt: float,
    *,
    freq_range: tuple[float, float] = (1.0, 80.0),
    accel_unit: str | None = None,
    calc_unit_system: UnitSystem | None = None,
    output_unit_system: UnitSystem | None = None,
) -> dict[str, Any]:
    """根据加速度时程计算分频最大振级。"""

    calc_units = calc_unit_system or get_default_unit_system()
    out_units = output_unit_system or get_default_unit_system()
    accel = convert_array(
        accel_mag,
        from_unit=accel_unit or calc_units.acceleration,
        to_unit=calc_units.acceleration,
    )
    solver = FreqDivMaxVibLevelSolver(
        accel=accel,
        fs=int(round(1.0 / dt)),
        freq_range=freq_range,
    )
    fdmvl, fdvls = solver.solve()
    return {
        "fdmvl": float(
            convert_array(
                np.asarray([fdmvl]),
                from_unit=calc_units.level,
                to_unit=out_units.level,
            ).flat[0]
        ),
        "freq": convert_array(
            solver.center_freqs,
            from_unit=calc_units.frequency,
            to_unit=out_units.frequency,
        ),
        "fdvls": convert_array(
            fdvls,
            from_unit=calc_units.level,
            to_unit=out_units.level,
        ),
        "units": {
            "fdmvl": out_units.level,
            "freq": out_units.frequency,
            "fdvls": out_units.level,
        },
        "unit_system": out_units,
    }


def fpvdv_from_accel(
    accel_mag: np.ndarray,
    dt: float,
    *,
    freq_range: tuple[float, float] = (1.0, 80.0),
    nsup: int = 1,
    accel_unit: str | None = None,
    calc_unit_system: UnitSystem | None = None,
    output_unit_system: UnitSystem | None = None,
) -> dict[str, Any]:
    """根据加速度时程计算四次方振动剂量值。"""

    calc_units = calc_unit_system or get_default_unit_system()
    out_units = output_unit_system or get_default_unit_system()
    accel = convert_array(
        accel_mag,
        from_unit=accel_unit or calc_units.acceleration,
        to_unit=calc_units.acceleration,
    )
    solver = FourPowVibDoseValueSolver(
        accel=accel,
        fs=int(round(1.0 / dt)),
        freq_range=freq_range,
        nsup=nsup,
    )
    fpvdv, aw = solver.solve()
    aw_time = LinearSequence.generate_time(num=aw.shape[0], dt=dt)
    return {
        "fpvdv": float(
            convert_array(
                np.asarray([fpvdv]),
                from_unit=calc_units.vibration_dose_value,
                to_unit=out_units.vibration_dose_value,
            ).flat[0]
        ),
        "aw_time": convert_array(
            aw_time,
            from_unit="second",
            to_unit=out_units.time,
        ),
        "aw_value": convert_array(
            aw,
            from_unit=calc_units.weighted_acceleration,
            to_unit=out_units.weighted_acceleration,
        ),
        "units": {
            "fpvdv": out_units.vibration_dose_value,
            "aw_time": out_units.time,
            "aw_value": out_units.weighted_acceleration,
        },
        "unit_system": out_units,
    }


def respspec_from_accel(
    accel_mag: np.ndarray,
    dt: float,
    *,
    periods: np.ndarray | None = None,
    method: SDOFSolveMethod = SDOFSolveMethod.NIGAM_JENNINGS,
    accel_unit: str | None = None,
    calc_unit_system: UnitSystem | None = None,
    output_unit_system: UnitSystem | None = None,
) -> dict[str, Any]:
    """根据加速度时程计算响应谱。"""

    calc_units = calc_unit_system or get_default_unit_system()
    out_units = output_unit_system or get_default_unit_system()
    if periods is None:
        periods = np.arange(0.01, 6.01, 0.01)
    accel_si = convert_array(
        accel_mag,
        from_unit=accel_unit or calc_units.acceleration,
        to_unit=calc_units.acceleration,
    )
    frame = SDOFSolver.solve_from_accel(
        periods=periods,
        accel=accel_si,
        accel_dt=dt,
        method=method,
    )
    return {
        "period": convert_array(
            frame["periods (s)"].to_numpy(),
            from_unit="second",
            to_unit=out_units.period,
        ),
        "sa": convert_array(
            frame["sa (m/s^2)"].to_numpy(),
            from_unit=calc_units.acceleration,
            to_unit=out_units.acceleration,
        ),
        "sv": convert_array(
            frame["sv (m/s)"].to_numpy(),
            from_unit=calc_units.velocity,
            to_unit=out_units.velocity,
        ),
        "sd": convert_array(
            frame["sd (m)"].to_numpy(),
            from_unit=calc_units.displacement,
            to_unit=out_units.displacement,
        ),
        "psa": convert_array(
            frame["psa (m/s^2)"].to_numpy(),
            from_unit=calc_units.acceleration,
            to_unit=out_units.acceleration,
        ),
        "psv": convert_array(
            frame["psv (m/s)"].to_numpy(),
            from_unit=calc_units.velocity,
            to_unit=out_units.velocity,
        ),
        "units": {
            "period": out_units.period,
            "sa": out_units.acceleration,
            "sv": out_units.velocity,
            "sd": out_units.displacement,
            "psa": out_units.acceleration,
            "psv": out_units.velocity,
        },
        "unit_system": out_units,
    }


__all__ = [
    "fdmvl_from_accel",
    "fpvdv_from_accel",
    "otovl_from_accel",
    "respspec_from_accel",
    "zvl_from_accel",
]
