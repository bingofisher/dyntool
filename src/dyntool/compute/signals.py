"""时程信号处理算法。"""

from __future__ import annotations

from enum import StrEnum

import numpy as np
from scipy import integrate
from scipy.interpolate import interp1d
from scipy.signal import butter, detrend, filtfilt

from .units import convert_array

ArrayLike = np.ndarray | list[float]


class BaselineMethod(StrEnum):
    """基线修正方法枚举。"""

    LINEAR = "linear"
    POLYNOMIAL = "polynomial"


def baseline_correct(
    value: ArrayLike,
    *,
    method: BaselineMethod | str = BaselineMethod.LINEAR,
    order: int = 1,
) -> np.ndarray:
    """对序列做基线修正，返回同形状数组。"""
    arr = np.asarray(value, dtype=float)

    if arr.ndim == 1:
        arr2d = arr[:, np.newaxis]
        squeeze = True
    else:
        arr2d = arr
        squeeze = False

    if arr2d.shape[0] < 2:
        raise ValueError("序列长度不足，无法进行基线修正")

    m = BaselineMethod(method)
    if m == BaselineMethod.LINEAR:
        corrected = np.column_stack([detrend(arr2d[:, i], type="linear") for i in range(arr2d.shape[1])])
    elif m == BaselineMethod.POLYNOMIAL:
        if order < 0:
            raise ValueError("order 必须为非负整数")
        x = np.arange(arr2d.shape[0], dtype=float)
        cols = []
        for i in range(arr2d.shape[1]):
            coef = np.polyfit(x, arr2d[:, i], order)
            trend = np.polyval(coef, x)
            cols.append(arr2d[:, i] - trend)
        corrected = np.column_stack(cols)
    else:
        raise ValueError(f"不支持的基线修正方法: {method}")

    if squeeze:
        return corrected[:, 0]
    return corrected


class FilterKind(StrEnum):
    """滤波器类型枚举。"""

    HIGHPASS = "highpass"
    LOWPASS = "lowpass"
    BANDPASS = "bandpass"


def filter_signal(
    value: ArrayLike,
    *,
    fs: float,
    kind: FilterKind | str,
    freq: float,
    f_high: float | None = None,
    order: int = 4,
) -> np.ndarray:
    """滤波并返回同形状数组。"""
    arr = np.asarray(value, dtype=float)
    if arr.ndim == 1:
        arr2d = arr[:, np.newaxis]
        squeeze = True
    else:
        arr2d = arr
        squeeze = False

    if arr2d.shape[0] < 3:
        raise ValueError("序列长度不足，无法滤波")
    if fs <= 0:
        raise ValueError("fs 必须为正数")
    if order < 1:
        raise ValueError("order 必须为正整数")

    nyq = fs * 0.5
    filt_kind = FilterKind(kind)

    if filt_kind == FilterKind.BANDPASS:
        if f_high is None:
            raise ValueError("bandpass 需要提供 f_high")
        low = float(freq) / nyq
        high = float(f_high) / nyq
        if not (0 < low < high < 1):
            raise ValueError("带通频率需满足 0 < freq < f_high < fs/2")
        b, a = butter(order, [low, high], btype="bandpass")
    elif filt_kind == FilterKind.HIGHPASS:
        wn = float(freq) / nyq
        if not (0 < wn < 1):
            raise ValueError("高通频率需满足 0 < freq < fs/2")
        b, a = butter(order, wn, btype="highpass")
    else:
        wn = float(freq) / nyq
        if not (0 < wn < 1):
            raise ValueError("低通频率需满足 0 < freq < fs/2")
        b, a = butter(order, wn, btype="lowpass")

    filtered = np.column_stack([filtfilt(b, a, arr2d[:, i], axis=0) for i in range(arr2d.shape[1])])
    if squeeze:
        return filtered[:, 0]
    return filtered


class IntegMethod(StrEnum):
    """一维积分方法枚举。"""

    SCIPY_CUMTRAPZ = "scipy-cumtrapz"
    SELF_CUMTRAPZ = "self-cumtrapz"


