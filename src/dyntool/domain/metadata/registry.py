"""元数据 payload 恢复入口。"""

from __future__ import annotations

from typing import Any

from ..serialization import StructuredPayload, normalize_payload
from .base import MetadataBase
from .types import Metadata, VibrationTestMetadata

_PAYLOAD_CATEGORY_TO_CLS: dict[str, type[MetadataBase]] = {
    "Metadata": Metadata,
    "VibrationTestMetadata": VibrationTestMetadata,
}
_PAYLOAD_DOMAIN_TO_CLS: dict[str, type[MetadataBase]] = {
    "default": Metadata,
    "vibration_test": VibrationTestMetadata,
}


def metadata_from_structured_payload(
    payload: StructuredPayload | dict[str, Any],
) -> MetadataBase:
    """根据 payload 恢复对应元数据对象。"""

    normalized = normalize_payload(payload)
    target_cls = _PAYLOAD_CATEGORY_TO_CLS.get(normalized.category)
    if target_cls is None:
        target_cls = _PAYLOAD_DOMAIN_TO_CLS.get(normalized.domain, Metadata)
    return target_cls.from_dict(normalized.meta)


__all__ = ["metadata_from_structured_payload"]
