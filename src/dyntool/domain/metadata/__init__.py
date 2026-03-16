"""领域层元数据模型与结构化恢复入口。"""

from __future__ import annotations

from .base import MetadataBase, MetadataIDGenerator
from .normalization import denormalize_flat_dict, dump_extra, normalize_extra
from .registry import metadata_from_structured_payload
from .schema import MetadataSchema
from .types import (
    Metadata,
    VibrationTestMetadata,
)

__all__ = [
    "MetadataIDGenerator",
    "normalize_extra",
    "dump_extra",
    "denormalize_flat_dict",
    "MetadataBase",
    "Metadata",
    "VibrationTestMetadata",
    "metadata_from_structured_payload",
    "MetadataSchema",
]