class Integration:
    """一维积分封装。"""

    def __init__(
        self,
        y: ArrayLike,
        *,
        x: ArrayLike | None = None,
        dx: float | None = None,
    ) -> None:
        self._init_data(y=y, x=x, dx=dx)

    def _init_data(
        self,
        *,
        y: ArrayLike,
        x: ArrayLike | None = None,
        dx: float | None = None,
    ) -> None:
        self.y = np.asarray(y)
        self.x = np.asarray(x) if x is not None else None
        self.dx = float(dx) if dx is not None else None
        if x is None and dx is None:
            raise ValueError("积分需要设置 `x` 或 `dx`")
        if x is not None and dx is not None:
            raise ValueError(f"`x` 和 `dx` 不能同时设置，当前 x={x}, dx={dx}")

        if x is not None:
            assert self.x is not None
            if self.x.shape != self.y.shape:
                raise ValueError(f"x 和 y 长度不一致: len(x)={len(self.x)}, len(y)={len(self.y)}")
            self.dx = None
        else:
            assert self.dx is not None
            if self.dx <= 0:
                raise ValueError("`dx` 必须为正数")
            n = len(self.y)
            self.x = np.arange(0, n * self.dx, self.dx)
            if len(self.x) != n:
                self.x = np.linspace(0, (n - 1) * self.dx, n)

    def _scipy_cumtrapz(self, y: np.ndarray, x: np.ndarray, initial: float = 0.0) -> np.ndarray:
        integdata = integrate.cumulative_trapezoid(y, x, initial=initial)
        return np.asarray(integdata)

    def _self_cumtrapz(self, y: np.ndarray, x: np.ndarray) -> np.ndarray:
        y = np.insert(np.array(y), 0, 0)
        x = np.insert(np.array(x), 0, 0)
        data = 0.5 * (np.diff(y) + y[:-1] * 2) * np.diff(x)
        return data.cumsum()

    def integ1d(
        self,
        method: IntegMethod | str = IntegMethod.SELF_CUMTRAPZ,
        **kwargs: object,
    ) -> np.ndarray:
        """执行一维积分。"""
        assert self.x is not None
        match IntegMethod(method):
            case IntegMethod.SCIPY_CUMTRAPZ:
                data = self._scipy_cumtrapz(self.y, self.x, **kwargs)
            case IntegMethod.SELF_CUMTRAPZ:
                data = self._self_cumtrapz(self.y, self.x)
            case _:
                raise ValueError(f"积分方法不支持: {method}, 可选方法有 {[m.value for m in IntegMethod]}")
        return np.asarray(data)


class DiffMethod(StrEnum):
    """一维差分方法枚举。"""

    SELF_CENTRAL = "self-central"


class Differentiation:
    """一维微分封装。"""

    def __init__(
        self,
        y: ArrayLike,
        *,
        x: ArrayLike | None = None,
        dx: float | None = None,
    ) -> None:
        self._init_data(y=y, x=x, dx=dx)

    def _init_data(
        self,
        *,
        y: ArrayLike,
        x: ArrayLike | None = None,
        dx: float | None = None,
    ) -> None:
        self.y = np.asarray(y)
        self.x = np.asarray(x) if x is not None else None
        self.dx = float(dx) if dx is not None else None
        if x is None and dx is None:
            raise ValueError("积分需要设置 `x` 或 `dx`")
        if x is not None and dx is not None:
            raise ValueError(f"`x` 和 `dx` 不能同时设置，当前 x={x}, dx={dx}")

        if x is not None:
            assert self.x is not None
            if self.x.shape != self.y.shape:
                raise ValueError(f"x 和 y 长度不一致: len(x)={len(self.x)}, len(y)={len(self.y)}")
            self.dx = None
        else:
            assert self.dx is not None
            if self.dx <= 0:
                raise ValueError("`dx` 必须为正数")
            n = len(self.y)
            self.x = np.arange(0, n * self.dx, self.dx)
            if len(self.x) != n:
                self.x = np.linspace(0, (n - 1) * self.dx, n)

    def __self_central_forward(self, y: float, y_next: float, dx: float) -> float:
        return (y_next - y) / dx

    def __self_central_backward(self, y_last: float, y: float, dx: float) -> float:
        return (y - y_last) / dx

    def __self_central_central(
        self,
        y_last: float,
        y_next: float,
        step1: float,
        step2: float,
    ) -> float:
        return (y_next - y_last) / (step1 + step2)

    def _self_central(self, y: np.ndarray, x: np.ndarray) -> np.ndarray:
        data = []
        y0, y1 = y[0], y[1]
        dx0 = float(np.diff(x[:2])[0])
        data.append(self.__self_central_forward(float(y0), float(y1), dx0))
        for y1, y3, dx21, dx23 in zip(y[:-2], y[2:], np.diff(x)[:-1], np.diff(x)[1:]):
            data.append(self.__self_central_central(float(y1), float(y3), float(dx21), float(dx23)))
        y_n1, y_n = y[-2], y[-1]
        dx_n = float(np.diff(x[-2:])[0])
        data.append(self.__self_central_backward(float(y_n1), float(y_n), dx_n))
        return np.asarray(data)

    def diff1d(
        self,
        method: DiffMethod | str = DiffMethod.SELF_CENTRAL,
        **kwargs: object,
    ) -> np.ndarray:
        """执行一维微分。"""
        del kwargs
        assert self.x is not None
        match DiffMethod(method):
            case DiffMethod.SELF_CENTRAL:
                data = self._self_central(self.y, self.x)
            case _:
                raise ValueError(f"微分方法不支持: {method}")
        return np.asarray(data)


