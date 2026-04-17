"""`SET_SQLITE_H5` 内部共享的行模型、artifact 与常量。"""

from __future__ import annotations

from dataclasses import dataclass, field

_SQLITE_H5_LOCK_TIMEOUT_SECONDS = 15.0
_SQLITE_H5_WRITE_FLUSH_BATCH_SIZE = 64
_SQLITE_H5_SCHEMA_VERSION_V1 = 1
_SQLITE_H5_SCHEMA_VERSION_V2 = 2


@dataclass(slots=True)
class _SqliteSampleRow:
    sample_id: int
    uid: str
    alias: str
    payload_id: str
    metadata_json: str
    created_at: str
    updated_at: str


@dataclass(slots=True)
class _SqlitePresenceRow:
    slot_name: str
    exists_flag: bool
    model_type: str | None
    data_category: str | None
    h5_path: str
    updated_at: str


@dataclass(slots=True)
class _SqliteSampleUpsertArtifact:
    uid: str
    alias: str
    payload_id: str
    metadata_json: str
    timestamp: str


@dataclass(slots=True)
class _SqliteMetadataArtifact:
    key: str
    value_text: str | None
    value_int: int | None
    value_real: float | None
    value_bool: int | None
    value_json: str | None


@dataclass(slots=True)
class _SqlitePresenceArtifact:
    slot_name: str
    exists_flag: int
    model_type: str | None
    data_category: str | None
    h5_path: str
    updated_at: str


@dataclass(slots=True)
class _SqliteSummaryArtifact:
    key: str
    value_real: float | None
    value_text: str | None
    unit: str | None
    updated_at: str


@dataclass(slots=True)
class _SqliteTransferArtifact:
    sample_row: _SqliteSampleUpsertArtifact
    metadata_rows: list[_SqliteMetadataArtifact]
    presence_rows: list[_SqlitePresenceArtifact]
    summary_rows: list[_SqliteSummaryArtifact]


@dataclass(slots=True)
class _SqliteFlushResult:
    sample_seconds: float = 0.0
    metadata_seconds: float = 0.0
    presence_seconds: float = 0.0
    summary_seconds: float = 0.0
    sample_rows_by_uid: dict[str, _SqliteSampleRow] = field(default_factory=dict)
    presence_rows_by_uid: dict[str, dict[str, _SqlitePresenceRow]] = field(default_factory=dict)


@dataclass(slots=True)
class _SqliteWriteMetrics:
    sample_count: int = 0
    flush_count: int = 0
    artifact_seconds: float = 0.0
    payload_seconds: float = 0.0
    sample_seconds: float = 0.0
    metadata_seconds: float = 0.0
    presence_seconds: float = 0.0
    summary_seconds: float = 0.0
    refresh_cache_seconds: float = 0.0


__all__ = [
    "_SQLITE_H5_LOCK_TIMEOUT_SECONDS",
    "_SQLITE_H5_SCHEMA_VERSION_V1",
    "_SQLITE_H5_SCHEMA_VERSION_V2",
    "_SQLITE_H5_WRITE_FLUSH_BATCH_SIZE",
    "_SqliteMetadataArtifact",
    "_SqliteFlushResult",
    "_SqlitePresenceArtifact",
    "_SqlitePresenceRow",
    "_SqliteSampleRow",
    "_SqliteSampleUpsertArtifact",
    "_SqliteSummaryArtifact",
    "_SqliteTransferArtifact",
    "_SqliteWriteMetrics",
]
