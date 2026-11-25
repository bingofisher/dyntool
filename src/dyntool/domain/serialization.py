"""领域序列化协议：StructuredPayload。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import re
from typing import Any, Mapping


SCHEMA_VERSION = "1.0.0"


@dataclass(slots=True)
class StructuredPayload:
    """统一交换载荷。"""

    schema_version: str = SCHEMA_VERSION
    entity_type: str = ""
    domain: str = "default"
    category: str = ""
    coords: dict[str, Any] = field(default_factory=dict)
    data_vars: dict[str, Any] = field(default_factory=dict)
    units: dict[str, str] = field(default_factory=dict)
    attrs: dict[str, Any] = field(default_factory=dict)
    meta: dict[str, Any] = field(default_factory=dict)
    lineage: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self._validate_version()

    def _validate_version(self) -> None:
        """校验非负 ASCII 三段版本，拒绝未知版本及静默降写。"""
        if re.fullmatch(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)", self.schema_version) is None:
            raise ValueError(f"交换载荷版本格式无效：{self.schema_version}")
        version = tuple(int(part) for part in self.schema_version.split("."))
        if len(version) != 3 or version > (1, 0, 0) or version[0] != 1:
            raise ValueError(f"交换载荷版本 {self.schema_version} 不受支持，当前支持 {SCHEMA_VERSION}")

    def to_dict(self) -> dict[str, Any]:
        """转为普通字典。"""

        self._validate_version()
        return {
            "schema_version": self.schema_version,
            "entity_type": self.entity_type,
            "domain": self.domain,
            "category": self.category,
            "coords": dict(self.coords),
            "data_vars": dict(self.data_vars),
            "units": dict(self.units),
            "attrs": dict(self.attrs),
            "meta": dict(self.meta),
            "lineage": list(self.lineage),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "StructuredPayload":
        """从字典恢复载荷。"""

        return cls(
            schema_version=str(payload.get("schema_version", SCHEMA_VERSION)),
            entity_type=str(payload.get("entity_type", "")),
            domain=str(payload.get("domain", "default")),
            category=str(payload.get("category", "")),
            coords=dict(payload.get("coords", {})),
            data_vars=dict(payload.get("data_vars", {})),
            units={str(k): str(v) for k, v in dict(payload.get("units", {})).items()},
            attrs=dict(payload.get("attrs", {})),
            meta=dict(payload.get("meta", {})),
            lineage=list(payload.get("lineage", [])),
        )


def normalize_payload(
    payload: Mapping[str, Any] | StructuredPayload,
) -> StructuredPayload:
    """规范化输入载荷。"""

    if isinstance(payload, StructuredPayload):
        payload._validate_version()
        return payload
    return StructuredPayload.from_dict(payload)


def make_lineage_entry(
    *,
    action: str,
    actor: str = "system",
    detail: str | None = None,
    timestamp: str | None = None,
) -> dict[str, str]:
    """创建 lineage 记录。"""

    created_at = timestamp or datetime.now(timezone.utc).isoformat()
    entry = {
        "action": action,
        "actor": actor,
        "timestamp": created_at,
    }
    if detail:
        entry["detail"] = detail
    return entry


def append_lineage(
    payload: StructuredPayload | Mapping[str, Any],
    *,
    action: str,
    actor: str = "system",
    detail: str | None = None,
) -> StructuredPayload:
    """在载荷末尾附加 lineage。"""

    normalized = normalize_payload(payload)
    normalized.lineage.append(make_lineage_entry(action=action, actor=actor, detail=detail))
    return normalized


__all__ = [
    "SCHEMA_VERSION",
    "StructuredPayload",
    "normalize_payload",
    "make_lineage_entry",
    "append_lineage",
]
