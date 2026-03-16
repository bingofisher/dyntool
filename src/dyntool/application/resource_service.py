"""包内静态资源访问入口。"""

from __future__ import annotations

from pathlib import Path
from typing import cast

import numpy as np
import pandas as pd

from .options import ResourceQueryOptions
from .resource_loader import ResourceLoader
from .runtime_binding import get_resource_loader_cls


class ResourceService:
    """对外暴露只读资源工具箱。"""

    def __init__(self) -> None:
        self._loader = cast(type[ResourceLoader], get_resource_loader_cls()).get_instance()

    def keys(self) -> list[str]:
        """返回已注册资源键列表。"""

        return self._loader.list_keys()

    def manifest(self) -> dict[str, str]:
        """返回资源清单映射。"""

        return self._loader.get_manifest()

    def path(self, key: str) -> Path:
        """返回资源键对应的文件路径。"""

        return self._loader.get_path(key)

    def csv(
        self,
        key: str | None = None,
        *,
        options: ResourceQueryOptions | None = None,
        csv_options: dict[str, object] | None = None,
    ) -> pd.DataFrame:
        """读取指定资源键对应的 CSV 数据。"""

        resolved_key = key or (options.key if options is not None else None)
        if resolved_key is None:
            raise TypeError("csv 查询必须提供 key")
        merged = dict(options.csv_options) if options is not None else {}
        if csv_options is not None:
            merged.update(csv_options)
        return self._loader.get_csv(resolved_key, **merged)

    def center_freqs(
        self,
        freq_range: tuple[float, float] = (1.0, 80.0),
        *,
        options: ResourceQueryOptions | None = None,
    ) -> tuple[np.ndarray, pd.Index]:
        """返回指定频段内的中心频率。"""

        resolved_range = options.freq_range if options is not None else freq_range
        return self._loader.get_center_freqs(freq_range=resolved_range)


__all__ = ["ResourceService"]
