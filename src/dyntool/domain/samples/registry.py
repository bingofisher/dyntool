"""领域样本 payload 恢复入口。"""

from __future__ import annotations

from typing import Any

from .base import SampleBaseModel
from .default import Sample, SampleSet
from .sets import SampleSetBase
from .vibration_test import VibrationTestSample, VibrationTestSampleSet
from ..serialization import StructuredPayload, normalize_payload

_SAMPLE_CATEGORY_MAP: dict[str, type[SampleBaseModel]] = {
    "Sample": Sample,
    "VibrationTestSample": VibrationTestSample,
}

_SAMPLE_SET_CATEGORY_MAP: dict[str, type[SampleSetBase[Any]]] = {
    "SampleSet": SampleSet,
    "VibrationTestSampleSet": VibrationTestSampleSet,
}


def sample_from_structured_payload(
    payload: StructuredPayload | dict[str, Any],
) -> SampleBaseModel:
    """根据 payload 类别恢复样本对象。"""

    normalized = normalize_payload(payload)
    target_cls = _SAMPLE_CATEGORY_MAP.get(normalized.category)
    if target_cls is None:
        raise ValueError(f"不支持的样本类别: {normalized.category}")
    return target_cls.from_structured_payload(normalized)


def sample_set_from_structured_payload(
    payload: StructuredPayload | dict[str, Any],
) -> SampleSetBase[Any]:
    """根据 payload 类别恢复样本集对象。"""

    normalized = normalize_payload(payload)
    target_cls = _SAMPLE_SET_CATEGORY_MAP.get(normalized.category)
    if target_cls is None:
        raise ValueError(f"不支持的样本集类别: {normalized.category}")
    return target_cls.from_structured_payload(normalized)


__all__ = ["sample_from_structured_payload", "sample_set_from_structured_payload"]
