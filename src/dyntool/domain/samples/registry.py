"""领域样本 payload 恢复入口。"""

from __future__ import annotations

from typing import Any

from .base import SampleBaseModel
from .default import DefaultSample, DefaultSampleSet
from .sets import SampleSetBase
from .vibration_test import VibrationTestSample, VibrationTestSampleSet
from ..serialization import StructuredPayload, normalize_payload

_SAMPLE_CATEGORY_MAP: dict[str, type[SampleBaseModel]] = {
    "DefaultSample": DefaultSample,
    "VibrationTestSample": VibrationTestSample,
}

_SAMPLE_SET_CATEGORY_MAP: dict[str, type[SampleSetBase[Any]]] = {
    "DefaultSampleSet": DefaultSampleSet,
    "VibrationTestSampleSet": VibrationTestSampleSet,
}


def sample_from_structured_payload(
    payload: StructuredPayload | dict[str, Any],
) -> SampleBaseModel:
    """根据 payload 类别恢复样本对象。"""

    normalized = normalize_payload(payload)
    if normalized.category == "Sample":
        raise ValueError("旧样本类别名 Sample 已移除，请迁移为 DefaultSample。")
    target_cls = _SAMPLE_CATEGORY_MAP.get(normalized.category)
    if target_cls is None:
        raise ValueError(f"不支持的样本类别: {normalized.category}")
    return target_cls.from_structured_payload(normalized)


def sample_set_from_structured_payload(
    payload: StructuredPayload | dict[str, Any],
) -> SampleSetBase[Any]:
    """根据 payload 类别恢复样本集对象。"""

    normalized = normalize_payload(payload)
    if normalized.category == "SampleSet":
        raise ValueError("旧样本集类别名 SampleSet 已移除，请迁移为 DefaultSampleSet。")
    target_cls = _SAMPLE_SET_CATEGORY_MAP.get(normalized.category)
    if target_cls is None:
        raise ValueError(f"不支持的样本集类别: {normalized.category}")
    return target_cls.from_structured_payload(normalized)


__all__ = ["sample_from_structured_payload", "sample_set_from_structured_payload"]
