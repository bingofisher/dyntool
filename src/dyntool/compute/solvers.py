"""数值求解器。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import StrEnum

import numpy as np
import pandas as pd
from scipy.signal import csd, welch

ArrayLike = np.ndarray | list[float]


def _load_manifest() -> dict[str, str]:
    from .solver_support import load_manifest

    return load_manifest()


def _load_resource_csv(key: str) -> pd.DataFrame:
    from .solver_support import load_resource_csv as _load_resource_csv_impl

    return _load_resource_csv_impl(key)


def _center_freqs(freq_range: tuple[float, float]) -> np.ndarray:
    from .solver_support import center_freqs as _center_freqs_impl

    return _center_freqs_impl(freq_range)


def _read_weight_from_df(
    center_freqs: np.ndarray,
    df: pd.DataFrame,
    weight_type: "WeightType",
) -> np.ndarray:
    from .solver_support import read_weight_from_df as _read_weight_from_df_impl

    return _read_weight_from_df_impl(center_freqs, df, weight_type.value.capitalize())


def _read_weight_z_from_df(center_freqs: np.ndarray, df: pd.DataFrame) -> np.ndarray:
    from .solver_support import read_weight_z_from_df as _read_weight_z_from_df_impl

    return _read_weight_z_from_df_impl(center_freqs, df)


class SolverBase(ABC):
    """求解器抽象基类。"""

    @abstractmethod
    def solve(self):
        """执行求解流程并返回求解结果。"""
        raise NotImplementedError


class WeightType(StrEnum):
    """频率计权类型枚举。

    枚举值说明:
        - ``WK``/``WD``/``WF``/``WC``/``WE``/``WJ``: 对应不同人体振动评价标准中的
          计权曲线，会直接影响加权加速度和后续振动评价结果。
    """

    WK = "wk"
    WD = "wd"
    WF = "wf"
    WC = "wc"
    WE = "we"
    WJ = "wj"


class LinearSequence:
    """线性序列工具类：用于生成、验证等差（线性）序列。"""

    ATOL: float = 1e-8
    RTOL: float = 1e-5

    def __init__(
        self,
        data: ArrayLike,
        *,
        atol: float | None = None,
        rtol: float | None = None,
    ) -> None:
        self._data = self.load_data(data)
        self.atol = atol if atol is not None else self.ATOL
        self.rtol = rtol if rtol is not None else self.RTOL

    @staticmethod
    def load_data(data: ArrayLike) -> np.ndarray:
        """将输入序列标准化为一维浮点数组。"""
        try:
            arr = np.asarray(data, dtype=float)
        except (ValueError, TypeError) as e:
            raise ValueError("序列必须为数值类型") from e
        if arr.ndim != 1:
            raise ValueError("输入数据必须是一维序列")
        return arr

    def check_uniform(self) -> bool:
        """判断当前序列是否为等间距线性序列。"""
        n = len(self._data)
        if n < 2:
            return True
        diffs = np.diff(self._data)
        return np.allclose(diffs, diffs[0], atol=self.atol, rtol=self.rtol)

    @classmethod
    def is_uniform(
        cls,
        sequence: ArrayLike,
        atol: float | None = None,
        rtol: float | None = None,
    ) -> bool:
        """判断任意输入序列是否满足等间距线性条件。"""
        return cls(sequence, atol=atol, rtol=rtol).check_uniform()

    @classmethod
    def generate(
        cls,
        start: float,
        end: float,
        *,
        interval: float | None = None,
        num: int | None = None,
        endpoint: bool = True,
        **kwargs: object,
    ) -> np.ndarray:
        """按起止值与间隔或点数生成线性序列。"""
        if start > end:
            raise ValueError(f"起始值 ({start}) 不能大于结束值 ({end})")
        if start == end:
            return np.array([start])
        if (interval is None) == (num is None):
            raise ValueError("必须且只能指定 'interval' 或 'num' 之一")

        if interval is not None:
            if interval <= 0:
                raise ValueError("'interval' 必须为正数")
            total_span = end - start
            n_intervals = total_span / interval
            n_rounded = round(n_intervals)
            if abs(n_intervals - n_rounded) > 1e-10:
                raise ValueError(f"interval={interval} 无法整除区间 [{start}, {end}]（跨度={total_span}）")
            num_computed = int(n_rounded) + 1
            return np.linspace(start, end, num=num_computed, endpoint=True, **kwargs)

        assert num is not None
        if num < 1:
            raise ValueError("'num' 必须 ≥ 1")
        return np.linspace(start, end, num=num, endpoint=endpoint, **kwargs)

    @classmethod
    def generate_time(
        cls,
        *,
        dt: float | None = None,
        num: int | None = None,
        duration: float | None = None,
        endpoint: bool = True,
        **kwargs: object,
    ) -> np.ndarray:
        """根据 ``dt``、``num``、``duration`` 中任意两项生成时间轴。"""
        args = {"dt": dt, "num": num, "duration": duration}
        provided = sum(v is not None for v in args.values())
        if provided != 2:
            raise ValueError(f"必须且只能提供两个参数，当前提供: {args}")
        if dt is not None and dt <= 0:
            raise ValueError("'dt' 必须为正数")
        if num is not None and num < 1:
            raise ValueError("'num' 必须 ≥ 1")
        if duration is not None and duration < 0:
            raise ValueError("'duration' 不能为负数")
        if duration == 0.0:
            return np.array([0.0])

        if dt is None:
            assert duration is not None
            return cls.generate(0.0, duration, num=num, endpoint=endpoint, **kwargs)
        if num is None:
            assert duration is not None
            return cls.generate(0.0, duration, interval=dt, **kwargs)
        if duration is None:
            end = dt * (num - 1) if endpoint else dt * num
            return cls.generate(0.0, end, num=num, endpoint=endpoint, **kwargs)
        raise RuntimeError("逻辑错误：参数推导失败")


class SDOFSolveMethod(StrEnum):
    """单自由度体系求解方法枚举。

    枚举值说明:
        - ``NIGAM_JENNINGS``: 使用 Nigam-Jennings 递推法求解时程响应，
          会影响响应谱与加速度/速度/位移结果。
    """

    NIGAM_JENNINGS = "nigam-jennings"


class SDOFSolver(SolverBase):
    """单自由度体系运动方程求解器。"""

    G: float = 9.81

    def __init__(
        self,
        *,
        dt: float,
        ag: ArrayLike | None = None,
        p: ArrayLike | None = None,
        m: float = 1,
        xi: float = 0.05,
        T: float = 1,
    ) -> None:
        self.build_sdof(m, xi, T)
        self.set_ag(dt=dt, ag=ag, p=p)

    def build_sdof(self, m: float, xi: float, T: float) -> None:
        """根据质量、阻尼比和周期构建单自由度体系参数。"""
        self.m = m
        self.xi = xi
        self.T = T
        self.wn = 2 * np.pi / T
        self.wd = self.wn * np.sqrt(1 - xi**2)
        self.k = m * self.wn**2
        self.c = 2 * m * self.wn * xi

    def set_ag(
        self,
        *,
        dt: float,
        ag: ArrayLike | None = None,
        p: ArrayLike | None = None,
    ) -> None:
        """设置外荷载时程，支持地震加速度或等效外力输入。"""
        self.dt = np.float64(dt)
        match (ag, p):
            case (None, None):
                raise ValueError("需要输入外荷载加速度`ag`或外荷载`p`")
            case (_, None):
                self.ag = np.asarray(ag)
                self.p = -self.ag * self.m
            case (None, _):
                self.p = np.asarray(p)
                self.ag = -self.p / self.m
            case (_, _):
                raise ValueError("`ag`和`p`不能同时输入")

    def _nigam_jennings(self) -> np.ndarray:
        xi = self.xi
        wn = self.wn
        wd = self.wd
        ag = self.ag
        dt = self.dt

        a11 = xi / np.sqrt(1 - xi**2) * np.sin(wd * dt) + np.cos(wd * dt)
        a11 *= np.exp(-xi * wn * dt)
        a12 = np.exp(-xi * wn * dt) / wd * np.sin(wd * dt)
        a21 = -wn / np.sqrt(1 - xi**2) * np.exp(-xi * wn * dt) * np.sin(wd * dt)

        a22 = np.cos(wd * dt) - xi / np.sqrt(1 - xi**2) * np.sin(wd * dt)
        a22 *= np.exp(-xi * wn * dt)

        b11 = ((2 * xi**2 - 1) / wn**2 / dt + xi / wn) * np.sin(wd * dt) / wd
        b11 += (2 * xi / wn**3 / dt + 1 / wn**2) * np.cos(wd * dt)
        b11 *= np.exp(-xi * wn * dt)
        b11 += -2 * xi / wn**3 / dt

        b12 = ((2 * xi**2 - 1) / wn**2 / dt) * np.sin(wd * dt) / wd
        b12 += 2 * xi / wn**3 / dt * np.cos(wd * dt)
        b12 *= -np.exp(-xi * wn * dt)
        b12 += -1 / wn**2 + 2 * xi / wn**3 / dt

        b21 = wn / np.sqrt(1 - xi**2) + xi / dt / np.sqrt(1 - xi**2)
        b21 *= np.sin(wd * dt)
        b21 += 1 / dt * np.cos(wd * dt)
        b21 *= np.exp(-xi * wn * dt)
        b21 += -1 / dt
        b21 *= -1 / wn**2

        b22 = xi / np.sqrt(1 - xi**2) * np.sin(wd * dt) + np.cos(wd * dt)
        b22 = 1 - np.exp(-xi * wn * dt) * b22
        b22 *= -1 / wn**2 / dt

        a = [-ag[0]]
        v = [0.0]
        d = [0.0]

        for i in range(len(ag) - 1):
            di = a11 * d[i] + a12 * v[i] + b11 * ag[i] + b12 * ag[i + 1]
            vi = a21 * d[i] + a22 * v[i] + b21 * ag[i] + b22 * ag[i + 1]
            ai = -ag[i + 1] - wn**2 * di - 2 * xi * wn * vi
            d.append(di)
            v.append(vi)
            a.append(ai + ag[i + 1])

        return np.stack((a, v, d))

    def solve(
        self,
        method: SDOFSolveMethod | str = SDOFSolveMethod.NIGAM_JENNINGS,
        **kwargs: dict,
    ) -> dict[str, np.ndarray]:
        """求解单自由度体系的加速度、速度和位移响应。"""
        del kwargs
        if not hasattr(self, "m"):
            raise ValueError("请先用 `build_sdof()` 构建单自由度体系")
        if not hasattr(self, "ag"):
            raise ValueError("请先用 `set_ag()` 设置外荷载加速度或外荷载")
        match SDOFSolveMethod(method):
            case SDOFSolveMethod.NIGAM_JENNINGS:
                avd = self._nigam_jennings()
            case _:
                raise ValueError(f"求解方法不支持: {method}")
        self.accel, self.vel, self.disp = avd
        return {"accel": self.accel, "vel": self.vel, "disp": self.disp}

    @classmethod
    def solve_from_accel(
        cls,
        periods: np.ndarray,
        accel: np.ndarray,
        accel_dt: float,
        method: SDOFSolveMethod | str = SDOFSolveMethod.NIGAM_JENNINGS,
        **kwargs: dict,
    ) -> pd.DataFrame:
        """对多个周期批量求解响应谱相关结果。"""
        periods = np.asarray(periods, dtype=float)
        if np.any(periods <= 0):
            raise ValueError("周期必须为正数")
        periods = np.sort(np.unique(periods))

        df = pd.DataFrame(
            index=range(len(periods)),
            columns=(
                "periods (s)",
                "psa (m/s^2)",
                "psv (m/s)",
                "sd (m)",
                "sv (m/s)",
                "sa (m/s^2)",
            ),
        )
        for i, Ti in enumerate(periods):
            sdof = cls(T=Ti, dt=accel_dt, ag=accel)
            data = sdof.solve(method=method, **kwargs)
            a, v, d = data["accel"], data["vel"], data["disp"]
            sa = np.max(np.abs(a))
            sv = np.max(np.abs(v))
            sd = np.max(np.abs(d))
            psv = sd * sdof.wn
            psa = sd * sdof.wn**2
            df.loc[i, :] = Ti, psa, psv, sd, sv, sa
        return df.astype(float)


class TransferSolver(SolverBase):
    """传递函数求解器。"""

    def __init__(
        self,
        input_accel: ArrayLike,
        output_accel: ArrayLike,
        *,
        fs: int = 500,
        nperseg: int = 256,
        noverlap: int = 128,
        nfft: int = 512,
        window: str = "hann",
    ) -> None:
        input_arr = np.asarray(input_accel)
        output_arr = np.asarray(output_accel)
        if input_arr.ndim != 1:
            raise ValueError("'input_accel' 不是 1 维列表")
        if output_arr.ndim != 1:
            raise ValueError("'output_accel' 不是 1 维列表")
        if len(input_arr) != len(output_arr):
            raise ValueError("'input_accel' 和 'output_accel' 长度不一致")
        self.input_accel = input_arr
        self.output_accel = output_arr
        self.fs = fs
        self.nperseg = nperseg
        self.noverlap = noverlap
        self.nfft = nfft
        self.window = window
        self.frequencies: np.ndarray | None = None
        self.transfer_function: np.ndarray | None = None

    def solve(self) -> tuple[np.ndarray, np.ndarray]:
        """计算输入与输出加速度之间的传递函数。"""
        f, Pxy = csd(
            self.output_accel,
            self.input_accel,
            fs=self.fs,
            window=self.window,
            nperseg=self.nperseg,
            noverlap=self.noverlap,
            nfft=self.nfft,
            scaling="density",
            axis=0,
        )
        _, Pxx = welch(
            self.input_accel,
            fs=self.fs,
            window=self.window,
            nperseg=self.nperseg,
            noverlap=self.noverlap,
            nfft=self.nfft,
            scaling="density",
            axis=0,
        )
        H = Pxy / Pxx
        self.frequencies = f
        self.transfer_function = H
        return self.frequencies, self.transfer_function


class ZVibLevelSolver(SolverBase):
    """Z 振级求解器。"""

    def __init__(
        self,
        accel: ArrayLike,
        *,
        fs: int = 500,
        freq_range: tuple[float, float] = (1.0, 80.0),
        weight_type: WeightType = WeightType.WK,
        time_windows: float = 1.0,
    ) -> None:
        accel_arr = np.asarray(accel)
        if accel_arr.ndim != 1:
            raise ValueError("'accel' 不是 1 维列表")
        self.accel = accel_arr
        self.fs = fs
        self.freq_range = freq_range
        self.weight_type = weight_type
        self.time_windows = time_windows if time_windows != -1 else len(accel_arr) / fs

        self.a0 = 1e-6
        self.octave = 1 / 3
        self.overlap = 3 / 4
        self.center_freqs = _center_freqs(self.freq_range)
        weight_df = _load_resource_csv("octave_weight")
        self.weight = _read_weight_from_df(self.center_freqs, weight_df, self.weight_type)
        self.zvl: float | None = None
        self.aw: float | None = None

    def __calculate_lower(self, center: float) -> float:
        return center / 2 ** (self.octave / 2)

    def __calculate_upper(self, center: float) -> float:
        return center * 2 ** (self.octave / 2)

    def __get_min_nfft(self, num: int) -> int:
        return int(np.around(np.power(2, np.ceil(np.log2(num)))))

    @property
    def bands(self) -> pd.DataFrame:
        """返回 Z 振级计算使用的中心频率及频带边界表。"""
        df = pd.DataFrame(self.center_freqs, columns=["中心频率 (Hz)"])
        df["下边界频率 (Hz)"] = df["中心频率 (Hz)"].apply(self.__calculate_lower)
        df["上边界频率 (Hz)"] = df["中心频率 (Hz)"].apply(self.__calculate_upper)
        return df

    def solve(self) -> tuple[float, float]:
        """计算 Z 振级与加权加速度结果。"""
        accel = self.accel
        fs = self.fs
        center_freqs = self.center_freqs
        overlap = self.overlap
        window_t = self.time_windows

        window_n = int(np.around(window_t * fs))
        window_nfft = self.__get_min_nfft(window_n)
        data_len = len(accel)
        step = int(round(window_n * (1 - overlap)))
        aw = 0.0
        vls = np.zeros_like(center_freqs)

        for idx in range(0, int(data_len - window_n + 1), step):
            window = accel[idx : idx + window_n]
            window = np.concatenate([window, np.zeros(window_nfft - window_n)])
            window_fft = np.fft.fft(window)
            ai = np.zeros_like(center_freqs)
            for i, center_freq in enumerate(center_freqs):
                subwindow_fft = window_fft.copy()
                lower_freq = self.__calculate_lower(float(center_freq))
                upper_freq = self.__calculate_upper(float(center_freq))
                drop_left = int(np.around(lower_freq * window_nfft / fs))
                drop_right = int(np.around(upper_freq * window_nfft / fs + 1))
                subwindow_fft[:drop_left] = 0.0
                subwindow_fft[-drop_left:] = 0.0
                subwindow_fft[drop_right:-drop_right] = 0.0
                window_acc = np.fft.ifft(subwindow_fft)[:window_n].real
                powered = np.sum(np.power(window_acc[1:-1], 2))
                powered += 0.5 * np.power(window_acc[0], 2)
                powered += 0.5 * np.power(window_acc[-1], 2)
                ai[i] = np.sqrt(powered / len(window_acc))
                safe_ai = max(ai[i], np.finfo(float).tiny)
                vl = 20 * np.log10(safe_ai / self.a0)
                vls[i] = max(vl, vls[i])
            aw = np.max((aw, np.sqrt(np.sum((self.weight * ai) ** 2))))
        safe_aw = max(aw, np.finfo(float).tiny)
        self.zvl = 20 * np.log10(safe_aw / self.a0)
        self.aw = aw
        return self.zvl, self.aw


class OneThirdOctaveVibLevelSolver(SolverBase):
    """1/3 倍频程分频振级求解器。"""

    def __init__(
        self,
        accel: ArrayLike,
        *,
        fs: int = 500,
        freq_range: tuple[float, float] = (1.0, 80.0),
        time_windows: float = 1.0,
    ) -> None:
        accel_arr = np.asarray(accel)
        if accel_arr.ndim != 1:
            raise ValueError("'accel' 不是 1 维列表")
        self.accel = accel_arr
        self.fs = fs
        self.freq_range = freq_range
        self.time_windows = time_windows if time_windows != -1 else accel_arr.shape[0] / fs

        self.a0 = 1e-6
        self.octave = 1 / 3
        self.overlap = 3 / 4
        self.center_freqs = _center_freqs(self.freq_range)
        self.otovl_env: np.ndarray | None = None
        self.otovl_data: np.ndarray | None = None

    def __calculate_lower(self, center: float) -> float:
        return center / 2 ** (self.octave / 2)

    def __calculate_upper(self, center: float) -> float:
        return center * 2 ** (self.octave / 2)

    def __get_min_nfft(self, num: int) -> int:
        return int(np.around(np.power(2, np.ceil(np.log2(num)))))

    @property
    def bands(self) -> pd.DataFrame:
        """返回 1/3 倍频程振级计算使用的中心频率及频带边界表。"""
        df = pd.DataFrame(self.center_freqs, columns=["中心频率 (Hz)"])
        df["下边界频率 (Hz)"] = df["中心频率 (Hz)"].apply(self.__calculate_lower)
        df["上边界频率 (Hz)"] = df["中心频率 (Hz)"].apply(self.__calculate_upper)
        return df

    def solve(self) -> tuple[np.ndarray, np.ndarray]:
        """计算 1/3 倍频程包络和分窗振级矩阵。"""
        accel = self.accel
        fs = self.fs
        center_freqs = self.center_freqs
        overlap = self.overlap
        window_t = self.time_windows

        window_n = int(np.around(window_t * fs))
        window_nfft = self.__get_min_nfft(window_n)
        data_len = len(accel)
        step = int(round(window_n * (1 - overlap)))
        otovl_data = []

        for idx in range(0, int(data_len - window_n + 1), step):
            window = accel[idx : idx + window_n]
            window = np.concatenate([window, np.zeros(window_nfft - window_n)])
            window_fft = np.fft.fft(window)
            ai = np.zeros_like(center_freqs)
            for i, center_freq in enumerate(center_freqs):
                subwindow_fft = window_fft.copy()
                lower_freq = self.__calculate_lower(float(center_freq))
                upper_freq = self.__calculate_upper(float(center_freq))
                drop_left = int(np.around(lower_freq * window_nfft / fs))
                drop_right = int(np.around(upper_freq * window_nfft / fs + 1))
                subwindow_fft[:drop_left] = 0.0
                subwindow_fft[-drop_left:] = 0.0
                subwindow_fft[drop_right:-drop_right] = 0.0
                window_acc = np.fft.ifft(subwindow_fft)[:window_n].real
                powered = np.sum(np.power(window_acc[1:-1], 2))
                powered += 0.5 * np.power(window_acc[0], 2)
                powered += 0.5 * np.power(window_acc[-1], 2)
                ai[i] = np.sqrt(powered / len(window_acc))
            safe_ai = np.clip(ai, np.finfo(float).tiny, None)
            otovl = 20 * np.log10(safe_ai / self.a0)
            otovl_data.append(otovl)

        self.otovl_data = np.asarray(otovl_data).T
        self.otovl_env = np.max(self.otovl_data, axis=1)
        return self.otovl_env, self.otovl_data


class FreqDivMaxVibLevelSolver(SolverBase):
    """分频最大振级求解器。"""

    def __init__(
        self,
        accel: ArrayLike,
        *,
        fs: int = 500,
        freq_range: tuple[float, float] = (1.0, 200.0),
    ) -> None:
        accel_arr = np.asarray(accel)
        if accel_arr.ndim != 1:
            raise ValueError("'accel' 不是 1 维列表")
        self.accel = accel_arr
        self.fs = fs
        self.freq_range = freq_range
        self.octave = 1 / 3
        self.a0 = 1e-6
        self.overlap = 3 / 4
        self.time_windows = 1
        self.center_freqs = _center_freqs(self.freq_range)
        z_weight_df = _load_resource_csv("z_weight")
        self.weight_z = _read_weight_z_from_df(self.center_freqs, z_weight_df)
        self.fdvl_max: float | None = None
        self.fdvl_data: np.ndarray | None = None

    def __calculate_lower(self, center: float) -> float:
        return center / 2 ** (self.octave / 2)

    def __calculate_upper(self, center: float) -> float:
        return center * 2 ** (self.octave / 2)

    def __get_min_nfft(self, num: int) -> int:
        return int(np.around(np.power(2, np.ceil(np.log2(num)))))

    @property
    def bands(self) -> pd.DataFrame:
        """返回分频最大振级计算使用的中心频率及频带边界表。"""
        df = pd.DataFrame(self.center_freqs, columns=["中心频率 (Hz)"])
        df["下边界频率 (Hz)"] = df["中心频率 (Hz)"].apply(self.__calculate_lower)
        df["上边界频率 (Hz)"] = df["中心频率 (Hz)"].apply(self.__calculate_upper)
        return df

    def solve(self) -> tuple[float, np.ndarray]:
        """计算分频最大振级总值和各频带结果。"""
        accel = self.accel
        fs = self.fs
        overlap = self.overlap
        weight_z = self.weight_z
        center_freqs = self.center_freqs
        window_t = self.time_windows

        window_n = int(np.around(window_t * fs))
        window_nfft = self.__get_min_nfft(window_n)
        data_len = len(accel)
        step = int(round(window_n * (1 - overlap)))
        fdvls = []

        for idx in range(0, int(data_len - window_n + 1), step):
            window = accel[idx : idx + window_n]
            window = np.concatenate([window, np.zeros(window_nfft - window_n)])
            window_fft = np.fft.fft(window)
            ai = np.zeros_like(center_freqs)
            for i, center_freq in enumerate(center_freqs):
                subwindow_fft = window_fft.copy()
                lower_freq = self.__calculate_lower(float(center_freq))
                upper_freq = self.__calculate_upper(float(center_freq))
                drop_left = int(np.around(lower_freq * window_nfft / fs))
                drop_right = int(np.around(upper_freq * window_nfft / fs + 1))
                subwindow_fft[:drop_left] = 0.0
                subwindow_fft[-drop_left:] = 0.0
                subwindow_fft[drop_right:-drop_right] = 0.0
                window_acc = np.fft.ifft(subwindow_fft)[:window_n].real
                powered = np.sum(np.power(window_acc[1:-1], 2))
                powered += 0.5 * np.power(window_acc[0], 2)
                powered += 0.5 * np.power(window_acc[-1], 2)
                ai[i] = np.sqrt(powered / len(window_acc))
            safe_ai = np.clip(ai, np.finfo(float).tiny, None)
            fdvl = 20 * np.log10(safe_ai / self.a0) + weight_z
            fdvls.append(fdvl)

        self.fdvl_data = np.max(np.array(fdvls), axis=0)
        self.fdvl_max = float(np.max(self.fdvl_data, axis=0))
        return self.fdvl_max, self.fdvl_data


class FourPowVibDoseValueSolver(SolverBase):
    """四次方振动剂量值求解器。"""

    def __init__(
        self,
        accel: ArrayLike,
        *,
        fs: int = 500,
        freq_range: tuple[float, float] = (1.0, 80.0),
        nsup: int = 1,
    ) -> None:
        accel_arr = np.asarray(accel)
        if accel_arr.ndim != 1:
            raise ValueError("'accel' 不是 1 维列表")
        self.accel = accel_arr
        self.fs = fs
        self.freq_range = freq_range
        self.nsup = nsup
        self.octave = 1 / 3
        self.weight_type = WeightType.WK
        self.center_freqs = _center_freqs(self.freq_range)
        weight_df = _load_resource_csv("octave_weight")
        self.weight = _read_weight_from_df(self.center_freqs, weight_df, self.weight_type)
        self.fpvdv: float | None = None
        self.aw: np.ndarray | None = None

    def __calculate_lower(self, center: float) -> float:
        return center / 2 ** (self.octave / 2)

    def __calculate_upper(self, center: float) -> float:
        return center * 2 ** (self.octave / 2)

    def __get_min_nfft(self, num: int) -> int:
        return int(np.around(np.power(2, np.ceil(np.log2(num)))))

    @property
    def bands(self) -> pd.DataFrame:
        """返回四次方振动剂量值计算使用的中心频率及频带边界表。"""
        df = pd.DataFrame(self.center_freqs, columns=["中心频率 (Hz)"])
        df["下边界频率 (Hz)"] = df["中心频率 (Hz)"].apply(self.__calculate_lower)
        df["上边界频率 (Hz)"] = df["中心频率 (Hz)"].apply(self.__calculate_upper)
        return df

    def solve(self) -> tuple[float, np.ndarray]:
        """计算四次方振动剂量值及对应加权加速度时程。"""
        accel = self.accel
        center_freqs = self.center_freqs
        fs = self.fs
        nsup = self.nsup

        data_len = len(accel)
        data_nfft = self.__get_min_nfft(data_len)
        data_extend = np.zeros(data_nfft)
        data_extend[:data_len] = accel
        data_fft = np.fft.fft(data_extend)
        aw = np.zeros(data_len)

        for i, center_freq in enumerate(center_freqs):
            subdata_fft = data_fft.copy()
            lower_freq = self.__calculate_lower(float(center_freq))
            upper_freq = self.__calculate_upper(float(center_freq))
            drop_left = int(np.around(lower_freq * data_nfft / fs))
            drop_right = int(np.around(upper_freq * data_nfft / fs + 1))
            subdata_fft[:drop_left] = 0.0
            subdata_fft[-drop_left:] = 0.0
            subdata_fft[drop_right:-drop_right] = 0.0
            subdata_acc = np.fft.ifft(subdata_fft)[:data_len].real
            aw = aw + self.weight[i] * self.weight[i] * subdata_acc * subdata_acc

        aw = np.sqrt(aw)
        powered = np.sum(np.power(aw[1:-1], 4))
        powered += 0.5 * np.power(aw[0], 4)
        powered += 0.5 * np.power(aw[-1], 4)
        fpvdv = np.power(powered / fs, 1 / 4)
        fpvdv *= np.power(int(nsup), 0.25)

        self.fpvdv = float(fpvdv)
        self.aw = aw.copy()
        return self.fpvdv, self.aw


__all__ = [
    "SolverBase",
    "LinearSequence",
    "SDOFSolver",
    "SDOFSolveMethod",
    "TransferSolver",
    "ZVibLevelSolver",
    "OneThirdOctaveVibLevelSolver",
    "FreqDivMaxVibLevelSolver",
    "FourPowVibDoseValueSolver",
    "WeightType",
]
