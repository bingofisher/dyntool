"""样本内部状态组织。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Iterable, Mapping

from ..constants import DataCategory
from ..metadata import MetadataBase
from .types import SampleField

if TYPE_CHECKING:
    from .base import SampleBase


class _SampleIdentityState:
    """管理样本身份、metadata 与 alias 同步。"""

    def __init__(self, sample: "SampleBase") -> None:
        self._sample = sample

    def default_alias_for_metadata(self, metadata: MetadataBase | None = None) -> str:
        """根据元数据计算默认 alias。"""

        target = metadata or self._sample.metadata
        metadata_alias = getattr(target, "alias", None)
        if isinstance(metadata_alias, str) and metadata_alias.strip():
            return metadata_alias.strip()
        return target.uid

    def set_alias_internal(self, alias: str, *, mark_override: bool) -> None:
        """内部设置 alias 并维护覆盖状态。"""

        object.__setattr__(self._sample, "alias", alias.strip())
        object.__setattr__(self._sample, "_alias_overridden", mark_override)

    def restore_alias_internal(self, alias: str | None) -> None:
        """按持久化结果恢复 alias。"""

        resolved = str(alias or "").strip()
        if not resolved:
            self.set_alias_internal(self.default_alias_for_metadata(), mark_override=False)
            return
        self.set_alias_internal(
            resolved,
            mark_override=resolved != self.default_alias_for_metadata(),
        )

    def bind_metadata(self, metadata: MetadataBase) -> None:
        """绑定元数据变更回调。"""

        metadata.bind_change_callback(self._sample._on_metadata_changed)

    def sync_alias_after_metadata_change(
        self,
        *,
        old_uid: str | None,
        old_metadata_alias: str | None,
        force: bool = False,
    ) -> None:
        """在 metadata 变化后同步 alias。"""

        current_alias = self._sample.alias.strip()
        if force or not self._sample._alias_overridden:
            self.set_alias_internal(self.default_alias_for_metadata(), mark_override=False)
            return
        if (
            not current_alias
            or current_alias == old_uid
            or (old_metadata_alias is not None and current_alias == old_metadata_alias)
        ):
            self.set_alias_internal(self.default_alias_for_metadata(), mark_override=False)

    def sync_identity_state(
        self,
        old_uid: str | None,
        old_metadata_alias: str | None,
        *,
        force_alias: bool = False,
    ) -> None:
        """统一同步 metadata 变化后的 uid 与 alias 状态。"""

        self.sync_alias_after_metadata_change(
            old_uid=old_uid,
            old_metadata_alias=old_metadata_alias,
            force=force_alias,
        )


class _SampleCategoryState:
    """管理样本公开分类、加载状态与 storage presence。"""

    def __init__(self, sample: "SampleBase") -> None:
        self._sample = sample

    def normalize_public_categories(
        self,
        categories: Iterable[SampleField | DataCategory | str] | None = None,
    ) -> list[SampleField] | None:
        """把公开 categories 解析为去重后的 ``SampleField`` 列表。"""

        if categories is None:
            return None
        resolved: list[SampleField] = []
        for raw_category in categories:
            field = self._sample._resolve_field(raw_category)
            if field not in resolved:
                resolved.append(field)
        return resolved or None

    def set_storage_presence(
        self,
        presence: Mapping[SampleField | str, bool],
    ) -> None:
        """内部写入样本槽位存在性映射。"""

        normalized: dict[SampleField, bool] = {}
        for name, exists in presence.items():
            normalized[self._sample._resolve_field(str(name))] = bool(exists)
        for field in self._sample._loaded_categories:
            normalized[field] = True
        object.__setattr__(self._sample, "_storage_presence", normalized)


__all__ = [
    "_SampleCategoryState",
    "_SampleIdentityState",
]
