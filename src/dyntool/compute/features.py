"""通用时序特征分析函数。"""

from __future__ import annotations

from typing import Any

import numpy as np
from scipy.signal import find_peaks, hilbert

from .solver_support import band_rms as _band_rms


def _as_1d_array(value: Any) -> np.ndarray:
    """将输入规整为一维浮点数组。"""

    array = np.asarray(value, dtype=np.float64)
    if array.ndim == 0:
        return array.reshape(1)
    if array.ndim == 1:
        return array
    if array.ndim == 2 and array.shape[1] == 1:
        return array[:, 0]
    raise ValueError("特征分析仅支持一维数组输入")


def absmax_feature(value: Any) -> dict[str, float]:
    """返回绝对最大值。"""

    array = _as_1d_array(value)
    return {"absmax": float(np.max(np.abs(array)))}


def rms_feature(value: Any) -> dict[str, float]:
    """返回均方根。"""

    array = _as_1d_array(value)
    return {"rms": float(np.sqrt(np.mean(np.square(array))))}


def mean_feature(value: Any) -> dict[str, float]:
    """返回均值。"""

    array = _as_1d_array(value)
    return {"mean": float(np.mean(array))}


def std_feature(value: Any, *, ddof: int = 0) -> dict[str, float]:
    """返回标准差。"""

    array = _as_1d_array(value)
    return {"std": float(np.std(array, ddof=ddof))}


def crest_factor_feature(value: Any) -> dict[str, float]:
    """返回峰值因子。"""

    array = _as_1d_array(value)
    rms_value = rms_feature(array)["rms"]
    peak_value = absmax_feature(array)["absmax"]
    crest = np.nan if np.isclose(rms_value, 0.0) else peak_value / rms_value
    return {"crest_factor": float(crest)}


def zero_crossings_feature(value: Any) -> dict[str, int]:
    """返回零交叉次数。"""

    array = _as_1d_array(value)
    if array.size < 2:
        return {"zero_crossings": 0}
    signs = np.signbit(array)
    crossings = np.count_nonzero(signs[1:] != signs[:-1])
    return {"zero_crossings": int(crossings)}


def peak_feature(value: Any, **kwargs: Any) -> dict[str, float | int]:
    """返回主峰值及其索引。"""

    array = _as_1d_array(value)
    peak_indices, _ = find_peaks(array, **kwargs)
    if peak_indices.size == 0:
        index = int(np.argmax(array))
        return {"peak": float(array[index]), "peak_index": index}
    peak_values = array[peak_indices]
    best = int(np.argmax(peak_values))
    index = int(peak_indices[best])
    return {"peak": float(array[index]), "peak_index": index}


def peaks_feature(value: Any, **kwargs: Any) -> dict[str, np.ndarray]:
    """返回多峰检测结果。"""

    array = _as_1d_array(value)
    peak_indices, _ = find_peaks(array, **kwargs)
    return {
        "peak_indices": peak_indices.astype(np.int64, copy=False),
        "peak_values": array[peak_indices],
    }


def envelope_feature(value: Any) -> dict[str, np.ndarray]:
    """返回包络线序列。"""

    array = _as_1d_array(value)
    return {
        "index": np.arange(array.size, dtype=np.int64),
        "envelope": np.abs(hilbert(array)),
    }


def band_rms_feature(
    value: Any,
    *,
    fs: float,
    center_freq: float,
    octave: float = 1.0 / 3.0,
) -> dict[str, float]:
    """返回指定倍频带的均方根值。"""

    array = _as_1d_array(value)
    if fs <= 0:
        raise ValueError("fs 必须为正数")
    if center_freq <= 0:
        raise ValueError("center_freq 必须为正数")

    window_n = int(array.size)
    window_nfft = int(2 ** np.ceil(np.log2(max(window_n, 2))))
    window_fft = np.fft.fft(array, n=window_nfft)
    return {
        "band_rms": float(
            _band_rms(
                window_fft,
                center_freq=float(center_freq),
                window_n=window_n,
                window_nfft=window_nfft,
                fs=int(round(fs)),
                octave=float(octave),
            )
        ),
        "center_freq": float(center_freq),
    }


__all__ = [
    "absmax_feature",
    "band_rms_feature",
    "crest_factor_feature",
    "envelope_feature",
    "mean_feature",
    "peak_feature",
    "peaks_feature",
    "rms_feature",
    "std_feature",
    "zero_crossings_feature",
]
