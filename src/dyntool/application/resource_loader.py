"""应用层资源加载器。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

_RESOURCES_ROOT = Path(__file__).resolve().parents[1] / "resources"
_MANIFEST_PATH = _RESOURCES_ROOT / "manifest.json"


def _load_manifest(manifest_path: Path = _MANIFEST_PATH) -> dict[str, str]:
    if not manifest_path.exists():
        raise FileNotFoundError(f"资源清单不存在: {manifest_path}")
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("资源清单格式错误，预期为 JSON object")
    return {str(key): str(value) for key, value in data.items()}


_STANDARD_KEYS = _load_manifest()


class ResourceLoader:
    """统一资源加载器。"""

    _instance: ResourceLoader | None = None

    def __init__(self, base_path: Path | None = None) -> None:
        self._base = Path(base_path) if base_path is not None else _RESOURCES_ROOT

    @classmethod
    def get_instance(cls, base_path: Path | None = None) -> ResourceLoader:
        """返回共享资源加载器实例。"""
        if cls._instance is None:
            cls._instance = cls(base_path)
        elif base_path is not None:
            cls._instance._base = Path(base_path)
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """重置共享资源加载器单例。"""
        cls._instance = None

    def get_path(self, key: str) -> Path:
        """根据标准资源键返回对应资源文件路径。"""
        if key not in _STANDARD_KEYS:
            raise KeyError(f"未知资源 key: {key}，可用项: {list(_STANDARD_KEYS)}")
        return self._base / _STANDARD_KEYS[key]

    def list_keys(self) -> list[str]:
        """返回当前资源清单中可用的标准键列表。"""
        return sorted(_STANDARD_KEYS)

    def get_manifest(self) -> dict[str, str]:
        """返回资源清单的浅拷贝。"""
        return dict(_STANDARD_KEYS)

    def get_csv(self, key: str, **read_csv_kwargs: Any) -> pd.DataFrame:
        """读取指定资源键对应的 CSV 文件。"""
        path = self.get_path(key)
        if not path.exists():
            raise FileNotFoundError(f"资源文件不存在: {path}")
        return pd.read_csv(path, **read_csv_kwargs)

    def get_center_freqs(
        self,
        freq_range: tuple[float, float] = (1.0, 80.0),
    ) -> tuple[np.ndarray, pd.Index]:
        """读取并筛选中心频率资源表。"""
        df = self.get_csv("center_freq")
        freq_col = "中心频率 (Hz)"
        if freq_col not in df.columns:
            raise ValueError(f"CSV 缺少列: {freq_col}")
        center_freqs = df[freq_col].to_numpy()
        lower, upper = freq_range
        mask = (center_freqs >= lower) & (center_freqs <= upper)
        arr = center_freqs[mask]
        return arr, pd.Index(arr, name=freq_col)


__all__ = [
    "ResourceLoader",
    "_MANIFEST_PATH",
    "_RESOURCES_ROOT",
    "_STANDARD_KEYS",
]
