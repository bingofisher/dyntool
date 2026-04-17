"""时程序列积分与微分相关的内部辅助函数。"""

from __future__ import annotations

from typing import Any

from ..constants import convert_array, get_default_unit_system
from ...compute.signals import Differentiation, Integration


def integrate_accel_series_to_vel(
    series: Any,
    *,
    method: Any,
    calc_unit_system: Any | None = None,
    output_unit: str | None = None,
    output_unit_system: Any | None = None,
    **options: Any,
) -> Any:
    """将加速度时程序列积分为速度。"""

    from .time_series import VelSeries

    calc_units = calc_unit_system or get_default_unit_system()
    out_units = output_unit_system or get_default_unit_system()
    vel_array = Integration(
        y=series.get_value(unit=calc_units.acceleration),
        dx=series.dt,
    ).integ1d(method=method, **options)
    target_value_unit = output_unit or out_units.velocity
    units = {"time": out_units.time, "value": target_value_unit}
    return VelSeries._from_base_data(
        convert_array(
            vel_array,
            from_unit=calc_units.velocity,
            to_unit=target_value_unit,
        ),
        time=series.get_axis(unit=out_units.time),
        units=units,
        unit_system=out_units,
    )


def integrate_vel_series_to_disp(
    series: Any,
    *,
    method: Any,
    calc_unit_system: Any | None = None,
    output_unit: str | None = None,
    output_unit_system: Any | None = None,
    **options: Any,
) -> Any:
    """将速度时程序列积分为位移。"""

    from .time_series import DispSeries

    calc_units = calc_unit_system or get_default_unit_system()
    out_units = output_unit_system or get_default_unit_system()
    disp_array = Integration(
        y=series.get_value(unit=calc_units.velocity),
        dx=series.dt,
    ).integ1d(method=method, **options)
    target_value_unit = output_unit or out_units.displacement
    units = {"time": out_units.time, "value": target_value_unit}
    return DispSeries._from_base_data(
        convert_array(
            disp_array,
            from_unit=calc_units.displacement,
            to_unit=target_value_unit,
        ),
        time=series.get_axis(unit=out_units.time),
        units=units,
        unit_system=out_units,
    )


def differentiate_vel_series_to_accel(
    series: Any,
    *,
    method: Any,
    calc_unit_system: Any | None = None,
    output_unit: str | None = None,
    output_unit_system: Any | None = None,
    **options: Any,
) -> Any:
    """将速度时程序列微分为加速度。"""

    from .time_series import AccelSeries

    calc_units = calc_unit_system or get_default_unit_system()
    out_units = output_unit_system or get_default_unit_system()
    accel_array = Differentiation(
        y=series.get_value(unit=calc_units.velocity),
        dx=series.dt,
    ).diff1d(method=method, **options)
    target_value_unit = output_unit or out_units.acceleration
    units = {"time": out_units.time, "value": target_value_unit}
    return AccelSeries._from_base_data(
        convert_array(
            accel_array,
            from_unit=calc_units.acceleration,
            to_unit=target_value_unit,
        ),
        time=series.get_axis(unit=out_units.time),
        units=units,
        unit_system=out_units,
    )


def differentiate_disp_series_to_vel(
    series: Any,
    *,
    method: Any,
    calc_unit_system: Any | None = None,
    output_unit: str | None = None,
    output_unit_system: Any | None = None,
    **options: Any,
) -> Any:
    """将位移时程序列微分为速度。"""

    from .time_series import VelSeries

    calc_units = calc_unit_system or get_default_unit_system()
    out_units = output_unit_system or get_default_unit_system()
    vel_array = Differentiation(
        y=series.get_value(unit=calc_units.displacement),
        dx=series.dt,
    ).diff1d(method=method, **options)
    target_value_unit = output_unit or out_units.velocity
    units = {"time": out_units.time, "value": target_value_unit}
    return VelSeries._from_base_data(
        convert_array(
            vel_array,
            from_unit=calc_units.velocity,
            to_unit=target_value_unit,
        ),
        time=series.get_axis(unit=out_units.time),
        units=units,
        unit_system=out_units,
    )


__all__ = [
    "differentiate_disp_series_to_vel",
    "differentiate_vel_series_to_accel",
    "integrate_accel_series_to_vel",
    "integrate_vel_series_to_disp",
]
