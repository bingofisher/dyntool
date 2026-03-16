"""数据模型结构化载荷恢复入口。"""

from __future__ import annotations

from ..serialization import StructuredPayload, normalize_payload
from .base import DataModelBase


def model_from_structured_payload(
    payload: StructuredPayload | dict[str, object],
) -> DataModelBase:
    """从结构化载荷恢复数据模型实例。"""

    normalized = normalize_payload(payload)
    target_cls = DataModelBase.from_category(normalized.category)
    return target_cls.from_structured_payload(normalized)


__all__ = ["model_from_structured_payload"]
