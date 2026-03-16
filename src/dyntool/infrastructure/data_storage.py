"""数据模型级持久化封装。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from . import persistence as io_registry
from ..storage.types import ContainerFormat, resolve_data_category


class DataStorage:
    """数据模型存储层，统一封装 save/load 能力。"""

    def save(
        self,
        path: Path,
        data: Any,
        *,
        fmt: ContainerFormat,
        category: str,
        options: dict[str, Any] | None = None,
    ) -> None:
        """按指定格式保存数据模型。"""

        del category
        opts = options.copy() if options else {}
        path.parent.mkdir(parents=True, exist_ok=True)
        if fmt in {ContainerFormat.CSV, ContainerFormat.H5}:
            io_registry.save(path, data, fmt=fmt.value, **opts)
            return
        if fmt is ContainerFormat.NPY:
            payload = data.to_dict()  # type: ignore[union-attr]
            np.save(path, np.array([payload], dtype=object), allow_pickle=True)
            return
        if fmt is ContainerFormat.JSON:
            payload = data.to_dict()  # type: ignore[union-attr]
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2, default=str)
            return
        raise ValueError(f"不支持的数据模型格式: {fmt}")

    def load(
        self,
        path: Path,
        *,
        fmt: ContainerFormat,
        category: str,
        options: dict[str, Any] | None = None,
        container_type: type[Any] | None = None,
    ) -> Any:
        """按指定格式加载数据模型。"""

        opts = options.copy() if options else {}
        if fmt in {ContainerFormat.CSV, ContainerFormat.H5}:
            resolved_category = (
                container_type.category  # type: ignore[attr-defined]
                if container_type is not None and hasattr(container_type, "category")
                else resolve_data_category(category)
            )
            return io_registry.load(
                path,
                fmt=fmt.value,
                category=resolved_category,
                **opts,
            )
        if fmt is ContainerFormat.NPY:
            payload = np.load(path, allow_pickle=True).item()
            cls = self._resolve_container_type(
                category=category,
                container_type=container_type,
            )
            return cls.from_dict(payload)  # type: ignore[union-attr]
        if fmt is ContainerFormat.JSON:
            with open(path, encoding="utf-8") as f:
                payload = json.load(f)
            cls = self._resolve_container_type(
                category=category,
                container_type=container_type,
            )
            return cls.from_dict(payload)  # type: ignore[union-attr]
        raise ValueError(f"不支持的数据模型格式: {fmt}")

    @staticmethod
    def _resolve_container_type(
        *,
        category: str,
        container_type: type[Any] | None,
    ) -> type[Any]:
        """解析用于反序列化的数据模型类型。"""

        if container_type is not None:
            return container_type

        from ..domain.models import DataModelBase

        return DataModelBase.from_category(resolve_data_category(category))
