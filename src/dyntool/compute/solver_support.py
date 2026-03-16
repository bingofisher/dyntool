"""Shared helpers for solver implementations."""

from __future__ import annotations

import io
import json
from pathlib import Path

import numpy as np
import pandas as pd

_RESOURCES_ROOT = Path(__file__).resolve().parents[1] / "resources"


def load_manifest() -> dict[str, str]:
    """Load solver resource manifest."""

    text = (_RESOURCES_ROOT / "manifest.json").read_text(encoding="utf-8")
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("资源清单格式错误，预期为 JSON object")
    return {str(k): str(v) for k, v in data.items()}


def load_resource_csv(key: str) -> pd.DataFrame:
    """Load csv resource declared in manifest."""

    manifest = load_manifest()
    if key not in manifest:
        raise KeyError(f"未知资源 key: {key}")
    rel = manifest[key]
    text = (_RESOURCES_ROOT / rel).read_text(encoding="utf-8")
    return pd.read_csv(io.StringIO(text))


def center_freqs(freq_range: tuple[float, float]) -> np.ndarray:
    """Resolve center frequencies within a range."""

    df = load_resource_csv("center_freq")
    freq_col = "中心频率 (Hz)"
    if freq_col not in df.columns:
        raise ValueError(f"CSV 缺少列 {freq_col}")
    values = df[freq_col].to_numpy()
    lower, upper = freq_range
    return values[(values >= lower) & (values <= upper)]


def read_weight_from_df(
    center_freqs: np.ndarray,
    df: pd.DataFrame,
    weight_key: str,
) -> np.ndarray:
    """Read octave weights from a weight table."""

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
    """Read Z weights from a weight table."""

    merged = pd.DataFrame(center_freqs, columns=["中心频率 (Hz)"]).merge(
        df,
        on="中心频率 (Hz)",
        how="left",
    )
    merged.loc[merged["中心频率 (Hz)"] < 4.0, "计权因子 (dB)"] = 0.0
    return merged["计权因子 (dB)"].to_numpy()


def calculate_lower(center: float, octave: float) -> float:
    """Calculate octave-band lower frequency bound."""

    return center / 2 ** (octave / 2)


def calculate_upper(center: float, octave: float) -> float:
    """Calculate octave-band upper frequency bound."""

    return center * 2 ** (octave / 2)


def get_min_nfft(num: int) -> int:
    """Return the minimum power-of-two nfft."""

    return int(np.around(np.power(2, np.ceil(np.log2(num)))))


def build_bands(center_values: np.ndarray, octave: float) -> pd.DataFrame:
    """Build a dataframe describing octave bands."""

    df = pd.DataFrame(center_values, columns=["中心频率 (Hz)"])
    df["下边界频率(Hz)"] = df["中心频率 (Hz)"].apply(lambda value: calculate_lower(float(value), octave))
    df["上边界频率(Hz)"] = df["中心频率 (Hz)"].apply(lambda value: calculate_upper(float(value), octave))
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
    """Calculate one octave-band RMS from an FFT window."""

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
