"""传递函数分析器与结果对象。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import numpy as np

from ...compute.solvers import TransferSolver
from ..constants import get_default_unit_system
from .frequency_spectrum import FreqSpec


class SignalModelProtocol(Protocol):
    """可供传递函数分析读取的一维信号模型协议。"""

    dt: float

    def get_value(self, unit: str | None = None) -> np.ndarray:
        """返回模型当前主值数组。"""


class SampleWithSignalProtocol(Protocol):
    """可通过属性名提取信号模型的样本协议。"""

    def __getattr__(self, name: str) -> SignalModelProtocol:
        """按属性名返回信号模型。"""


@dataclass(slots=True)
class TransferFunctionResult:
    """传递函数分析结果。"""

    frequencies: np.ndarray
    transfer_function: np.ndarray
    freqspec: FreqSpec


class TransferFunctionAnalyzer:
    """以类为主入口的传递函数分析器。"""

    def __init__(
        self,
        input_signal: np.ndarray | list[float],
        output_signal: np.ndarray | list[float],
        *,
        fs: int,
        nperseg: int = 256,
        noverlap: int = 128,
        nfft: int = 512,
        window: str = "hann",
    ) -> None:
        """初始化传递函数分析器。

        Args:
            input_signal: 输入侧一维时程数据。
            output_signal: 输出侧一维时程数据。
            fs: 采样频率，单位为 Hz。
            nperseg: Welch 类频域估计的分段长度。
            noverlap: 相邻分段的重叠点数。
            nfft: FFT 点数。
            window: 频域估计使用的窗函数名称。

        Returns:
            None。

        Raises:
            ValueError: 输入与输出信号长度不一致，或 `fs` 非正数时抛出。

        Notes:
            该分析器只负责单输入单输出的一维离散信号传递函数估计。
        """

        self.input_signal = self._coerce_signal(input_signal, name="input_signal")
        self.output_signal = self._coerce_signal(output_signal, name="output_signal")
        if self.input_signal.shape != self.output_signal.shape:
            raise ValueError("输入与输出信号长度必须一致。")
        if fs <= 0:
            raise ValueError("采样频率 fs 必须为正数。")
        self.fs = int(fs)
        self.nperseg = int(nperseg)
        self.noverlap = int(noverlap)
        self.nfft = int(nfft)
        self.window = window

    @classmethod
    def from_models(
        cls,
        input_model: SignalModelProtocol,
        output_model: SignalModelProtocol,
        *,
        fs: int | None = None,
        nperseg: int = 256,
        noverlap: int = 128,
        nfft: int = 512,
        window: str = "hann",
    ) -> "TransferFunctionAnalyzer":
        """从两个时程模型创建分析器。

        Args:
            input_model: 输入侧信号模型；必须提供 `dt` 和 `get_value()`。
            output_model: 输出侧信号模型；必须提供 `dt` 和 `get_value()`。
            fs: 显式采样频率。为空时根据模型的 `dt` 推导。
            nperseg: Welch 类频域估计的分段长度。
            noverlap: 相邻分段的重叠点数。
            nfft: FFT 点数。
            window: 频域估计使用的窗函数名称。

        Returns:
            已初始化的传递函数分析器。

        Raises:
            ValueError: 输入模型与输出模型的采样频率不一致时抛出。

        Notes:
            若显式传入 `fs`，该值只覆盖分析器使用的采样频率，不会回写模型对象。
        """

        input_signal, input_fs = cls._extract_model_signal(input_model, name="input_model")
        output_signal, output_fs = cls._extract_model_signal(output_model, name="output_model")
        if input_fs != output_fs:
            raise ValueError("输入模型与输出模型的采样频率必须一致。")
        return cls(
            input_signal,
            output_signal,
            fs=fs or input_fs,
            nperseg=nperseg,
            noverlap=noverlap,
            nfft=nfft,
            window=window,
        )

    @classmethod
    def from_samples(
        cls,
        input_sample: SampleWithSignalProtocol,
        output_sample: SampleWithSignalProtocol,
        *,
        data_attr: str = "accel",
        fs: int | None = None,
        nperseg: int = 256,
        noverlap: int = 128,
        nfft: int = 512,
        window: str = "hann",
    ) -> "TransferFunctionAnalyzer":
        """从两个样本对象创建分析器。

        Args:
            input_sample: 输入侧样本对象，必须能通过 `data_attr` 取到信号模型。
            output_sample: 输出侧样本对象，必须能通过 `data_attr` 取到信号模型。
            data_attr: 样本上承载信号模型的属性名，默认读取 `accel`。
            fs: 显式采样频率。为空时根据模型的 `dt` 推导。
            nperseg: Welch 类频域估计的分段长度。
            noverlap: 相邻分段的重叠点数。
            nfft: FFT 点数。
            window: 频域估计使用的窗函数名称。

        Returns:
            已初始化的传递函数分析器。

        Raises:
            ValueError: 样本缺少指定数据属性时抛出。

        Notes:
            该入口只负责样本属性提取；真实传递函数计算仍由 `solve()` 完成。
        """

        input_model = getattr(input_sample, data_attr, None)
        if input_model is None:
            raise ValueError(f"输入样本缺少 {data_attr} 数据。")
        output_model = getattr(output_sample, data_attr, None)
        if output_model is None:
            raise ValueError(f"输出样本缺少 {data_attr} 数据。")
        return cls.from_models(
            input_model,
            output_model,
            fs=fs,
            nperseg=nperseg,
            noverlap=noverlap,
            nfft=nfft,
            window=window,
        )

    def solve(self) -> TransferFunctionResult:
        """执行传递函数分析并返回领域结果。

        Returns:
            包含频率数组、复数传递函数和领域频谱对象的分析结果。

        Raises:
            ValueError: 求解器参数非法或求解失败时由下游逻辑抛出。

        Notes:
            频域领域对象会同步保留幅值与相位信息，便于后续绘图与导出。
        """

        solver = TransferSolver(
            self.input_signal,
            self.output_signal,
            fs=self.fs,
            nperseg=self.nperseg,
            noverlap=self.noverlap,
            nfft=self.nfft,
            window=self.window,
        )
        frequencies, transfer_function = solver.solve()
        freqspec = self._build_freqspec(frequencies, transfer_function)
        return TransferFunctionResult(
            frequencies=np.asarray(frequencies, dtype=float),
            transfer_function=np.asarray(transfer_function),
            freqspec=freqspec,
        )

    @staticmethod
    def _coerce_signal(values: np.ndarray | list[float], *, name: str) -> np.ndarray:
        """将输入信号规范化为一维浮点数组。"""

        arr = np.asarray(values, dtype=float).flatten()
        if arr.ndim != 1:
            raise ValueError(f"{name} 必须是一维数值序列。")
        if arr.size == 0:
            raise ValueError(f"{name} 不能为空。")
        return arr

    @classmethod
    def _extract_model_signal(
        cls,
        model: SignalModelProtocol,
        *,
        name: str,
    ) -> tuple[np.ndarray, int]:
        """从信号模型中提取数值序列与采样频率。"""

        dt = model.dt
        if float(dt) <= 0:
            raise ValueError(f"{name} 的采样步长 dt 必须为正数。")
        signal = cls._coerce_signal(model.get_value(), name=name)
        fs = int(round(1.0 / float(dt)))
        if fs <= 0:
            raise ValueError(f"{name} 的采样频率解析失败。")
        return signal, fs

    @staticmethod
    def _build_freqspec(frequencies: np.ndarray, transfer_function: np.ndarray) -> FreqSpec:
        """将频率响应转换为领域频谱对象。"""

        units = get_default_unit_system()
        return FreqSpec.from_data(
            np.asarray(frequencies, dtype=float),
            amp=np.abs(transfer_function),
            pha=np.angle(transfer_function),
            units={
                "freq": units.frequency,
                "amp": "dimensionless",
                "phase": units.phase,
            },
            unit_system=units,
        )


def analyze_transfer_function(
    input_signal: np.ndarray | list[float],
    output_signal: np.ndarray | list[float],
    *,
    fs: int,
    nperseg: int = 256,
    noverlap: int = 128,
    nfft: int = 512,
    window: str = "hann",
) -> TransferFunctionResult:
    """便捷函数：直接执行一次传递函数分析。

    Args:
        input_signal: 输入侧一维时程数据。
        output_signal: 输出侧一维时程数据。
        fs: 采样频率，单位为 Hz。
        nperseg: Welch 类频域估计的分段长度。
        noverlap: 相邻分段的重叠点数。
        nfft: FFT 点数。
        window: 频域估计使用的窗函数名称。

    Returns:
        传递函数分析结果对象。

    Raises:
        ValueError: 输入参数非法时抛出。

    Notes:
        该函数是 `TransferFunctionAnalyzer` 的一步式封装，适合脚本场景快速调用。
    """

    return TransferFunctionAnalyzer(
        input_signal,
        output_signal,
        fs=fs,
        nperseg=nperseg,
        noverlap=noverlap,
        nfft=nfft,
        window=window,
    ).solve()


__all__ = [
    "TransferFunctionAnalyzer",
    "TransferFunctionResult",
    "analyze_transfer_function",
]
