"""Single-sample storage facade."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .sample_storage_context import StorageContext
from .sample_storage_strategies import STRATEGY_REGISTRY, _StorageStrategy
from ..storage.types import StorageScheme

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

    def save(self, sample: SampleBaseModel, categories: list[str] | None = None) -> None:
        """保存单个样本及其选定数据槽位。"""
        self.strategy.save_sample(sample, categories)

    def load(self, uid: str, categories: list[str] | None = None) -> SampleBaseModel:
        """根据 UID 读取单个样本。"""
        resolved_categories = self.ctx.resolve_storage_categories(categories)
        idx = self.index()
        if uid not in idx:
            raise FileNotFoundError(f"No file found for UID: {uid}")
        return self.strategy.load_sample(uid, idx[uid], resolved_categories)

    def organize(self, valid_uids: set[str]) -> int:
        """清理不在 ``valid_uids`` 中的陈旧样本条目。"""
        return self.strategy.organize(valid_uids)
