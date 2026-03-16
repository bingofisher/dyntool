"""样本存储策略基础协议。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from .sample_storage_context import StorageContext

if TYPE_CHECKING:
    from ..domain.samples.base import SampleBaseModel


class _StorageStrategy(ABC):
    def __init__(self, ctx: StorageContext) -> None:
        self.ctx = ctx

    @abstractmethod
    def prepare_layout(self) -> None: ...

    @abstractmethod
    def uid_name_index(self) -> dict[str, str]: ...

    @abstractmethod
    def save_sample(self, sample: SampleBaseModel, categories: list[str] | None = None) -> None: ...

    def resolve_load_categories(
        self,
        categories: list[str] | None = None,
    ) -> list[str]:
        """Resolve requested categories into canonical storage slot names."""

        return self.ctx.resolve_storage_categories(categories)

    @abstractmethod
    def load_sample(
        self,
        uid: str,
        name: str,
        categories: list[str] | None = None,
    ) -> SampleBaseModel: ...

    @abstractmethod
    def organize(self, valid_uids: set[str]) -> int: ...


__all__ = ["_StorageStrategy"]
