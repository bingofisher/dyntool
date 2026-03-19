"""时程序列模型。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar, Mapping, Self

import numpy as np
import pandas as pd
import xarray as xr

from .conversion import MagnitudeConversion
from .base import DataModelBase
from ..constants import (
    DataCategory,
    UnitSystem,
    convert_array,
    format_label_with_unit,
    get_default_unit_system,
    normalize_unit_map,
    parse_label_unit,
    resolve_unit_system,
    resolve_current_units,
    resolve_file_units,
)
from ...compute.metrics import (
    fdmvl_from_accel,
    fpvdv_from_accel,
    otovl_from_accel,
    respspec_from_accel,
    zvl_from_accel,
)
from ...compute.signals import (
    BaselineMethod,
    DiffMethod,
    Differentiation,
    FilterKind,
    IntegMethod,
    Integration,
    baseline_correct,
    fft_with_phase,
    filter_signal,
    truncate,
)
from ...compute.solvers import LinearSequence, SDOFSolveMethod, WeightType

if TYPE_CHECKING:
    from .frequency_spectrum import FreqAmpSeries, FreqPhaSeries, FreqSpec
    from .response_spectrum import (
        PSpecAccelSeries,
        PSpecVelSeries,
        RespSpec,
        ResponseSpectrum,
        SpecAccelSeries,
        SpecDispSeries,
        SpecVelSeries,
    )
    from .vibration_evaluation import FDMVLEval, FPVDVEval, OTOVLEval, ZVLEval


_CURRENT_UNITS_ATTR = "_current_units"


class TimeSeries(DataModelBase):
    """基于 ``xarray.DataArray`` 的时程序列基类。"""

    category: ClassVar[DataCategory] = DataCategory.TS
    axis_field: ClassVar[str | None] = "time"
    value_field: ClassVar[str | None] = "value"

    def __init__(self, data: xr.DataArray) -> None:
        if "time" not in data.dims and "time" not in data.coords:
            raise ValueError("TimeSeries requires a `time` dimension or coordinate.")
        self._data = data

    @property
    def xr(self) -> xr.DataArray:
        """返回基础单位存储的底层 ``xarray.DataArray``。"""

        return self._data

    @property
    def xr_base(self) -> xr.DataArray:
        """返回内部基础单位存储的底层 ``xarray.DataArray``。"""

        return self._data

    @property
    def time(self) -> np.ndarray:
        """返回当前单位下的时间轴。"""

        return self.get_axis()

    @property
    def value(self) -> np.ndarray:
        """返回当前单位下的数值数组。"""

        return self.get_value()

    @property
    def dt(self) -> float:
        """返回以秒为单位的采样间隔。"""

        t = self.get_axis(unit="second")
        if len(t) < 2:
            raise ValueError("At least two time samples are required to compute dt.")
        if not LinearSequence.is_uniform(t):
            raise ValueError("Time samples must be uniform to compute dt.")
        return float(t[1] - t[0])

    @property
    def is_uniform_time(self) -> bool:
        """返回时间轴是否等间隔采样。"""

        t = self.get_axis(unit="second")
        return len(t) < 3 or LinearSequence.is_uniform(t)

    def sampling_info(self) -> dict[str, float | int | bool | None]:
        """返回当前采样状态的简要摘要。"""

        t = self.get_axis(unit="second")
        info: dict[str, float | int | bool | None] = {
            "num_samples": int(len(t)),
            "start": float(t[0]) if len(t) else None,
            "end": float(t[-1]) if len(t) else None,
            "is_uniform": self.is_uniform_time,
            "dt": None,
            "dt_min": None,
            "dt_max": None,
        }
        if len(t) < 2:
            return info
        diffs = np.diff(t)
        info["dt_min"] = float(np.min(diffs))
        info["dt_max"] = float(np.max(diffs))
        if self.is_uniform_time:
            info["dt"] = float(diffs[0])
        return info

    def require_uniform_time(self) -> Self:
        """若时间轴等间隔则返回自身，否则抛出异常。"""

        if not self.is_uniform_time:
            raise ValueError("时间轴不是等间距，请先调用 resample_uniform(...)。")
        return self

    @property
    def absmax(self) -> float:
        """返回当前数值单位下的绝对峰值。"""

        arr = self.get_value()
        return float(np.max(np.abs(arr)))

    @classmethod
    def _base_axis_unit(cls) -> str:
        return "second"

    @classmethod
    def _base_value_unit(cls) -> str:
        return "dimensionless"

    @classmethod
    def _default_current_units(cls, unit_system: UnitSystem | None = None) -> dict[str, str]:
        units = resolve_unit_system(unit_system)
        return {"time": units.time, "value": cls._base_value_unit()}

    @classmethod
    def _resolve_current_units(
        cls,
        *,
        units: Mapping[str, str | None] | None = None,
        unit_system: UnitSystem | None = None,
    ) -> dict[str, str]:
        defaults = cls._default_current_units(unit_system)
        current = resolve_current_units(defaults, units=units)
        if "time" not in current:
            current["time"] = cls._base_axis_unit()
        if "value" not in current:
            current["value"] = cls._base_value_unit()
        return current

    def base_units(self) -> dict[str, str]:
        """返回模型固定的内部基础单位。"""

        time_unit = str(self._data.coords["time"].attrs.get("units", self._base_axis_unit()))
        value_unit = str(self._data.attrs.get("units", self._base_value_unit()))
        return {"time": time_unit, "value": value_unit}

    def current_units(self) -> dict[str, str]:
        """返回实例当前单位。"""

        return self.base_units()

    def _base_axis_values(self) -> np.ndarray:
        return MagnitudeConversion.to_magnitude(self._data.coords["time"]).flatten()

    def _base_value_values(self) -> np.ndarray:
        return MagnitudeConversion.to_magnitude(self._data)

    def get_field(self, name: str, unit: str | None = None) -> np.ndarray:
        """返回字段数组，可按请求单位临时换算。"""

        base = self.base_units()
        if name == "time":
            target = unit or base["time"]
            return convert_array(
                self._base_axis_values(),
                from_unit=base["time"],
                to_unit=target,
            )
        if name == "value":
            target = unit or base["value"]
            return convert_array(
                self._base_value_values(),
                from_unit=base["value"],
                to_unit=target,
            )
        raise KeyError(f"{self.__class__.__name__} does not expose field {name!r}.")

    def convert_units(
        self,
        units: Mapping[str, str | None],
        *,
        replace: bool = True,
    ) -> Self:
        """返回一个仅更新当前单位的新对象。"""

        current = self.current_units().copy()
        current.update(normalize_unit_map(units))
        axis_values = convert_array(
            self._base_axis_values(),
            from_unit=self.base_units()["time"],
            to_unit=current["time"],
        )
        value_values = convert_array(
            self._base_value_values(),
            from_unit=self.base_units()["value"],
            to_unit=current["value"],
        )
        converted = self.__class__._from_base_data(
            value_values,
            time=axis_values,
            units=current,
        )
        if replace:
            self._data = converted._data
            return self
        return converted

    def _value_array_1d(self, unit: str | None = None) -> np.ndarray:
        arr = self.get_value(unit=unit)
        if arr.ndim == 1:
            return arr
        if arr.ndim == 2 and arr.shape[1] == 1:
            return arr[:, 0]
        raise ValueError("This time series contains multiple channels.")

    @classmethod
    def _from_base_data(
        cls,
        value: list | np.ndarray | Any,
        *,
        time: list | np.ndarray | Any,
        units: Mapping[str, str | None] | None = None,
        unit_system: UnitSystem | None = None,
    ) -> Self:
        current = cls._resolve_current_units(units=units, unit_system=unit_system)
        value_arr = np.asarray(value, dtype=np.float64)
        time_arr = np.asarray(time, dtype=np.float64).flatten()
        if value_arr.ndim == 1:
            dims = ["time"]
            data = value_arr
            n = value_arr.shape[0]
        elif value_arr.ndim == 2:
            dims = ["time", "channel"]
            data = value_arr
            n = value_arr.shape[0]
        else:
            raise ValueError("value only supports 1D or 2D arrays.")
        if len(time_arr) != n:
            raise ValueError("time length must match the first dimension of value.")
        da = xr.DataArray(
            data,
            dims=dims,
            coords={"time": ("time", time_arr, {"units": current["time"]})},
            attrs={
                "units": current["value"],
                _CURRENT_UNITS_ATTR: current,
            },
        )
        return cls(da)

    @classmethod
    def from_data(
        cls,
        value: list | np.ndarray | Any,
        *,
        time: list | np.ndarray | Any | None = None,
        dt: float | None = None,
        duration: float | None = None,
        axis_unit: str | None = None,
        data_unit: str | None = None,
        units: Mapping[str, str | None] | None = None,
        unit_system: UnitSystem | None = None,
    ) -> Self:
        """按输入单位构造时程序列，并转换为基础单位存储。"""

        current = cls._resolve_current_units(
            units=cls._merge_input_units(
                axis_unit=axis_unit,
                data_unit=data_unit,
                units=units,
            ),
            unit_system=unit_system,
        )
        value_arr = np.asarray(value, dtype=np.float64)
        if value_arr.ndim == 1:
            n = value_arr.shape[0]
        elif value_arr.ndim == 2:
            n = value_arr.shape[0]
        else:
            raise ValueError("value only supports 1D or 2D arrays.")

        if time is None:
            if dt is None and duration is None:
                raise ValueError("Either `time` or `dt`/`duration` must be provided.")
            dt_current = None
            duration_current = None
            if dt is not None:
                dt_current = float(np.asarray([dt], dtype=np.float64)[0])
            if duration is not None:
                duration_current = float(np.asarray([duration], dtype=np.float64)[0])
            time_arr = LinearSequence.generate_time(dt=dt_current, duration=duration_current, num=n)
        else:
            time_arr = np.asarray(time, dtype=np.float64).flatten()
        return cls._from_base_data(
            value_arr,
            time=time_arr,
            units=current,
            unit_system=unit_system,
        )

    @classmethod
    def from_arrays(cls, axis: np.ndarray, value: np.ndarray, **options: Any) -> Self:
        """根据数组重建时程序列对象。"""

        return cls.from_data(value, time=axis, **options)

    def truncate(self, start: float, end: float) -> Self:
        """按秒为单位裁剪时程。"""

        axis_new, value_new = truncate(
            self.get_axis(unit="second"),
            self._base_value_values(),
            start,
            end,
        )
        return self.__class__._from_base_data(
            value_new,
            time=convert_array(
                axis_new,
                from_unit="second",
                to_unit=self.axis_unit,
            ),
            units=self.current_units(),
        )

    def resample_uniform(
        self,
        *,
        target_dt: float,
        start: float | None = None,
        end: float | None = None,
        method: str = "linear",
    ) -> Self:
        """重采样到显式给定的等间距时间轴。"""

        if target_dt <= 0:
            raise ValueError("target_dt must be positive.")
        if method != "linear":
            raise ValueError("当前仅支持 linear 重采样。")
        base_time = self.get_axis(unit="second")
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
        base_value = self._base_value_values()
        if base_value.ndim == 1:
            resampled_value = np.interp(resampled_time, base_time, base_value)
        elif base_value.ndim == 2:
            resampled_value = np.column_stack(
                [np.interp(resampled_time, base_time, base_value[:, idx]) for idx in range(base_value.shape[1])]
            )
        else:
            raise ValueError("value only supports 1D or 2D arrays.")
        return self.__class__._from_base_data(
            resampled_value,
            time=convert_array(
                resampled_time,
                from_unit="second",
                to_unit=self.axis_unit,
            ),
            units=self.current_units(),
        )

    def resample_like(self, other: "TimeSeries", *, method: str = "linear") -> Self:
        """按目标时程的时间轴进行重采样。"""

        other.require_uniform_time()
        info = other.sampling_info()
        dt = info["dt"]
        start = info["start"]
        end = info["end"]
        if not isinstance(dt, float) or not isinstance(start, float) or not isinstance(end, float):
            raise ValueError("目标时间轴信息不足，无法执行重采样。")
        return self.resample_uniform(
            target_dt=dt,
            start=start,
            end=end,
            method=method,
        )

    def baseline_correct(
        self,
        *,
        method: BaselineMethod | str = BaselineMethod.LINEAR,
        order: int = 1,
    ) -> Self:
        """执行基线修正，并保持当前单位不变。"""

        corrected = baseline_correct(self._base_value_values(), method=method, order=order)
        return self.__class__._from_base_data(
            corrected,
            time=self._base_axis_values(),
            units=self.current_units(),
        )

    def filter_highpass(self, freq: float, *, order: int = 4) -> Self:
        """执行高通滤波，并保持当前单位不变。"""

        filtered = filter_signal(
            self._base_value_values(),
            fs=1.0 / self.dt,
            kind=FilterKind.HIGHPASS,
            freq=freq,
            order=order,
        )
        return self.__class__._from_base_data(
            filtered,
            time=self._base_axis_values(),
            units=self.current_units(),
        )

    def filter_lowpass(self, freq: float, *, order: int = 4) -> Self:
        """执行低通滤波，并保持当前单位不变。"""

        filtered = filter_signal(
            self._base_value_values(),
            fs=1.0 / self.dt,
            kind=FilterKind.LOWPASS,
            freq=freq,
            order=order,
        )
        return self.__class__._from_base_data(
            filtered,
            time=self._base_axis_values(),
            units=self.current_units(),
        )

    def filter_bandpass(self, freq: float, *, f_high: float, order: int = 4) -> Self:
        """执行带通滤波，并保持当前单位不变。"""

        filtered = filter_signal(
            self._base_value_values(),
            fs=1.0 / self.dt,
            kind=FilterKind.BANDPASS,
            freq=freq,
            f_high=f_high,
            order=order,
        )
        return self.__class__._from_base_data(
            filtered,
            time=self._base_axis_values(),
            units=self.current_units(),
        )

    def calc_fft(
        self,
        *,
        output_unit_system: UnitSystem | None = None,
    ) -> tuple[np.ndarray, np.ndarray]:
        """计算 FFT，并返回正频率与幅值。"""

        freqs_pos, mag, _ = self.calc_fft_with_phase(output_unit_system=output_unit_system)
        return freqs_pos, mag

    def calc_fft_with_phase(
        self,
        *,
        output_unit_system: UnitSystem | None = None,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """计算 FFT，并按目标单位返回频率、幅值和相位。"""

        output_units = resolve_unit_system(output_unit_system)
        data = self.get_value(unit=self._base_value_unit())
        if data.ndim > 1:
            data = self._value_array_1d(unit=self._base_value_unit())
        return fft_with_phase(
            data,
            dt=self.dt,
            value_unit=self._base_value_unit(),
            output_value_unit=self.value_unit,
            output_frequency_unit=output_units.frequency,
            output_phase_unit=output_units.phase,
        )

    def to_pandas(self) -> pd.DataFrame:
        """转换为带当前单位表头的 DataFrame。"""

        axis_name = format_label_with_unit("time", self.axis_unit)
        value_name = format_label_with_unit("value", self.value_unit)
        t = self.get_axis()
        v = self.get_value()
        index = pd.Index(t, name=axis_name)
        if v.ndim == 1:
            return pd.DataFrame({value_name: v}, index=index)
        cols = [format_label_with_unit(f"value_{i}", self.value_unit) for i in range(v.shape[1])]
        return pd.DataFrame(v, index=index, columns=cols)

    @classmethod
    def from_pandas(
        cls,
        df: pd.DataFrame,
        *,
        axis_unit: str | None = None,
        data_unit: str | None = None,
        units: Mapping[str, str | None] | None = None,
        unit_system: UnitSystem | None = None,
    ) -> Self:
        """根据 DataFrame 构造时程序列。"""

        _, axis_unit = parse_label_unit(df.index.name or "time")
        parsed_units: dict[str, str | None] = {"time": axis_unit}
        inferred_value_unit = None
        if len(df.columns) == 1:
            _, inferred_value_unit = parse_label_unit(df.columns[0])
        parsed_units["value"] = inferred_value_unit
        current = resolve_file_units(
            {"time", "value"},
            parsed_units=parsed_units,
            units=cls._merge_input_units(
                axis_unit=axis_unit,
                data_unit=data_unit,
                units=units,
            ),
            allow_partial=True,
        )
        default_current = cls._resolve_current_units(
            units=current if current else units,
            unit_system=unit_system,
        )
        t = df.index.to_numpy()
        v = df.iloc[:, 0].to_numpy() if len(df.columns) == 1 else df.to_numpy()
        model = cls.from_data(v, time=t, units=default_current, unit_system=unit_system)
        return model

    def to_dict(self) -> dict[str, Any]:
        """序列化当前单位数组与单位元数据。"""

        return {
            "time": self.get_axis(),
            "value": self.get_value(),
            "_units": self.current_units(),
        }

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
        category: DataCategory | None = None,
        *,
        axis_unit: str | None = None,
        data_unit: str | None = None,
        units: Mapping[str, str | None] | None = None,
        unit_system: UnitSystem | None = None,
    ) -> Self:
        """根据字典负载反序列化时程序列。"""

        del category
        current = resolve_file_units(
            {"time", "value"},
            parsed_units=data.get("_units", {}),
            units=cls._merge_input_units(
                axis_unit=axis_unit,
                data_unit=data_unit,
                units=units,
            ),
            allow_partial=True,
        )
        default_current = cls._resolve_current_units(
            units=current if current else units,
            unit_system=unit_system,
        )
        model = cls.from_data(
            data["value"],
            time=data["time"],
            units=default_current,
            unit_system=unit_system,
        )
        return model


class AccelSeries(TimeSeries):
    """加速度时程。"""

    category: ClassVar[DataCategory] = DataCategory.TS_ACCEL

    @classmethod
    def _base_value_unit(cls) -> str:
        return "meter/second**2"

    @classmethod
    def _default_current_units(cls, unit_system: UnitSystem | None = None) -> dict[str, str]:
        units = unit_system or get_default_unit_system()
        return {"time": units.time, "value": units.acceleration}

    def calc_vel(
        self,
        method: IntegMethod = IntegMethod.SCIPY_CUMTRAPZ,
        *,
        calc_unit_system: UnitSystem | None = None,
        output_unit: str | None = None,
        output_unit_system: UnitSystem | None = None,
        **options: Any,
    ) -> "VelSeries":
        """按固定基准单位规则将加速度积分为速度。

        Args:
            method: 积分方法。
            calc_unit_system: 计算阶段采用的单位制；为空时使用当前默认单位制。
            output_unit: 显式指定输出速度单位；为空时使用 `output_unit_system` 的速度单位。
            output_unit_system: 输出对象采用的单位制。
            **options: 传给积分器的具名参数。当前仅在 `method` 对应的积分实现需要时生效，
                常见键包括 `initial`。
        """

        calc_units = calc_unit_system or get_default_unit_system()
        out_units = output_unit_system or get_default_unit_system()
        vel_array = Integration(
            y=self.get_value(unit=calc_units.acceleration),
            dx=self.dt,
        ).integ1d(method=method, **options)
        target_value_unit = output_unit or out_units.velocity
        units = {"time": out_units.time, "value": target_value_unit}
        return VelSeries._from_base_data(
            convert_array(
                vel_array,
                from_unit=calc_units.velocity,
                to_unit=target_value_unit,
            ),
            time=self.get_axis(unit=out_units.time),
            units=units,
            unit_system=out_units,
        )

    def calc_disp(
        self,
        method: IntegMethod = IntegMethod.SCIPY_CUMTRAPZ,
        *,
        calc_unit_system: UnitSystem | None = None,
        output_unit: str | None = None,
        output_unit_system: UnitSystem | None = None,
        **options: Any,
    ) -> "DispSeries":
        """将加速度二次积分为位移。"""

        return self.calc_vel(
            method=method,
            calc_unit_system=calc_unit_system,
            output_unit_system=output_unit_system,
            **options,
        ).calc_disp(
            method=method,
            calc_unit_system=calc_unit_system,
            output_unit=output_unit,
            output_unit_system=output_unit_system,
            **options,
        )

    def calc_fft_series(
        self,
        *,
        output_unit_system: UnitSystem | None = None,
    ) -> "FreqAmpSeries":
        """按当前单位计算幅值频谱。"""

        from .frequency_spectrum import FreqAmpSeries

        units = output_unit_system or get_default_unit_system()
        freqs, mag = self.calc_fft(output_unit_system=units)
        return FreqAmpSeries.from_data(
            freqs,
            mag,
            units={"freq": units.frequency, "amp": self.value_unit},
            unit_system=units,
        )

    def calc_fft_phase_series(
        self,
        *,
        output_unit_system: UnitSystem | None = None,
    ) -> "FreqPhaSeries":
        """按当前单位计算相位频谱。"""

        from .frequency_spectrum import FreqPhaSeries

        units = output_unit_system or get_default_unit_system()
        freqs, _, phase = self.calc_fft_with_phase(output_unit_system=units)
        return FreqPhaSeries.from_data(
            freqs,
            phase,
            units={"freq": units.frequency, "phase": units.phase},
            unit_system=units,
        )

    def calc_freqspec(
        self,
        *,
        output_unit_system: UnitSystem | None = None,
    ) -> "FreqSpec":
        """计算组合频谱对象。"""

        from .frequency_spectrum import FreqSpec

        units = output_unit_system or get_default_unit_system()
        freqs, mag, phase = self.calc_fft_with_phase(output_unit_system=units)
        return FreqSpec.from_data(
            freqs,
            amp=mag,
            pha=phase,
            units={
                "freq": units.frequency,
                "amp": self.value_unit,
                "phase": units.phase,
            },
            unit_system=units,
        )

    def calc_respspec(
        self,
        method: SDOFSolveMethod = SDOFSolveMethod.NIGAM_JENNINGS,
        *,
        calc_unit_system: UnitSystem | None = None,
        output_unit_system: UnitSystem | None = None,
        periods: np.ndarray | None = None,
    ) -> "RespSpec":
        """按显式单位规则由加速度计算响应谱。"""

        calc_units = calc_unit_system or get_default_unit_system()
        out_units = output_unit_system or get_default_unit_system()
        return respspec_from_accel(
            self.get_value(unit=calc_units.acceleration),
            self.dt,
            periods=periods,
            method=method,
            accel_unit=calc_units.acceleration,
            calc_unit_system=calc_units,
            output_unit_system=out_units,
        )

    def calc_respspec_bundle(
        self,
        method: SDOFSolveMethod = SDOFSolveMethod.NIGAM_JENNINGS,
        *,
        calc_unit_system: UnitSystem | None = None,
        output_unit_system: UnitSystem | None = None,
        periods: np.ndarray | None = None,
    ) -> "RespSpec":
        """计算组合响应谱对象。"""

        from .response_spectrum import RespSpec

        out = self.calc_respspec(
            method=method,
            calc_unit_system=calc_unit_system,
            output_unit_system=output_unit_system,
            periods=periods,
        )
        if not isinstance(out, pd.DataFrame):
            raise TypeError("calc_respspec did not return a pandas DataFrame")
        return RespSpec.from_pandas(
            out,
            unit_system=output_unit_system,
        )

    def _calc_respspec_component(
        self,
        component: str,
        method: SDOFSolveMethod = SDOFSolveMethod.NIGAM_JENNINGS,
        *,
        calc_unit_system: UnitSystem | None = None,
        output_unit_system: UnitSystem | None = None,
        periods: np.ndarray | None = None,
    ) -> "ResponseSpectrum":
        bundle = self.calc_respspec_bundle(
            method=method,
            calc_unit_system=calc_unit_system,
            output_unit_system=output_unit_system,
            periods=periods,
        )
        result = getattr(bundle, component, None)
        if result is None:
            raise ValueError(f"Response spectrum component {component!r} is unavailable.")
        return result

    def calc_respspec_sa(
        self,
        method: SDOFSolveMethod = SDOFSolveMethod.NIGAM_JENNINGS,
        *,
        calc_unit_system: UnitSystem | None = None,
        output_unit_system: UnitSystem | None = None,
        periods: np.ndarray | None = None,
    ) -> "SpecAccelSeries":
        """计算谱加速度分量。"""

        return self._calc_respspec_component(
            "sa",
            method=method,
            calc_unit_system=calc_unit_system,
            output_unit_system=output_unit_system,
            periods=periods,
        )

    def calc_respspec_sv(
        self,
        method: SDOFSolveMethod = SDOFSolveMethod.NIGAM_JENNINGS,
        *,
        calc_unit_system: UnitSystem | None = None,
        output_unit_system: UnitSystem | None = None,
        periods: np.ndarray | None = None,
    ) -> "SpecVelSeries":
        """计算谱速度分量。"""

        return self._calc_respspec_component(
            "sv",
            method=method,
            calc_unit_system=calc_unit_system,
            output_unit_system=output_unit_system,
            periods=periods,
        )

    def calc_respspec_sd(
        self,
        method: SDOFSolveMethod = SDOFSolveMethod.NIGAM_JENNINGS,
        *,
        calc_unit_system: UnitSystem | None = None,
        output_unit_system: UnitSystem | None = None,
        periods: np.ndarray | None = None,
    ) -> "SpecDispSeries":
        """计算谱位移分量。"""

        return self._calc_respspec_component(
            "sd",
            method=method,
            calc_unit_system=calc_unit_system,
            output_unit_system=output_unit_system,
            periods=periods,
        )

    def calc_respspec_psa(
        self,
        method: SDOFSolveMethod = SDOFSolveMethod.NIGAM_JENNINGS,
        *,
        calc_unit_system: UnitSystem | None = None,
        output_unit_system: UnitSystem | None = None,
        periods: np.ndarray | None = None,
    ) -> "PSpecAccelSeries":
        """计算伪谱加速度分量。"""

        return self._calc_respspec_component(
            "psa",
            method=method,
            calc_unit_system=calc_unit_system,
            output_unit_system=output_unit_system,
            periods=periods,
        )

    def calc_respspec_psv(
        self,
        method: SDOFSolveMethod = SDOFSolveMethod.NIGAM_JENNINGS,
        *,
        calc_unit_system: UnitSystem | None = None,
        output_unit_system: UnitSystem | None = None,
        periods: np.ndarray | None = None,
    ) -> "PSpecVelSeries":
        """计算伪谱速度分量。"""

        return self._calc_respspec_component(
            "psv",
            method=method,
            calc_unit_system=calc_unit_system,
            output_unit_system=output_unit_system,
            periods=periods,
        )

    def eval_zvl(
        self,
        *,
        freq_range: tuple[float, float] = (1.0, 80.0),
        weight_type: WeightType = WeightType.WK,
        time_windows: float = 1.0,
        calc_unit_system: UnitSystem | None = None,
        output_unit_system: UnitSystem | None = None,
    ) -> "ZVLEval":
        """根据加速度数据计算 Z 振级。"""

        calc_units = calc_unit_system or get_default_unit_system()
        result = zvl_from_accel(
            self.get_value(unit=calc_units.acceleration),
            self.dt,
            freq_range=freq_range,
            weight_type=weight_type,
            time_windows=time_windows,
            accel_unit=calc_units.acceleration,
            calc_unit_system=calc_units,
            output_unit_system=output_unit_system,
        )
        from .vibration_evaluation import ZVLEval

        return ZVLEval.from_data(
            zvl=result.zvl,
            aw=result.aw,
            units=result.units,
            unit_system=result.unit_system,
        )

    def eval_otovl(
        self,
        *,
        freq_range: tuple[float, float] = (1.0, 80.0),
        time_windows: float = 1.0,
        calc_unit_system: UnitSystem | None = None,
        output_unit_system: UnitSystem | None = None,
    ) -> "OTOVLEval":
        """根据加速度数据计算三分之一倍频程振级。"""

        calc_units = calc_unit_system or get_default_unit_system()
        result = otovl_from_accel(
            self.get_value(unit=calc_units.acceleration),
            self.dt,
            freq_range=freq_range,
            time_windows=time_windows,
            accel_unit=calc_units.acceleration,
            calc_unit_system=calc_units,
            output_unit_system=output_unit_system,
        )
        from .vibration_evaluation import OTOVLEval

        return OTOVLEval.from_data(
            freq=result.freq,
            comps=result.comps,
            env=result.env,
            units=result.units,
            unit_system=result.unit_system,
        )

    def eval_fpvdv(
        self,
        *,
        freq_range: tuple[float, float] = (1.0, 80.0),
        nsup: int = 1,
        calc_unit_system: UnitSystem | None = None,
        output_unit_system: UnitSystem | None = None,
    ) -> "FPVDVEval":
        """根据加速度数据计算 FPVDV。"""

        calc_units = calc_unit_system or get_default_unit_system()
        result = fpvdv_from_accel(
            self.get_value(unit=calc_units.acceleration),
            self.dt,
            freq_range=freq_range,
            nsup=nsup,
            accel_unit=calc_units.acceleration,
            calc_unit_system=calc_units,
            output_unit_system=output_unit_system,
        )
        from .vibration_evaluation import FPVDVEval

        return FPVDVEval.from_data(
            fpvdv=result.fpvdv,
            aw_time=result.aw_time,
            aw_value=result.aw_value,
            units=result.units,
            unit_system=result.unit_system,
        )

    def eval_fdmvl(
        self,
        *,
        freq_range: tuple[float, float] = (1.0, 80.0),
        calc_unit_system: UnitSystem | None = None,
        output_unit_system: UnitSystem | None = None,
    ) -> "FDMVLEval":
        """根据加速度数据计算 FDMVL。"""

        calc_units = calc_unit_system or get_default_unit_system()
        result = fdmvl_from_accel(
            self.get_value(unit=calc_units.acceleration),
            self.dt,
            freq_range=freq_range,
            accel_unit=calc_units.acceleration,
            calc_unit_system=calc_units,
            output_unit_system=output_unit_system,
        )
        from .vibration_evaluation import FDMVLEval

        return FDMVLEval.from_data(
            fdmvl=result.fdmvl,
            freq=result.freq,
            fdvls=result.fdvls,
            units=result.units,
            unit_system=result.unit_system,
        )


class VelSeries(TimeSeries):
    """速度时程。"""

    category: ClassVar[DataCategory] = DataCategory.TS_VEL

    @classmethod
    def _base_value_unit(cls) -> str:
        return "meter/second"

    @classmethod
    def _default_current_units(cls, unit_system: UnitSystem | None = None) -> dict[str, str]:
        units = unit_system or get_default_unit_system()
        return {"time": units.time, "value": units.velocity}

    def calc_disp(
        self,
        method: IntegMethod = IntegMethod.SCIPY_CUMTRAPZ,
        *,
        calc_unit_system: UnitSystem | None = None,
        output_unit: str | None = None,
        output_unit_system: UnitSystem | None = None,
        **options: Any,
    ) -> "DispSeries":
        """按固定基准单位规则将速度积分为位移。"""

        calc_units = calc_unit_system or get_default_unit_system()
        out_units = output_unit_system or get_default_unit_system()
        disp_array = Integration(
            y=self.get_value(unit=calc_units.velocity),
            dx=self.dt,
        ).integ1d(method=method, **options)
        target_value_unit = output_unit or out_units.displacement
        units = {"time": out_units.time, "value": target_value_unit}
        return DispSeries._from_base_data(
            convert_array(
                disp_array,
                from_unit=calc_units.displacement,
                to_unit=target_value_unit,
            ),
            time=self.get_axis(unit=out_units.time),
            units=units,
            unit_system=out_units,
        )

    def calc_accel(
        self,
        method: DiffMethod = DiffMethod.SELF_CENTRAL,
        *,
        calc_unit_system: UnitSystem | None = None,
        output_unit: str | None = None,
        output_unit_system: UnitSystem | None = None,
        **options: Any,
    ) -> AccelSeries:
        """按固定基准单位规则将速度微分为加速度。"""

        calc_units = calc_unit_system or get_default_unit_system()
        out_units = output_unit_system or get_default_unit_system()
        accel_array = Differentiation(
            y=self.get_value(unit=calc_units.velocity),
            dx=self.dt,
        ).diff1d(method=method, **options)
        target_value_unit = output_unit or out_units.acceleration
        units = {"time": out_units.time, "value": target_value_unit}
        return AccelSeries._from_base_data(
            convert_array(
                accel_array,
                from_unit=calc_units.acceleration,
                to_unit=target_value_unit,
            ),
            time=self.get_axis(unit=out_units.time),
            units=units,
            unit_system=out_units,
        )


class ForceSeries(TimeSeries):
    """力时程。"""

    category: ClassVar[DataCategory] = DataCategory.TS_FORCE

    @classmethod
    def _base_value_unit(cls) -> str:
        return "newton"

    @classmethod
    def _default_current_units(cls, unit_system: UnitSystem | None = None) -> dict[str, str]:
        units = unit_system or get_default_unit_system()
        return {"time": units.time, "value": units.force}


class DispSeries(TimeSeries):
    """位移时程。"""

    category: ClassVar[DataCategory] = DataCategory.TS_DISP

    @classmethod
    def _base_value_unit(cls) -> str:
        return "meter"

    @classmethod
    def _default_current_units(cls, unit_system: UnitSystem | None = None) -> dict[str, str]:
        units = unit_system or get_default_unit_system()
        return {"time": units.time, "value": units.displacement}

    def calc_vel(
        self,
        method: DiffMethod = DiffMethod.SELF_CENTRAL,
        *,
        calc_unit_system: UnitSystem | None = None,
        output_unit: str | None = None,
        output_unit_system: UnitSystem | None = None,
        **options: Any,
    ) -> VelSeries:
        """按固定基准单位规则将位移微分为速度。"""

        calc_units = calc_unit_system or get_default_unit_system()
        out_units = output_unit_system or get_default_unit_system()
        vel_array = Differentiation(
            y=self.get_value(unit=calc_units.displacement),
            dx=self.dt,
        ).diff1d(method=method, **options)
        target_value_unit = output_unit or out_units.velocity
        units = {"time": out_units.time, "value": target_value_unit}
        return VelSeries._from_base_data(
            convert_array(
                vel_array,
                from_unit=calc_units.velocity,
                to_unit=target_value_unit,
            ),
            time=self.get_axis(unit=out_units.time),
            units=units,
            unit_system=out_units,
        )

    def calc_accel(
        self,
        method: DiffMethod = DiffMethod.SELF_CENTRAL,
        *,
        calc_unit_system: UnitSystem | None = None,
        output_unit: str | None = None,
        output_unit_system: UnitSystem | None = None,
        **options: Any,
    ) -> AccelSeries:
        """将位移二次微分为加速度。"""

        return self.calc_vel(
            method=method,
            calc_unit_system=calc_unit_system,
            output_unit_system=output_unit_system,
            **options,
        ).calc_accel(
            method=method,
            calc_unit_system=calc_unit_system,
            output_unit=output_unit,
            output_unit_system=output_unit_system,
            **options,
        )
