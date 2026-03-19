"""具体元数据类型。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, ClassVar, Self

import pandas as pd
from pydantic import Field, field_validator, model_validator

from .base import MetadataBase, MetadataIDGenerator
from .normalization import dump_extra, normalize_extra
from .schema import MetadataSchema


class Metadata(MetadataBase):
    """通用元数据。

    该类型用于承载不具备固定业务字段结构的 metadata。
    `identity` 用于参与 UID 计算，`attributes` 用于保存常规说明字段，
    `extra` 用于保存不参与标准 identity 的附加业务信息。
    """

    payload_domain: ClassVar[str] = "default"
    metadata_schema: ClassVar[MetadataSchema] = MetadataSchema(name="generic_metadata")

    identity: dict[str, Any] = Field(
        default_factory=dict,
        description="身份字段映射，用于参与 UID 计算并区分不同业务对象。",
    )
    attributes: dict[str, Any] = Field(
        default_factory=dict,
        description="属性字段映射，用于保存不直接参与 UID 计算的常规业务说明。",
    )
    extra: dict[str, Any] | None = Field(
        default=None,
        description="附加业务信息映射，用于保留扩展描述、导出标签或来源信息。",
    )

    @model_validator(mode="before")
    @classmethod
    def _normalize_input_payload(cls, data: Any) -> Any:
        """将输入 payload 统一收敛到 identity/attributes/extra。"""

        if not isinstance(data, dict):
            return data
        payload = dict(data)
        payload.pop("uid", None)
        payload.pop("alias", None)
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
    """振动试验元数据。

    该类型用于描述 VibTest 主线样本的业务身份字段，并负责标准 alias
    `C-{case}_R-{record}_P-{point}_I-{instr}_T-{timestamp:%Y%m%d%H%M%S}_D-{dir}`
    的生成与反构建。`case`、`point`、`instr`、`dir`、`record` 与
    `timestamp` 都参与标准 UID 计算；`extra` 仅用于附加说明与导出，不参与
    标准 identity。
    """

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

    case: str = Field(
        ...,
        description="工况编号，用于区分不同加载工况或试验场景，是 VibTest 标准 alias 与 UID 的组成字段。",
    )
    point: str = Field(
        ...,
        description="测点编号，表示传感器或观测位置，是 VibTest 标准 alias 与 UID 的组成字段。",
    )
    instr: str = Field(
        ...,
        description="仪器编号，表示采集通道或设备标识，是 VibTest 标准 alias 与 UID 的组成字段。",
    )
    dir: str = Field(
        ...,
        description="方向编号，表示测量方向或轴向标识，是 VibTest 标准 alias 与 UID 的组成字段。",
    )
    record: str = Field(
        ...,
        description="记录编号，表示同一工况下的记录序号，是 VibTest 标准 alias 与 UID 的组成字段。",
    )
    timestamp: datetime = Field(
        ...,
        description="采样开始时间或记录时间戳，是 VibTest 标准 alias 与 UID 的组成字段；alias 中使用 `T-YYYYmmddHHMMSS` 格式。",
    )
    extra: dict[str, Any] | None = Field(
        default=None,
        description="附加业务信息，不参与标准 identity，但参与附加描述、导出和上下文补充。",
    )

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

    def build_alias(self) -> str:
        """构建 VibTest 标准业务 alias。"""

        return (
            f"C-{self.case}_R-{self.record}_P-{self.point}_I-{self.instr}_T-{self.timestamp:%Y%m%d%H%M%S}_D-{self.dir}"
        )

    @classmethod
    def from_alias(cls, alias: str) -> Self:
        """根据 VibTest 标准 alias 反构建元数据对象。"""

        parts = [part.strip() for part in alias.split("_") if part.strip()]
        if len(parts) != 6:
            raise ValueError(f"VibTest alias 片段数量错误，应为 6 段: {alias}")
        payload: dict[str, str] = {}
        expected_keys = {
            "C": "case",
            "R": "record",
            "P": "point",
            "I": "instr",
            "T": "timestamp",
            "D": "dir",
        }
        for part in parts:
            if "-" not in part:
                raise ValueError(f"VibTest alias 片段缺少 '-' 分隔符: {part}")
            prefix, value = part.split("-", 1)
            key = prefix.strip()
            if key not in expected_keys:
                raise ValueError(f"VibTest alias 包含未知片段前缀: {key}")
            if not value.strip():
                raise ValueError(f"VibTest alias 片段值不能为空: {part}")
            mapped_key = expected_keys[key]
            if mapped_key in payload:
                raise ValueError(f"VibTest alias 存在重复片段: {key}")
            payload[mapped_key] = value.strip()
        missing = [field for field in expected_keys.values() if field not in payload]
        if missing:
            raise ValueError(f"VibTest alias 缺少必要片段: {missing}")
        try:
            timestamp = datetime.strptime(payload["timestamp"], "%Y%m%d%H%M%S")
        except ValueError as exc:
            raise ValueError(f"VibTest alias 时间格式错误: {payload['timestamp']}") from exc
        return cls(
            case=payload["case"],
            record=payload["record"],
            point=payload["point"],
            instr=payload["instr"],
            timestamp=timestamp,
            dir=payload["dir"],
        )

    def refresh_alias(self, *, force: bool = False) -> str:
        """显式重建 VibTest 标准 alias。"""

        del force
        return self.build_alias()

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
