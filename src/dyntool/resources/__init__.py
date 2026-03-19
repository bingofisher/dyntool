"""AdvDynTool 正式资源模块。"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

_RESOURCES_ROOT = Path(__file__).resolve().parent
_MANIFEST_PATH = _RESOURCES_ROOT / "manifest.json"


def _load_manifest(manifest_path: Path = _MANIFEST_PATH) -> dict[str, str]:
    """读取资源清单映射。"""

    if not manifest_path.exists():
        raise FileNotFoundError(f"资源清单不存在: {manifest_path}")
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("资源清单格式错误，预期为 JSON object")
    return {str(key): str(value) for key, value in data.items()}


_STANDARD_KEYS = _load_manifest()


@dataclass(slots=True)
class ResourceQueryOptions:
    """资源查询参数。"""

    key: str | None = None
    freq_range: tuple[float, float] = (1.0, 80.0)
    csv_options: dict[str, Any] = field(default_factory=dict)


def keys() -> tuple[str, ...]:
    """返回当前资源清单中的可用键。"""

    return tuple(sorted(_STANDARD_KEYS))


def manifest() -> dict[str, str]:
    """返回资源清单映射。"""

    return dict(_STANDARD_KEYS)


def path(key: str) -> Path:
    """返回资源键对应的文件路径。"""

    if key not in _STANDARD_KEYS:
        raise KeyError(f"未知资源 key: {key}，可用项: {sorted(_STANDARD_KEYS)}")
    return _RESOURCES_ROOT / _STANDARD_KEYS[key]


def csv(
    key: str | None = None,
    *,
    options: ResourceQueryOptions | None = None,
    csv_options: dict[str, Any] | None = None,
) -> pd.DataFrame:
    """读取指定资源键对应的 CSV 数据。"""

    resolved_key = key or (options.key if options is not None else None)
    if resolved_key is None:
        raise TypeError("csv 查询必须提供 key")
    target = path(resolved_key)
    if not target.exists():
        raise FileNotFoundError(f"资源文件不存在: {target}")
    merged = dict(options.csv_options) if options is not None else {}
    if csv_options is not None:
        merged.update(csv_options)
    return pd.read_csv(target, **merged)


def center_freqs(
    freq_range: tuple[float, float] = (1.0, 80.0),
    *,
    options: ResourceQueryOptions | None = None,
) -> tuple[np.ndarray, pd.Index]:
    """返回指定频段内的中心频率。"""

    resolved_range = options.freq_range if options is not None else freq_range
    df = csv("center_freq")
    freq_col = "中心频率 (Hz)"
    if freq_col not in df.columns:
        raise ValueError(f"CSV 缺少列 {freq_col}")
    center = df[freq_col].to_numpy()
    lower, upper = resolved_range
    mask = (center >= lower) & (center <= upper)
    values = center[mask]
    return values, pd.Index(values, name=freq_col)


__all__ = [
    "ResourceQueryOptions",
    "center_freqs",
    "csv",
    "keys",
    "manifest",
    "path",
]
