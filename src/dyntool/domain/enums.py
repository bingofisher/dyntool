"""领域层通用枚举定义。"""

from __future__ import annotations

from enum import StrEnum


class SampleDomain(StrEnum):
    """样本领域类型枚举。

    枚举值说明:
        - ``DEFAULT``: 默认样本领域，使用基础样本/样本集类型和通用工作流。
        - ``VIBRATION_TEST``: 振动试验领域，使用振动试验专用元数据、样本模型和评价流程。

    影响:
        该枚举会影响样本工厂选择的 ``DefaultSample``/``DefaultSampleSet`` 具体类型、默认元数据类型，
        以及 ``from_storage``、评价工作流和公开 API 中的领域分派行为。
    """

    DEFAULT = "default"
    VIBRATION_TEST = "vibration_test"


__all__ = ["SampleDomain"]