class InterpMethod(StrEnum):
    """一维插值方法枚举。"""

    SCIPY_INTERP1D = "scipy_interp1d"


class Interpolation:
    """一维插值封装。"""

    def __init__(self, y: ArrayLike, *, num: int) -> None:
        self._init_data(y=y, num=num)

    def _init_data(self, *, y: ArrayLike, num: int) -> None:
        self.y = np.asarray(y)
        self.num = int(num)

    def _scipy_interp1d(self, y: np.ndarray, *, num: int, **kwargs: object) -> np.ndarray:
        x_base = np.linspace(0, len(y), len(y))
        x_interp = np.linspace(0, len(y), len(y) * (num + 1) - num)
        return np.array(interp1d(x_base, y, **kwargs)(x_interp))

    def interp1d(
        self,
        method: InterpMethod | str = InterpMethod.SCIPY_INTERP1D,
        **kwargs: object,
    ) -> np.ndarray:
        """执行一维插值。"""
        match InterpMethod(method):
            case InterpMethod.SCIPY_INTERP1D:
                data = self._scipy_interp1d(self.y, num=self.num, **kwargs)
            case _:
                raise ValueError(f"插值方法不支持: {method}")
        return np.asarray(data)


def truncate(
    axis: ArrayLike,
    value: ArrayLike,
    start: float,
    end: float,
) -> tuple[np.ndarray, np.ndarray]:
    """按轴值区间截断数据，返回 ``(axis_new, value_new)``。"""
    axis_arr = np.asarray(axis, dtype=float).flatten()
    value_arr = np.asarray(value)

    if axis_arr.ndim != 1:
        raise ValueError("axis 必须为一维数组")
    if len(axis_arr) == 0:
        raise ValueError("axis 不能为空")
    if start >= end:
        raise ValueError("start 必须小于 end")
    if value_arr.shape[0] != axis_arr.shape[0]:
        raise ValueError("value 首维长度必须与 axis 长度一致")

    mask = (axis_arr >= float(start)) & (axis_arr <= float(end))
    if not np.any(mask):
        raise ValueError("截断区间内没有数据点")
    return axis_arr[mask], value_arr[mask]


def fft_with_phase(
    value: ArrayLike,
    *,
    dt: float,
    value_unit: str = "dimensionless",
    output_value_unit: str | None = None,
    output_frequency_unit: str = "hertz",
    output_phase_unit: str = "radian",
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """计算一维时程的 FFT 频率、幅值和相位。"""
    arr = np.asarray(value, dtype=float)
    if arr.ndim != 1:
        raise ValueError("FFT 输入必须为一维序列")
    if arr.size < 2:
        raise ValueError("FFT 至少需要两个采样点")
    if dt <= 0:
        raise ValueError("dt 必须为正数")

    fs = 1.0 / dt
    n = arr.size
    data = detrend(arr, type="linear")
    window = np.hanning(n)
    fft_results = np.fft.fft(data * window)
    freqs = np.fft.fftfreq(n, d=1.0 / fs)
    half_n = n // 2

    freqs_pos = convert_array(
        freqs[:half_n].copy(),
        from_unit="hertz",
        to_unit=output_frequency_unit,
    )
    mag_base = np.abs(fft_results[:half_n]) * (2.0 / n)
    if mag_base.size > 0:
        mag_base[0] = mag_base[0] / 2.0
    mag = convert_array(
        mag_base,
        from_unit=value_unit,
        to_unit=output_value_unit or value_unit,
    )
    phase = convert_array(
        np.angle(fft_results[:half_n]),
        from_unit="radian",
        to_unit=output_phase_unit,
    )
    return freqs_pos, mag, phase


__all__ = [
    "truncate",
    "baseline_correct",
    "filter_signal",
    "BaselineMethod",
    "FilterKind",
    "IntegMethod",
    "Integration",
    "DiffMethod",
    "Differentiation",
    "InterpMethod",
    "Interpolation",
    "fft_with_phase",
]
