"""单样本存储门面。"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd

from ..storage.types import StorageScheme
from .sample_storage_context import StorageContext
from .sample_storage_strategies import STRATEGY_REGISTRY, _StorageReadSession, _StorageStrategy

if TYPE_CHECKING:
    from ..domain.samples.base import SampleBaseModel


class SampleStorage:
    """单样本存储门面，按存储方案路由到底层策略。"""

    _STRATEGIES: dict[StorageScheme, type[_StorageStrategy]] = STRATEGY_REGISTRY

    def __init__(self, ctx: StorageContext) -> None:
        self.ctx = ctx
        strategy_cls = self._STRATEGIES.get(ctx.storage_scheme)
        if strategy_cls is None:
            raise ValueError(f"Unsupported storage_scheme: {ctx.storage_scheme}")
        self.strategy = strategy_cls(ctx)
        self.strategy.prepare_layout()

    def index(self) -> dict[str, str]:
        """返回当前存储中的 ``UID -> 名称`` 索引映射。"""

        return self.strategy.uid_name_index()

    def save(self, sample: "SampleBaseModel", categories: list[str] | None = None) -> None:
        """保存单个样本及其选定数据槽位。"""

        self.strategy.save_sample(sample, categories)

    def write_session(self) -> object:
        """返回当前存储方案的写入会话。"""

        return self.strategy.write_session()

    def read_session(self) -> _StorageReadSession:
        """返回当前存储方案的读取会话。"""

        return self.strategy.read_session()

    def load(self, uid: str, categories: list[str] | None = None) -> "SampleBaseModel":
        """根据 UID 读取单个样本。"""

        resolved_categories = self.ctx.resolve_storage_categories(categories)
        idx = self.index()
        if uid not in idx:
            raise FileNotFoundError(f"No file found for UID: {uid}")
        with self.read_session() as session:
            sample = session.load_sample(uid, idx[uid], resolved_categories)
            sample._set_storage_presence_internal(session.sample_presence(uid, idx[uid]))
        return sample

    def load_fields(self, uid: str, categories: list[str]) -> dict[str, object]:
        """按槽位读取单个样本的目标数据。"""

        resolved_categories = self.ctx.resolve_storage_categories(categories)
        idx = self.index()
        if uid not in idx:
            raise FileNotFoundError(f"No file found for UID: {uid}")
        with self.read_session() as session:
            return session.load_sample_fields(uid, idx[uid], resolved_categories)

    def load_many_fields(self, uids: list[str], categories: list[str]) -> dict[str, dict[str, object]]:
        """按槽位批量读取多个样本的数据。"""

        resolved_categories = self.ctx.resolve_storage_categories(categories)
        idx = self.index()
        missing = [uid for uid in uids if uid not in idx]
        if missing:
            raise FileNotFoundError(f"No file found for UID: {missing[0]}")
        items = [(uid, idx[uid]) for uid in uids]
        with self.read_session() as session:
            return session.load_many_sample_fields(items, resolved_categories)

    def presence(self, uid: str) -> dict[str, bool]:
        """读取样本槽位存在性映射。"""

        idx = self.index()
        if uid not in idx:
            raise FileNotFoundError(f"No file found for UID: {uid}")
        with self.read_session() as session:
            return session.sample_presence(uid, idx[uid])

    def summary_frame(
        self,
        *,
        uids: list[str] | None = None,
        metadata_fields: list[str] | None = None,
        data_vars: list[str] | None = None,
        features: list[str] | None = None,
    ) -> pd.DataFrame:
        """直接从底层摘要层构建标量表。"""

        with self.read_session() as session:
            return session.summary_frame(
                uids=uids,
                metadata_fields=metadata_fields,
                data_vars=data_vars,
                features=features,
            )

    def organize(self, valid_uids: set[str]) -> int:
        """清理不在 ``valid_uids`` 中的陈旧样本条目。"""

        return self.strategy.organize(valid_uids)
