"""样本 schema 定义。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..metadata import MetadataBase
from ..models import DataModelBase


@dataclass(frozen=True, slots=True)
class SampleSlotSpec:
    """描述单个样本槽位。"""

    name: str
    model_type: type[DataModelBase]
    aliases: tuple[str, ...] = ()
    required: bool = False
    role: str | None = None
    include_in_storage: bool = True

    def supports(self, value: Any) -> bool:
        """判断槽位是否接受当前值。"""

        return isinstance(value, self.model_type)


@dataclass(frozen=True, slots=True)
class SampleSchema:
    """描述样本的元数据类型与数据槽位。"""

    name: str
    version: int = 1
    metadata_type: type[MetadataBase] = MetadataBase
    slots: tuple[SampleSlotSpec, ...] = ()
    aliases: dict[str, str] = field(default_factory=dict)

    def canonical_name(self, name: str) -> str:
        """将别名解析为规范槽位名。"""

        if name in self.aliases:
            return self.aliases[name]
        for slot in self.slots:
            if name == slot.name or name in slot.aliases:
                return slot.name
        return name

    def slot(self, name: str) -> SampleSlotSpec:
        """按规范名或别名获取槽位定义。"""

        canonical = self.canonical_name(name)
        for slot in self.slots:
            if slot.name == canonical:
                return slot
        raise KeyError(f"未知样本槽位: {name}")

    def has_slot(self, name: str) -> bool:
        """判断 schema 是否包含指定槽位。"""

        try:
            self.slot(name)
        except KeyError:
            return False
        return True

    def slot_names(self, *, include_storage_only: bool = False) -> tuple[str, ...]:
        """返回槽位名称列表。"""

        if not include_storage_only:
            return tuple(slot.name for slot in self.slots)
        return tuple(slot.name for slot in self.slots if slot.include_in_storage)


__all__ = ["SampleSlotSpec", "SampleSchema"]
