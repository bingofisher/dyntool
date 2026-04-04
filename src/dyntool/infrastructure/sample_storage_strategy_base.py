"""样本存储策略基础协议。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

import pandas as pd

from .sample_storage_context import StorageContext

if TYPE_CHECKING:
    from ..domain.samples.base import SampleBaseModel


class _StorageWriteSession:
    """样本写入会话。

    Notes:
        默认实现直接逐样本转发到策略的 ``save_sample``。需要复用文件句柄、
        数据库连接或事务的存储方案，可以覆盖
        ``_StorageStrategy.write_session()`` 返回自定义实现。
    """

    def __init__(self, strategy: "_StorageStrategy") -> None:
        self._strategy = strategy

    def __enter__(self) -> "_StorageWriteSession":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        del exc_type, exc, tb

    def save_sample(self, sample: "SampleBaseModel", categories: list[str] | None = None) -> None:
        self._strategy.save_sample(sample, categories)


class _StorageReadSession:
    """样本读取会话。

    Notes:
        默认实现直接转发到策略对象本身。需要复用只读连接、文件句柄或仓库级并发控制的
        存储方案，可以覆盖 ``_StorageStrategy.read_session()`` 返回自定义实现。
    """

    def __init__(self, strategy: "_StorageStrategy") -> None:
        self._strategy = strategy

    def __enter__(self) -> "_StorageReadSession":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        del exc_type, exc, tb

    def load_sample(
        self,
        uid: str,
        name: str,
        categories: list[str] | None = None,
    ) -> "SampleBaseModel":
        return self._strategy.load_sample(uid, name, categories)

    def load_sample_fields(
        self,
        uid: str,
        name: str,
        categories: list[str],
    ) -> dict[str, object]:
        return self._strategy.load_sample_fields(uid, name, categories)

    def load_many_sample_fields(
        self,
        items: list[tuple[str, str]],
        categories: list[str],
    ) -> dict[str, dict[str, object]]:
        return self._strategy.load_many_sample_fields(items, categories)

    def sample_presence(
        self,
        uid: str,
        name: str,
    ) -> dict[str, bool]:
        return self._strategy.sample_presence(uid, name)

    def summary_frame(
        self,
        *,
        uids: list[str] | None = None,
        metadata_fields: list[str] | None = None,
        data_vars: list[str] | None = None,
        features: list[str] | None = None,
    ) -> pd.DataFrame:
        return self._strategy.summary_frame(
            uids=uids,
            metadata_fields=metadata_fields,
            data_vars=data_vars,
            features=features,
        )


class _StorageStrategy(ABC):
    """样本存储策略基类。"""

    def __init__(self, ctx: StorageContext) -> None:
        self.ctx = ctx

    @abstractmethod
    def prepare_layout(self) -> None: ...

    @abstractmethod
    def uid_name_index(self) -> dict[str, str]: ...

    @abstractmethod
    def save_sample(self, sample: "SampleBaseModel", categories: list[str] | None = None) -> None: ...

    def resolve_load_categories(
        self,
        categories: list[str] | None = None,
    ) -> list[str]:
        """把外部请求的分类名解析为存储层使用的标准槽位名。"""

        return self.ctx.resolve_storage_categories(categories)

    @abstractmethod
    def load_sample(
        self,
        uid: str,
        name: str,
        categories: list[str] | None = None,
    ) -> "SampleBaseModel": ...

    def load_sample_fields(
        self,
        uid: str,
        name: str,
        categories: list[str],
    ) -> dict[str, object]:
        """按槽位读取单个样本数据。

        默认回退到整样本恢复，仅用于未优化的存储方案。
        """

        loaded = self.load_sample(uid, name, categories)
        return {
            category: data
            for category in self.resolve_load_categories(categories)
            if (data := loaded.get_data_var(category)) is not None
        }

    def load_many_sample_fields(
        self,
        items: list[tuple[str, str]],
        categories: list[str],
    ) -> dict[str, dict[str, object]]:
        """按槽位批量读取多个样本数据。

        默认逐样本回退；支持的存储方案可覆盖为真正的批量实现。
        """

        return {uid: self.load_sample_fields(uid, name, categories) for uid, name in items}

    def write_session(self) -> _StorageWriteSession:
        """返回当前存储方案的写入会话。"""

        return _StorageWriteSession(self)

    def read_session(self) -> _StorageReadSession:
        """返回当前存储方案的读取会话。"""

        return _StorageReadSession(self)

    def sample_presence(
        self,
        uid: str,
        name: str,
    ) -> dict[str, bool]:
        """返回样本槽位存在性映射。"""

        del uid, name
        return {}

    def summary_frame(
        self,
        *,
        uids: list[str] | None = None,
        metadata_fields: list[str] | None = None,
        data_vars: list[str] | None = None,
        features: list[str] | None = None,
    ) -> pd.DataFrame:
        """直接从底层摘要层构建标量表。

        默认表示当前存储方案不支持摘要快路径。
        """

        del uids, metadata_fields, data_vars, features
        raise RuntimeError("当前存储方案不支持摘要快路径")

    @abstractmethod
    def organize(self, valid_uids: set[str]) -> int: ...


__all__ = ["_StorageReadSession", "_StorageStrategy", "_StorageWriteSession"]
