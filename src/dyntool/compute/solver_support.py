"""求解器实现共享的资源与带宽辅助函数。"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .. import resources as dt_resources


def load_manifest() -> dict[str, str]:
    """返回求解器使用的资源清单。"""

    return dt_resources.manifest()


def load_resource_csv(key: str) -> pd.DataFrame:
    """读取资源清单中声明的 CSV 资源。"""

    return dt_resources.csv(key)


def center_freqs(freq_range: tuple[float, float]) -> np.ndarray:
    """返回指定频段内的中心频率数组。"""

    values, _ = dt_resources.center_freqs(freq_range)
    return values


def read_weight_from_df(
    center_freqs: np.ndarray,
    df: pd.DataFrame,
    weight_key: str,
) -> np.ndarray:
    """从计权表中读取指定计权因子。"""

    weight_factor = 1000
    weight_cols = [
        "中心频率 (Hz)",
        f"{weight_key}_波峰因数*{weight_factor}",
        f"{weight_key} (dB)",
    ]
    if not set(weight_cols).issubset(df.columns):
        raise ValueError(f"计权方式 {weight_key} 需要列 {weight_cols}")
    merged = pd.DataFrame(center_freqs, columns=["中心频率 (Hz)"]).merge(
        df,
        on="中心频率 (Hz)",
        how="left",
    )
    return merged[weight_cols[1]].to_numpy() / weight_factor


def read_weight_z_from_df(center_freqs: np.ndarray, df: pd.DataFrame) -> np.ndarray:
    """从计权表中读取 Z 计权因子。"""

    merged = pd.DataFrame(center_freqs, columns=["中心频率 (Hz)"]).merge(
        df,
        on="中心频率 (Hz)",
        how="left",
    )
    merged.loc[merged["中心频率 (Hz)"] < 4.0, "计权因子 (dB)"] = 0.0
    return merged["计权因子 (dB)"].to_numpy()


def calculate_lower(center: float, octave: float) -> float:
    """计算倍频带下边界频率。"""

    return center / 2 ** (octave / 2)


def calculate_upper(center: float, octave: float) -> float:
    """计算倍频带上边界频率。"""

    return center * 2 ** (octave / 2)


def get_min_nfft(num: int) -> int:
    """返回不小于样本点数的最小 2 次幂 nfft。"""

    return int(np.around(np.power(2, np.ceil(np.log2(num)))))


def build_bands(center_values: np.ndarray, octave: float) -> pd.DataFrame:
    """构造倍频带描述表。"""

    df = pd.DataFrame(center_values, columns=["中心频率 (Hz)"])
    df["下边界频率 (Hz)"] = df["中心频率 (Hz)"].apply(lambda value: calculate_lower(float(value), octave))
    df["上边界频率 (Hz)"] = df["中心频率 (Hz)"].apply(lambda value: calculate_upper(float(value), octave))
    return df


def band_rms(
    window_fft: np.ndarray,
    *,
    center_freq: float,
    window_n: int,
    window_nfft: int,
    fs: int,
    octave: float,
) -> float:
    """根据 FFT 窗口计算单个倍频带的 RMS。"""

    subwindow_fft = window_fft.copy()
    lower_freq = calculate_lower(center_freq, octave)
    upper_freq = calculate_upper(center_freq, octave)
    drop_left = int(np.around(lower_freq * window_nfft / fs))
    drop_right = int(np.around(upper_freq * window_nfft / fs + 1))
    subwindow_fft[:drop_left] = 0.0
    subwindow_fft[-drop_left:] = 0.0
    subwindow_fft[drop_right:-drop_right] = 0.0
    window_acc = np.fft.ifft(subwindow_fft)[:window_n].real
    powered = np.sum(np.power(window_acc[1:-1], 2))
    powered += 0.5 * np.power(window_acc[0], 2)
    powered += 0.5 * np.power(window_acc[-1], 2)
    return float(np.sqrt(powered / len(window_acc)))


__all__ = [
    "band_rms",
    "build_bands",
    "calculate_lower",
    "calculate_upper",
    "center_freqs",
    "get_min_nfft",
    "load_manifest",
    "load_resource_csv",
    "read_weight_from_df",
    "read_weight_z_from_df",
]
