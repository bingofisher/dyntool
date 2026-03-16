"""具体元数据类型。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, ClassVar

import pandas as pd
from pydantic import Field, field_validator, model_validator

from .base import MetadataBase, MetadataIDGenerator
from .normalization import dump_extra, normalize_extra
from .schema import MetadataSchema


class Metadata(MetadataBase):
    """通用元数据。"""

    payload_domain: ClassVar[str] = "default"
    metadata_schema: ClassVar[MetadataSchema] = MetadataSchema(name="generic_metadata")

    identity: dict[str, Any] = Field(default_factory=dict, description="身份字段")
    attributes: dict[str, Any] = Field(default_factory=dict, description="属性字段")
    extra: dict[str, Any] | None = Field(default=None, description="附加元数据")

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy_payload(cls, data: Any) -> Any:
        """将旧风格 payload 收敛到 identity/attributes/extra。"""

        if not isinstance(data, dict):
            return data
        payload = dict(data)
        payload.pop("uid", None)
        payload.pop("schema_name", None)
        payload.pop("schema_version", None)
        explicit_identity = payload.pop("identity", None)
        explicit_attributes = payload.pop("attributes", None)
        explicit_extra = payload.pop("extra", None)

        identity = dict(explicit_identity or {})
        attributes = dict(explicit_attributes or {})
        extra = normalize_extra(explicit_extra)

        if payload:
            attributes = {**attributes, **payload}

        migrated: dict[str, Any] = {
            "identity": identity,
            "attributes": attributes,
        }
        if extra is not None:
            migrated["extra"] = extra
        return migrated

    @field_validator("extra", mode="before")
    @classmethod
    def validate_extra(cls, value: Any) -> dict[str, Any] | None:
        """规范化通用元数据的 extra 字段。"""

        return normalize_extra(value)

    def generate_uid(self) -> str:
        """生成 UID。"""

        base_payload = self.identity or self.attributes or (self.extra if self.extra is not None else {})
        return MetadataIDGenerator.quick_id(
            {
                "schema_name": self.schema_name,
                "schema_version": self.schema_version,
                "identity": base_payload,
            }
        )

    def identity_payload(self) -> dict[str, Any]:
        """返回用于生成 UID 的身份字段。"""

        return dict(self.identity)

    def attribute_payload(self) -> dict[str, Any]:
        """返回通用元数据的属性字段。"""

        return dict(self.attributes)

    def to_sqldict(self) -> dict[str, Any]:
        """导出 SQL 友好字典。"""

        payload = self.model_dump()
        payload["extra"] = dump_extra(payload["extra"])
        return payload


class VibrationTestMetadata(MetadataBase):
    """振动试验元数据。"""

    payload_domain: ClassVar[str] = "vibration_test"
    metadata_schema: ClassVar[MetadataSchema] = MetadataSchema(
        name="vibration_test_metadata",
        identity_fields=("case", "point", "instr", "dir", "record", "timestamp"),
    )
    timestamp_formats: ClassVar[list[str]] = [
        "%Y%m%d%H%M%S",
        "%Y%m%dT%H%M%S",
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y/%m/%d %H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S",
        "%Y/%m/%d %H:%M:%S",
    ]

    case: str = Field(..., description="试验工况标识")
    point: str = Field(..., description="测点标识")
    instr: str = Field(..., description="仪器标识")
    dir: str = Field(..., description="测量方向")
    record: str = Field(..., description="记录编号")
    timestamp: datetime = Field(..., description="采样时间")
    extra: dict[str, Any] | None = Field(default=None, description="附加元数据")

    @field_validator("case", "point", "instr", "dir", "record", mode="before")
    @classmethod
    def validate_non_empty_str(cls, value: Any) -> str:
        """校验字符串字段。"""

        if isinstance(value, int):
            value = str(value)
        if not isinstance(value, str) or not value.strip():
            raise ValueError("字段值必须是非空字符串")
        return value.strip()

    @field_validator("timestamp", mode="before")
    @classmethod
    def validate_timestamp(cls, value: Any) -> datetime:
        """校验并规范时间字段。"""

        if isinstance(value, int):
            value = str(value)
        if isinstance(value, str):
            for fmt in cls.timestamp_formats:
                try:
                    return datetime.strptime(value, fmt)
                except ValueError:
                    continue
            raise ValueError(f"timestamp 字符串不匹配已知格式: {cls.timestamp_formats}")
        if isinstance(value, pd.Timestamp):
            return value.to_pydatetime()
        if not isinstance(value, datetime):
            raise TypeError("timestamp 必须是 datetime 或受支持的时间字符串")
        return value

    @field_validator("extra", mode="before")
    @classmethod
    def validate_extra(cls, value: Any) -> dict[str, Any] | None:
        """规范化振动试验元数据的 extra 字段。"""

        return normalize_extra(value)

    def generate_uid(self) -> str:
        """生成 UID。"""

        return MetadataIDGenerator.quick_id(
            {
                "schema_name": self.schema_name,
                "schema_version": self.schema_version,
                "identity": self.identity_payload(),
            }
        )

    def identity_payload(self) -> dict[str, Any]:
        """返回振动试验元数据的身份字段。"""

        return {
            "case": self.case,
            "point": self.point,
            "instr": self.instr,
            "dir": self.dir,
            "record": self.record,
            "timestamp": self.timestamp,
        }

    def attribute_payload(self) -> dict[str, Any]:
        """返回振动试验元数据的属性字段。"""

        return {}

    def to_sqldict(self) -> dict[str, Any]:
        """导出 SQL 友好字典。"""

        payload = self.model_dump()
        payload["extra"] = dump_extra(payload["extra"])
        return payload


__all__ = ["Metadata", "VibrationTestMetadata"]
