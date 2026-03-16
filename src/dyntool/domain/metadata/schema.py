"""元数据 schema 定义。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class MetadataSchema:
    """描述元数据身份字段、属性字段和别名规则。"""

    name: str
    version: int = 1
    identity_fields: tuple[str, ...] = ()
    attribute_fields: tuple[str, ...] = ()
    extra_field: str | None = "extra"
    aliases: dict[str, str] = field(default_factory=dict)

    def canonical_field(self, name: str) -> str:
        """返回字段或别名对应的规范名称。"""

        return self.aliases.get(name, name)

    def canonicalize_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        """将 payload 中的别名字段归一到规范名称。"""

        normalized: dict[str, Any] = {}
        for raw_name, value in payload.items():
            canonical = self.canonical_field(str(raw_name))
            normalized[canonical] = value
        return normalized

    def normalize_identity(self, payload: dict[str, Any]) -> dict[str, Any]:
        """按 schema 规则提取身份字段。"""

        normalized = self.canonicalize_payload(payload)
        if self.identity_fields:
            return {field: normalized.get(field) for field in self.identity_fields if field in normalized}
        return dict(normalized)

    def normalize_attributes(self, payload: dict[str, Any]) -> dict[str, Any]:
        """按 schema 规则提取属性字段。"""

        normalized = self.canonicalize_payload(payload)
        if self.attribute_fields:
            return {field: normalized.get(field) for field in self.attribute_fields if field in normalized}
        return dict(normalized)


__all__ = ["MetadataSchema"]
