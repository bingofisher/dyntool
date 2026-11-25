"""样本内部状态组织。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Iterable, Mapping
from copy import deepcopy

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

    def validate_uid(self, uid: str) -> None:
        """在任何身份发布前检查拥有者内的 UID 冲突。"""
        owner = self._sample._storage_set
        if owner is not None and uid in owner and owner[uid] is not self._sample:
            raise ValueError(f"样本集内已存在 UID 冲突: {uid}")

    def publish_change(self, old_uid: str, old_alias: str | None) -> None:
        """同步身份，失败时恢复 alias、索引与拥有者脏状态。"""
        sample = self._sample
        self.validate_uid(sample.uid)
        owner = sample._storage_set
        alias_state = sample.alias, sample._alias_overridden
        keys = dict(owner._items) if owner is not None else None
        dirty = owner.storage_dirty if owner is not None else False
        try:
            self.sync_identity_state(old_uid, old_alias)
            if owner is not None:
                owner._on_sample_metadata_changed(sample, old_uid)
        except Exception:
            self.set_alias_internal(alias_state[0], mark_override=alias_state[1])
            if owner is not None:
                owner._items.clear()
                owner._items.update(keys)
                owner.storage_dirty = dirty
            raise

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


class _SampleMutation:
    """预检统一更新请求，并在发布失败时恢复聚合状态。"""

    def __init__(self, sample: Any) -> None:
        self.sample = sample

    def apply(self, patch: dict[str, Any], *, strict: bool) -> None:
        sample = self.sample
        patch = dict(patch)
        data = patch.pop("data_vars", {})
        if not isinstance(data, dict):
            raise TypeError("data_vars 必须是 dict[str, DataModelBase]")
        valid_keys = {"alias", "metadata", *sample.sample_schema.slot_names()}
        for key in list(patch):
            if key not in valid_keys:
                if strict:
                    raise KeyError(f"未知样本字段：{key}")
                patch.pop(key)
        slots = {**data, **{key: value for key, value in patch.items() if key not in {"alias", "metadata"}}}
        for key, value in slots.items():
            spec = sample.sample_schema.field_spec(str(key))
            if value is not None and not spec.supports(value):
                raise TypeError(f"数据项 {key!r} 只接受 {spec.model_type.__name__}")
        candidate = patch.get("metadata")
        if "metadata" in patch:
            if not isinstance(candidate, MetadataBase):
                raise TypeError("metadata 必须是 MetadataBase 实例")
            _SampleIdentityState(sample).validate_uid(candidate.uid)
        old_metadata = sample.metadata
        alias = sample.alias, sample._alias_overridden
        old_data = dict(sample._data_map)
        loaded, dirty = set(sample._loaded_categories), set(sample._dirty_categories)
        states = deepcopy(sample._slot_state)
        owner = sample._storage_set
        keys = dict(owner._items) if owner is not None else None
        owner_dirty = owner.storage_dirty if owner is not None else False
        try:
            if candidate is not None:
                sample._replace_metadata(candidate)
            if "alias" in patch:
                if patch["alias"] is None:
                    sample.clear_alias_override()
                else:
                    sample.set_alias(str(patch["alias"]))
            for key, value in slots.items():
                sample.set_data_var(str(key), value)
        except BaseException:
            if sample.metadata is not old_metadata:
                sample.metadata.bind_change_callback(None)
                object.__setattr__(sample, "metadata", old_metadata)
                sample._bind_metadata(old_metadata)
            sample._set_alias_internal(alias[0], mark_override=alias[1])
            from ..models._model_data_state import _ModelDataState

            for model in sample._data_map.values():
                if model is not None and all(model is not old for old in old_data.values()):
                    _ModelDataState.detach_owner(model, sample)
            sample._data_map.clear()
            sample._data_map.update(
                {key: _ModelDataState.bind_owner(model, sample, key) for key, model in old_data.items()}
            )
            sample._loaded_categories, sample._dirty_categories = loaded, dirty
            sample._slot_state = states
            for key, model in old_data.items():
                if model is not None and str(key) in states:
                    model.__dict__["_provenance"] = deepcopy(states[str(key)])
            if owner is not None:
                owner._items.clear()
                owner._items.update(keys)
                owner.storage_dirty = owner_dirty
            raise


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
        return resolved

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
