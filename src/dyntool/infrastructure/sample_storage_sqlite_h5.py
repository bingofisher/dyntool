"""`SET_SQLITE_H5` 存储策略实现。"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from time import perf_counter
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import uuid4

import h5py
import numpy as np
import pandas as pd

from .sample_storage_context import StorageContext
from .sample_storage_strategy_base import _StorageReadSession, _StorageStrategy, _StorageWriteSession
from .storage_constants import H5_ATTR_UNIT
from ..storage.types import StorageScheme

if TYPE_CHECKING:
    from ..domain.samples.base import SampleBaseModel


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


_SQLITE_H5_LOCK_TIMEOUT_SECONDS = 15.0
_SQLITE_H5_WRITE_FLUSH_BATCH_SIZE = 64
_SQLITE_H5_SCHEMA_VERSION_V1 = 1
_SQLITE_H5_SCHEMA_VERSION_V2 = 2


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


class _SetSqliteH5Strategy(_StorageStrategy):
    """基于 SQLite 索引与 H5 payload 的样本集存储策略。"""

    def __init__(self, ctx: Any) -> None:
        super().__init__(ctx)
        self._sample_rows_by_uid: dict[str, _SqliteSampleRow] = {}
        self._presence_rows_by_uid: dict[str, dict[str, _SqlitePresenceRow]] = {}
        self._last_write_metrics: _SqliteWriteMetrics | None = None

    def prepare_layout(self) -> None:
        self.ctx.base_dir.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            self._ensure_schema(conn)
        payload_path = self.ctx.sqlite_payload_h5_path()
        if payload_path.exists():
            return
        with h5py.File(payload_path, "a") as h5_file:
            h5_file.require_group("samples")

    def uid_name_index(self) -> dict[str, str]:
        self._refresh_cache()
        return {uid: uid for uid in self._sample_rows_by_uid}

    def save_sample(self, sample: SampleBaseModel, categories: list[str] | None = None) -> None:
        with self.write_session() as session:
            session.save_sample(sample, categories)
        self._refresh_cache()

    def load_sample(
        self,
        uid: str,
        name: str,
        categories: list[str] | None = None,
    ) -> SampleBaseModel:
        del name
        return self._load_sample_from_resources(uid, categories=categories)

    def load_sample_fields(
        self,
        uid: str,
        name: str,
        categories: list[str],
    ) -> dict[str, object]:
        del name
        return self._load_sample_fields_from_resources(uid, categories=categories)

    def load_many_sample_fields(
        self,
        items: list[tuple[str, str]],
        categories: list[str],
    ) -> dict[str, dict[str, object]]:
        loaded: dict[str, dict[str, object]] = {uid: {} for uid, _ in items}
        if not categories or not items:
            return loaded

        selected = self.resolve_load_categories(categories)
        path_groups: dict[str, list[tuple[str, str]]] = {}
        for uid, _ in items:
            presence_rows = self._presence_rows(uid)
            for category in selected:
                row_info = presence_rows.get(category)
                if row_info is None or not row_info.exists_flag:
                    continue
                path_groups.setdefault(row_info.h5_path, []).append((uid, category))

        with h5py.File(self.ctx.sqlite_payload_h5_path(), "r") as h5_file:
            for h5_path, refs in path_groups.items():
                payload = self._read_payload_path(h5_file, h5_path)
                for uid, category in refs:
                    loaded[uid][category] = self.ctx.deserialize_container(category, payload)
        return loaded

    def sample_presence(
        self,
        uid: str,
        name: str,
    ) -> dict[str, bool]:
        del name
        presence_rows = self._presence_rows(uid)
        return {
            category: bool(presence_rows.get(category).exists_flag) if category in presence_rows else False
            for category in self.ctx.category_fields()
        }

    def summary_frame(
        self,
        *,
        uids: list[str] | None = None,
        metadata_fields: list[str] | None = None,
        data_vars: list[str] | None = None,
        features: list[str] | None = None,
    ) -> pd.DataFrame:
        target_uids = list(uids or self.uid_name_index().keys())
        if not target_uids:
            return pd.DataFrame()

        requested_metadata = [str(field) for field in metadata_fields or ()]
        requested_features = [str(feature) for feature in features or ()]
        requested_data_vars = [str(data_var) for data_var in data_vars or ()]

        with self._connect() as conn:
            self._ensure_schema(conn)
            placeholders = ", ".join("?" for _ in target_uids)
            sample_rows = conn.execute(
                f"""
                SELECT sample_id, uid, alias, metadata_json
                FROM sample
                WHERE uid IN ({placeholders})
                ORDER BY sample_id
                """,
                target_uids,
            ).fetchall()

            sample_ids = [int(row["sample_id"]) for row in sample_rows]
            id_to_uid = {int(row["sample_id"]): str(row["uid"]) for row in sample_rows}
            rows: dict[str, dict[str, Any]] = {
                str(row["uid"]): {"uid": str(row["uid"]), "alias": str(row["alias"])} for row in sample_rows
            }

            if requested_metadata and sample_ids:
                metadata_by_uid = self._flatten_metadata_rows(sample_rows)
                for uid, flattened in metadata_by_uid.items():
                    target_row = rows[uid]
                    for field_name in requested_metadata:
                        if field_name in flattened:
                            target_row[field_name] = flattened[field_name]

            if (requested_features or requested_data_vars) and sample_ids:
                sample_id_placeholders = ", ".join("?" for _ in sample_ids)
                projection_rows = conn.execute(
                    f"""
                    SELECT sample_id, key, value_real, value_text
                    FROM sample_summary_projection
                    WHERE sample_id IN ({sample_id_placeholders})
                    ORDER BY sample_id, key
                    """,
                    sample_ids,
                ).fetchall()
                for row in projection_rows:
                    key = str(row["key"])
                    if key not in requested_features and not any(
                        key.startswith(f"{data_var}.") for data_var in requested_data_vars
                    ):
                        continue
                    uid = id_to_uid[int(row["sample_id"])]
                    rows[uid][key] = float(row["value_real"]) if row["value_real"] is not None else row["value_text"]

        ordered_rows = [rows.setdefault(uid, {"uid": uid, "alias": ""}) for uid in target_uids]
        return pd.DataFrame(ordered_rows)

    def organize(self, valid_uids: set[str]) -> int:
        removed = 0
        with self._connect() as conn:
            self._ensure_schema(conn)
            rows = conn.execute("SELECT uid, payload_id FROM sample").fetchall()
            stale_rows = [
                (str(row["uid"]), str(row["payload_id"])) for row in rows if str(row["uid"]) not in valid_uids
            ]
            for uid, _ in stale_rows:
                conn.execute("DELETE FROM sample WHERE uid = ?", (uid,))
            conn.commit()

        if stale_rows:
            with h5py.File(self.ctx.sqlite_payload_h5_path(), "a") as h5_file:
                samples_group = h5_file.require_group("samples")
                for _, payload_id in stale_rows:
                    if payload_id in samples_group:
                        del samples_group[payload_id]
                        removed += 1

        self._refresh_cache()
        return removed

    def metadata_frame(self, *, uids: list[str] | None = None) -> pd.DataFrame:
        """直接从 SQLite 元数据表构建 metadata 表。"""

        target_uids = list(uids or self.uid_name_index().keys())
        if not target_uids:
            return pd.DataFrame()

        with self._connect() as conn:
            self._ensure_schema(conn)
            placeholders = ", ".join("?" for _ in target_uids)
            rows = conn.execute(
                f"""
                SELECT sample_id, uid, metadata_json
                FROM sample
                WHERE uid IN ({placeholders})
                ORDER BY sample_id
                """,
                target_uids,
            ).fetchall()

        bucket = self._flatten_metadata_rows(rows)
        return pd.DataFrame([bucket.get(uid, {}) for uid in target_uids])

    def write_session(self) -> _StorageWriteSession:
        return _SetSqliteH5WriteSession(self)

    def read_session(self) -> _StorageReadSession:
        return _SetSqliteH5ReadSession(self)

    def _connect(
        self,
        *,
        timeout: float = _SQLITE_H5_LOCK_TIMEOUT_SECONDS,
        isolation_level: str | None = "",
    ) -> sqlite3.Connection:
        conn = sqlite3.connect(
            self.ctx.sqlite_index_path(),
            timeout=timeout,
            isolation_level=isolation_level,
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute(f"PRAGMA busy_timeout = {int(timeout * 1000)}")
        return conn

    @staticmethod
    def _begin_reader_transaction(conn: sqlite3.Connection) -> None:
        conn.execute("BEGIN")
        conn.execute("SELECT 1 FROM sample LIMIT 1").fetchone()

    @staticmethod
    def _begin_writer_transaction(conn: sqlite3.Connection) -> None:
        conn.execute("BEGIN EXCLUSIVE")

    def _ensure_schema(self, conn: sqlite3.Connection) -> None:
        table_names = self._table_names(conn)
        version = self._schema_version(conn)
        if version >= _SQLITE_H5_SCHEMA_VERSION_V2:
            self._ensure_v2_schema_objects(conn)
            if "sample_metadata_flat" in table_names:
                self._drop_v1_metadata_flat(conn)
            if version != _SQLITE_H5_SCHEMA_VERSION_V2:
                self._set_schema_version(conn, _SQLITE_H5_SCHEMA_VERSION_V2)
            return
        if "sample" in table_names and "sample_metadata_flat" in table_names:
            self._migrate_v1_to_v2(conn)
            return
        self._ensure_v2_schema_objects(conn)
        self._set_schema_version(conn, _SQLITE_H5_SCHEMA_VERSION_V2)

    @staticmethod
    def _schema_version(conn: sqlite3.Connection) -> int:
        return int(conn.execute("PRAGMA user_version").fetchone()[0])

    @staticmethod
    def _set_schema_version(conn: sqlite3.Connection, version: int) -> None:
        conn.execute(f"PRAGMA user_version = {int(version)}")

    @staticmethod
    def _table_names(conn: sqlite3.Connection) -> set[str]:
        rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        return {str(row["name"]) for row in rows}

    def _ensure_v2_schema_objects(self, conn: sqlite3.Connection) -> None:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS sample (
                sample_id INTEGER PRIMARY KEY AUTOINCREMENT,
                uid TEXT NOT NULL UNIQUE,
                alias TEXT NOT NULL,
                payload_id TEXT NOT NULL UNIQUE,
                metadata_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sample_slot_presence (
                sample_id INTEGER NOT NULL,
                slot_name TEXT NOT NULL,
                exists_flag INTEGER NOT NULL,
                model_type TEXT,
                data_category TEXT,
                h5_path TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (sample_id, slot_name),
                FOREIGN KEY (sample_id) REFERENCES sample(sample_id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_sample_slot_presence_slot
                ON sample_slot_presence (slot_name, exists_flag);
            CREATE TABLE IF NOT EXISTS sample_summary_projection (
                sample_id INTEGER NOT NULL,
                key TEXT NOT NULL,
                value_real REAL,
                value_text TEXT,
                unit TEXT,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (sample_id, key),
                FOREIGN KEY (sample_id) REFERENCES sample(sample_id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_sample_summary_projection_real
                ON sample_summary_projection (key, value_real);
            """
        )

    def _migrate_v1_to_v2(self, conn: sqlite3.Connection) -> None:
        rows = conn.execute("SELECT sample_id, metadata_json FROM sample ORDER BY sample_id").fetchall()
        for row in rows:
            metadata_json = row["metadata_json"]
            try:
                json.loads(str(metadata_json))
            except Exception as exc:  # noqa: BLE001
                raise RuntimeError(f"SET_SQLITE_H5 v1 -> v2 迁移失败，metadata_json 无法解析: {exc}") from exc
        self._drop_v1_metadata_flat(conn)
        self._ensure_v2_schema_objects(conn)
        self._set_schema_version(conn, _SQLITE_H5_SCHEMA_VERSION_V2)

    @staticmethod
    def _drop_v1_metadata_flat(conn: sqlite3.Connection) -> None:
        conn.executescript(
            """
            DROP INDEX IF EXISTS idx_sample_metadata_flat_text;
            DROP INDEX IF EXISTS idx_sample_metadata_flat_int;
            DROP INDEX IF EXISTS idx_sample_metadata_flat_real;
            DROP TABLE IF EXISTS sample_metadata_flat;
            """
        )

    def _refresh_cache(self) -> None:
        with self._connect() as conn:
            self._ensure_schema(conn)
            sample_rows = conn.execute(
                """
                SELECT sample_id, uid, alias, payload_id, metadata_json, created_at, updated_at
                FROM sample
                ORDER BY sample_id
                """
            ).fetchall()
            presence_rows = conn.execute(
                """
                SELECT s.uid, p.slot_name, p.exists_flag, p.model_type, p.data_category, p.h5_path, p.updated_at
                FROM sample_slot_presence AS p
                JOIN sample AS s ON s.sample_id = p.sample_id
                ORDER BY p.sample_id, p.slot_name
                """
            ).fetchall()

        self._sample_rows_by_uid = {
            str(row["uid"]): _SqliteSampleRow(
                sample_id=int(row["sample_id"]),
                uid=str(row["uid"]),
                alias=str(row["alias"]),
                payload_id=str(row["payload_id"]),
                metadata_json=str(row["metadata_json"]),
                created_at=str(row["created_at"]),
                updated_at=str(row["updated_at"]),
            )
            for row in sample_rows
        }
        self._presence_rows_by_uid = {uid: {} for uid in self._sample_rows_by_uid}
        for row in presence_rows:
            uid = str(row["uid"])
            self._presence_rows_by_uid.setdefault(uid, {})[str(row["slot_name"])] = _SqlitePresenceRow(
                slot_name=str(row["slot_name"]),
                exists_flag=bool(row["exists_flag"]),
                model_type=str(row["model_type"]) if row["model_type"] is not None else None,
                data_category=str(row["data_category"]) if row["data_category"] is not None else None,
                h5_path=str(row["h5_path"]),
                updated_at=str(row["updated_at"]),
            )

    def _resolve_payload_id(
        self,
        sample: SampleBaseModel,
        *,
        conn: sqlite3.Connection | None = None,
    ) -> str:
        cached_payload_id = getattr(sample, "_storage_payload_id", None)
        if isinstance(cached_payload_id, str) and cached_payload_id:
            return cached_payload_id
        if conn is not None:
            row = conn.execute(
                """
                SELECT payload_id
                FROM sample
                WHERE uid = ?
                LIMIT 1
                """,
                (sample.uid,),
            ).fetchone()
            if row is not None and row["payload_id"] is not None:
                return str(row["payload_id"])
            return uuid4().hex
        row = self._sample_row(sample.uid)
        if row is not None:
            return row.payload_id
        return uuid4().hex

    def _save_sample_with_handles(
        self,
        sample: SampleBaseModel,
        *,
        categories: list[str] | None,
        conn: sqlite3.Connection,
        h5_file: h5py.File,
        commit: bool = True,
    ) -> str:
        artifact, data_dict = self._build_transfer_artifact(sample, categories=categories, conn=conn)
        self._write_payload(
            artifact.sample_row.payload_id,
            sample,
            data_dict,
            artifact.sample_row.timestamp,
            h5_file=h5_file,
        )
        self._flush_transfer_artifacts(conn, [artifact])
        if commit:
            conn.commit()
        sample._storage_payload_id = artifact.sample_row.payload_id
        return artifact.sample_row.payload_id

    def _build_transfer_artifact(
        self,
        sample: SampleBaseModel,
        *,
        categories: list[str] | None,
        conn: sqlite3.Connection,
    ) -> tuple[_SqliteTransferArtifact, dict[str, Any]]:
        data_dict = self.ctx.sample_data_dict(sample, categories)
        payload_id = self._resolve_payload_id(sample, conn=conn)
        timestamp = self._now_text()
        metadata_json = json.dumps(sample.metadata.model_dump(), ensure_ascii=False, default=str)

        presence_rows = [
            _SqlitePresenceArtifact(
                slot_name=slot_name,
                exists_flag=1,
                model_type=data.__class__.__name__,
                data_category=self.ctx.sampleset.sample_schema.category(slot_name).value,
                h5_path=f"/samples/{payload_id}/slots/{slot_name}",
                updated_at=timestamp,
            )
            for slot_name, data in data_dict.items()
        ]

        summary_rows = [
            _SqliteSummaryArtifact(
                key=key,
                value_real=payload.get("value_real"),
                value_text=payload.get("value_text"),
                unit=payload.get("unit"),
                updated_at=timestamp,
            )
            for key, payload in self._build_summary_rows(data_dict).items()
        ]

        return (
            _SqliteTransferArtifact(
                sample_row=_SqliteSampleUpsertArtifact(
                    uid=sample.uid,
                    alias=sample.alias,
                    payload_id=payload_id,
                    metadata_json=metadata_json,
                    timestamp=timestamp,
                ),
                metadata_rows=[],
                presence_rows=presence_rows,
                summary_rows=summary_rows,
            ),
            data_dict,
        )

    def _flush_transfer_artifacts(
        self,
        conn: sqlite3.Connection,
        artifacts: list[_SqliteTransferArtifact],
    ) -> dict[str, float]:
        if not artifacts:
            return {
                "sample_seconds": 0.0,
                "metadata_seconds": 0.0,
                "presence_seconds": 0.0,
                "summary_seconds": 0.0,
            }
        self._ensure_schema(conn)
        sample_started = perf_counter()
        sample_ids = self._batch_upsert_sample_rows(conn, artifacts)
        sample_seconds = perf_counter() - sample_started
        target_sample_ids = list(sample_ids.values())
        metadata_started = perf_counter()
        metadata_seconds = perf_counter() - metadata_started
        presence_started = perf_counter()
        self._delete_sample_projection_rows(conn, table="sample_slot_presence", sample_ids=target_sample_ids)
        self._insert_presence_artifacts(conn, sample_ids=sample_ids, artifacts=artifacts)
        presence_seconds = perf_counter() - presence_started
        summary_started = perf_counter()
        self._delete_sample_projection_rows(conn, table="sample_summary_projection", sample_ids=target_sample_ids)
        self._insert_summary_artifacts(conn, sample_ids=sample_ids, artifacts=artifacts)
        summary_seconds = perf_counter() - summary_started
        return {
            "sample_seconds": sample_seconds,
            "metadata_seconds": metadata_seconds,
            "presence_seconds": presence_seconds,
            "summary_seconds": summary_seconds,
        }

    def _batch_upsert_sample_rows(
        self,
        conn: sqlite3.Connection,
        artifacts: list[_SqliteTransferArtifact],
    ) -> dict[str, int]:
        if not artifacts:
            return {}
        uids = [artifact.sample_row.uid for artifact in artifacts]
        payload_ids = [artifact.sample_row.payload_id for artifact in artifacts]
        uid_placeholders = ", ".join("?" for _ in uids)
        payload_placeholders = ", ".join("?" for _ in payload_ids)
        existing_rows = conn.execute(
            f"""
            SELECT sample_id, uid, payload_id
            FROM sample
            WHERE uid IN ({uid_placeholders}) OR payload_id IN ({payload_placeholders})
            """,
            [*uids, *payload_ids],
        ).fetchall()
        by_uid = {str(row["uid"]): int(row["sample_id"]) for row in existing_rows}
        by_payload = {str(row["payload_id"]): int(row["sample_id"]) for row in existing_rows}

        insert_rows: list[tuple[str, str, str, str, str, str]] = []
        update_rows: list[tuple[str, str, str, str, str, int]] = []
        for artifact in artifacts:
            sample_row = artifact.sample_row
            sample_id = by_payload.get(sample_row.payload_id) or by_uid.get(sample_row.uid)
            if sample_id is None:
                insert_rows.append(
                    (
                        sample_row.uid,
                        sample_row.alias,
                        sample_row.payload_id,
                        sample_row.metadata_json,
                        sample_row.timestamp,
                        sample_row.timestamp,
                    )
                )
                continue
            update_rows.append(
                (
                    sample_row.uid,
                    sample_row.alias,
                    sample_row.payload_id,
                    sample_row.metadata_json,
                    sample_row.timestamp,
                    sample_id,
                )
            )

        if insert_rows:
            conn.executemany(
                """
                INSERT INTO sample (uid, alias, payload_id, metadata_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                insert_rows,
            )
        if update_rows:
            conn.executemany(
                """
                UPDATE sample
                SET uid = ?, alias = ?, payload_id = ?, metadata_json = ?, updated_at = ?
                WHERE sample_id = ?
                """,
                update_rows,
            )

        sample_rows = conn.execute(
            f"""
            SELECT sample_id, uid
            FROM sample
            WHERE uid IN ({uid_placeholders})
            """,
            uids,
        ).fetchall()
        return {str(row["uid"]): int(row["sample_id"]) for row in sample_rows}

    @staticmethod
    def _delete_sample_projection_rows(
        conn: sqlite3.Connection,
        *,
        table: str,
        sample_ids: list[int],
    ) -> None:
        if not sample_ids:
            return
        placeholders = ", ".join("?" for _ in sample_ids)
        conn.execute(f"DELETE FROM {table} WHERE sample_id IN ({placeholders})", sample_ids)

    def _insert_metadata_artifacts(
        self,
        conn: sqlite3.Connection,
        *,
        sample_ids: dict[str, int],
        artifacts: list[_SqliteTransferArtifact],
    ) -> None:
        rows: list[tuple[int, str, str | None, int | None, float | None, int | None, str | None]] = []
        for artifact in artifacts:
            sample_id = sample_ids[artifact.sample_row.uid]
            rows.extend(
                (
                    sample_id,
                    item.key,
                    item.value_text,
                    item.value_int,
                    item.value_real,
                    item.value_bool,
                    item.value_json,
                )
                for item in artifact.metadata_rows
            )
        if not rows:
            return
        conn.executemany(
            """
            INSERT INTO sample_metadata_flat
                (sample_id, key, value_text, value_int, value_real, value_bool, value_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )

    def _insert_presence_artifacts(
        self,
        conn: sqlite3.Connection,
        *,
        sample_ids: dict[str, int],
        artifacts: list[_SqliteTransferArtifact],
    ) -> None:
        rows: list[tuple[int, str, int, str | None, str | None, str, str]] = []
        for artifact in artifacts:
            sample_id = sample_ids[artifact.sample_row.uid]
            rows.extend(
                (
                    sample_id,
                    item.slot_name,
                    item.exists_flag,
                    item.model_type,
                    item.data_category,
                    item.h5_path,
                    item.updated_at,
                )
                for item in artifact.presence_rows
            )
        if not rows:
            return
        conn.executemany(
            """
            INSERT INTO sample_slot_presence
                (sample_id, slot_name, exists_flag, model_type, data_category, h5_path, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )

    def _insert_summary_artifacts(
        self,
        conn: sqlite3.Connection,
        *,
        sample_ids: dict[str, int],
        artifacts: list[_SqliteTransferArtifact],
    ) -> None:
        rows: list[tuple[int, str, float | None, str | None, str | None, str]] = []
        for artifact in artifacts:
            sample_id = sample_ids[artifact.sample_row.uid]
            rows.extend(
                (
                    sample_id,
                    item.key,
                    item.value_real,
                    item.value_text,
                    item.unit,
                    item.updated_at,
                )
                for item in artifact.summary_rows
            )
        if not rows:
            return
        conn.executemany(
            """
            INSERT INTO sample_summary_projection
                (sample_id, key, value_real, value_text, unit, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            rows,
        )

    def _load_sample_from_resources(
        self,
        uid: str,
        *,
        categories: list[str] | None,
        h5_file: h5py.File | None = None,
    ) -> SampleBaseModel:
        row = self._sample_row(uid)
        if row is None:
            raise FileNotFoundError(f"未找到 UID 对应样本: {uid}")

        sample = self.ctx.sampleset.sample_type(
            metadata=self.ctx.metadata_from_dict(json.loads(row.metadata_json)),
        )
        sample._restore_alias_internal(row.alias)
        sample._storage_payload_id = row.payload_id

        loaded_fields = self._load_sample_fields_from_resources(uid, categories=categories, h5_file=h5_file)
        if loaded_fields:
            sample.update(**loaded_fields)
        return sample

    def _load_sample_fields_from_resources(
        self,
        uid: str,
        *,
        categories: list[str] | None,
        h5_file: h5py.File | None = None,
    ) -> dict[str, object]:
        loaded: dict[str, object] = {}
        selected = self.resolve_load_categories(categories)
        if not selected:
            return loaded
        presence_rows = self._presence_rows(uid)
        if h5_file is None:
            with h5py.File(self.ctx.sqlite_payload_h5_path(), "r") as managed_h5_file:
                return self._load_sample_fields_from_resources(uid, categories=selected, h5_file=managed_h5_file)
        for category in selected:
            row_info = presence_rows.get(category)
            if row_info is None or not row_info.exists_flag:
                continue
            payload = self._read_payload_path(h5_file, row_info.h5_path)
            loaded[category] = self.ctx.deserialize_container(category, payload)
        return loaded

    def _read_payload_path(self, h5_file: h5py.File, h5_path: str) -> dict[str, Any]:
        if h5_path not in h5_file:
            raise FileNotFoundError(f"H5 payload 缺少槽位路径: {h5_path}")
        category_group = h5_file[h5_path]
        if not isinstance(category_group, h5py.Group):
            raise TypeError(f"H5 payload 节点不是 Group: {h5_path}")
        return self._read_group_payload(category_group)

    def _sample_row(self, uid: str) -> _SqliteSampleRow | None:
        if uid in self._sample_rows_by_uid:
            return self._sample_rows_by_uid[uid]
        self._refresh_cache()
        return self._sample_rows_by_uid.get(uid)

    def _presence_rows(self, uid: str) -> dict[str, _SqlitePresenceRow]:
        if uid not in self._presence_rows_by_uid:
            self._refresh_cache()
        return self._presence_rows_by_uid.get(uid, {})

    def _flatten_metadata_rows(self, rows: list[sqlite3.Row]) -> dict[str, dict[str, Any]]:
        flattened_by_uid: dict[str, dict[str, Any]] = {}
        for row in rows:
            uid = str(row["uid"])
            metadata_dict = json.loads(str(row["metadata_json"]))
            metadata = self.ctx.metadata_from_dict(metadata_dict)
            flattened_by_uid[uid] = {str(key): value for key, value in metadata.to_flatten_dict(sep="@").items()}
        return flattened_by_uid

    def _upsert_sample_row(
        self,
        conn: sqlite3.Connection,
        *,
        sample: SampleBaseModel,
        payload_id: str,
        metadata_json: str,
        timestamp: str,
    ) -> int:
        existing = conn.execute(
            """
            SELECT sample_id, created_at
            FROM sample
            WHERE payload_id = ? OR uid = ?
            ORDER BY CASE WHEN payload_id = ? THEN 0 ELSE 1 END
            LIMIT 1
            """,
            (payload_id, sample.uid, payload_id),
        ).fetchone()
        if existing is None:
            cursor = conn.execute(
                """
                INSERT INTO sample (uid, alias, payload_id, metadata_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (sample.uid, sample.alias, payload_id, metadata_json, timestamp, timestamp),
            )
            return int(cursor.lastrowid)

        sample_id = int(existing["sample_id"])
        conn.execute(
            """
            UPDATE sample
            SET uid = ?, alias = ?, payload_id = ?, metadata_json = ?, updated_at = ?
            WHERE sample_id = ?
            """,
            (sample.uid, sample.alias, payload_id, metadata_json, timestamp, sample_id),
        )
        return sample_id

    def _replace_metadata_rows(
        self,
        conn: sqlite3.Connection,
        *,
        sample_id: int,
        metadata: dict[str, Any],
    ) -> None:
        conn.execute("DELETE FROM sample_metadata_flat WHERE sample_id = ?", (sample_id,))
        for key, value in metadata.items():
            row = self._metadata_value_columns(value)
            conn.execute(
                """
                INSERT INTO sample_metadata_flat
                    (sample_id, key, value_text, value_int, value_real, value_bool, value_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    sample_id,
                    str(key),
                    row["value_text"],
                    row["value_int"],
                    row["value_real"],
                    row["value_bool"],
                    row["value_json"],
                ),
            )

    def _replace_presence_rows(
        self,
        conn: sqlite3.Connection,
        *,
        sample_id: int,
        data_dict: dict[str, Any],
        payload_id: str,
        timestamp: str,
    ) -> None:
        conn.execute("DELETE FROM sample_slot_presence WHERE sample_id = ?", (sample_id,))
        for slot_name, data in data_dict.items():
            conn.execute(
                """
                INSERT INTO sample_slot_presence
                    (sample_id, slot_name, exists_flag, model_type, data_category, h5_path, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    sample_id,
                    slot_name,
                    1,
                    data.__class__.__name__,
                    self.ctx.sampleset.sample_schema.category(slot_name).value,
                    f"/samples/{payload_id}/slots/{slot_name}",
                    timestamp,
                ),
            )

    def _replace_summary_rows(
        self,
        conn: sqlite3.Connection,
        *,
        sample_id: int,
        summary_rows: dict[str, dict[str, Any]],
        timestamp: str,
    ) -> None:
        conn.execute("DELETE FROM sample_summary_projection WHERE sample_id = ?", (sample_id,))
        for key, payload in summary_rows.items():
            conn.execute(
                """
                INSERT INTO sample_summary_projection
                    (sample_id, key, value_real, value_text, unit, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    sample_id,
                    key,
                    payload.get("value_real"),
                    payload.get("value_text"),
                    payload.get("unit"),
                    timestamp,
                ),
            )

    def _write_payload(
        self,
        payload_id: str,
        sample: SampleBaseModel,
        data_dict: dict[str, Any],
        timestamp: str,
        *,
        h5_file: h5py.File | None = None,
    ) -> None:
        if h5_file is None:
            with h5py.File(self.ctx.sqlite_payload_h5_path(), "a") as managed_h5_file:
                self._write_payload(payload_id, sample, data_dict, timestamp, h5_file=managed_h5_file)
            return

        samples_group = h5_file.require_group("samples")
        if payload_id in samples_group:
            del samples_group[payload_id]
        sample_group = samples_group.create_group(payload_id)
        sample_group.attrs["payload_id"] = payload_id
        sample_group.attrs["uid_snapshot"] = sample.uid
        sample_group.attrs["alias_snapshot"] = sample.alias
        sample_group.attrs["updated_at"] = timestamp
        slots_group = sample_group.create_group("slots")
        for category, data in data_dict.items():
            self._write_group(slots_group, category, data)

    def _write_group(self, group: h5py.Group, category: str, data: Any) -> None:
        payload = self.ctx.serialize_container(data)
        category_group = group.create_group(category)
        self._write_payload_group(category_group, payload)

    def _write_payload_group(self, group: h5py.Group, payload: dict[str, Any]) -> None:
        units = payload.get("_units", {})
        dataset_options = self.ctx.h5_dataset_options()
        for key, value in payload.items():
            if key == "_units" or value is None:
                continue
            if isinstance(value, dict):
                self._write_payload_group(group.create_group(key), value)
                continue
            array = np.asarray(value)
            if array.dtype == object:
                raise TypeError(f"H5 不支持 object dtype 数据集: {key}")
            effective_dataset_options = {} if array.shape == () else dataset_options
            dataset = group.create_dataset(key, data=array, **effective_dataset_options)
            unit = units.get(key, "")
            if unit:
                dataset.attrs[H5_ATTR_UNIT] = unit

    def _read_group_payload(self, group: h5py.Group) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        units: dict[str, Any] = {}
        for key in group.keys():
            node = group[key]
            if isinstance(node, h5py.Group):
                payload[key] = self._read_group_payload(node)
                continue
            if not isinstance(node, h5py.Dataset):
                continue
            value = node[()]
            if isinstance(value, bytes):
                value = value.decode("utf-8")
            payload[key] = value
            if H5_ATTR_UNIT in node.attrs:
                units[key] = node.attrs[H5_ATTR_UNIT]
        if units:
            payload["_units"] = units
        return payload

    @staticmethod
    def _metadata_value_columns(value: Any) -> dict[str, Any]:
        row = {
            "value_text": None,
            "value_int": None,
            "value_real": None,
            "value_bool": None,
            "value_json": None,
        }
        if value is None:
            return row
        if isinstance(value, bool):
            row["value_bool"] = int(value)
            return row
        if isinstance(value, int):
            row["value_int"] = value
            return row
        if isinstance(value, float):
            row["value_real"] = value
            return row
        if isinstance(value, str):
            row["value_text"] = value
            return row
        row["value_json"] = json.dumps(value, ensure_ascii=False, default=str)
        return row

    @staticmethod
    def _decode_metadata_value(row: sqlite3.Row) -> Any:
        if row["value_text"] is not None:
            return row["value_text"]
        if row["value_int"] is not None:
            return int(row["value_int"])
        if row["value_real"] is not None:
            return float(row["value_real"])
        if row["value_bool"] is not None:
            return bool(row["value_bool"])
        if row["value_json"] is not None:
            return json.loads(str(row["value_json"]))
        return None

    @staticmethod
    def _now_text() -> str:
        return datetime.now().isoformat(timespec="seconds")

    @staticmethod
    def _summary_scalar_row(
        value: float | str | None,
        *,
        unit: str | None = None,
    ) -> dict[str, Any]:
        if value is None:
            return {"value_real": None, "value_text": None, "unit": unit}
        if isinstance(value, (int, float, np.floating, np.integer)):
            return {"value_real": float(value), "value_text": None, "unit": unit}
        return {"value_real": None, "value_text": str(value), "unit": unit}

    def _build_summary_rows(self, data_dict: dict[str, Any]) -> dict[str, dict[str, Any]]:
        rows: dict[str, dict[str, Any]] = {}
        for slot_name, data in data_dict.items():
            if hasattr(data, "to_scalar_record"):
                try:
                    scalar_record = data.to_scalar_record()
                except Exception:  # noqa: BLE001
                    scalar_record = {}
                current_units = data.current_units() if hasattr(data, "current_units") else {}
                if isinstance(scalar_record, dict):
                    for key, value in scalar_record.items():
                        unit = current_units.get(key) if isinstance(current_units, dict) else None
                        rows[f"{slot_name}.{key}"] = self._summary_scalar_row(value, unit=unit)

            if hasattr(data, "sampling_info"):
                try:
                    sampling_info = data.sampling_info()
                except Exception:  # noqa: BLE001
                    sampling_info = {}
                if isinstance(sampling_info, dict):
                    sample_count = sampling_info.get("num_samples")
                    dt = sampling_info.get("dt")
                    start = sampling_info.get("start")
                    end = sampling_info.get("end")
                    if sample_count is not None:
                        rows[f"{slot_name}@sample_count"] = self._summary_scalar_row(sample_count)
                    if dt is not None:
                        rows[f"{slot_name}@dt"] = self._summary_scalar_row(dt, unit="second")
                    if start is not None and end is not None:
                        rows[f"{slot_name}@duration"] = self._summary_scalar_row(
                            float(end) - float(start),
                            unit="second",
                        )

            unit_map = data.current_units() if hasattr(data, "current_units") else {}
            value_unit = unit_map.get("value") if isinstance(unit_map, dict) else None
            if slot_name == "accel" and hasattr(data, "pga"):
                rows["pga"] = self._summary_scalar_row(data.pga(), unit=value_unit)
            if slot_name == "vel" and hasattr(data, "pgv"):
                rows["pgv"] = self._summary_scalar_row(data.pgv(), unit=value_unit)
            if slot_name == "disp" and hasattr(data, "pgd"):
                rows["pgd"] = self._summary_scalar_row(data.pgd(), unit=value_unit)
        return rows


class _LegacySetSqliteH5V1Strategy(_SetSqliteH5Strategy):
    """`SET_SQLITE_H5` 的旧版 v1 兼容策略。

    Stability:
        Private / implementation detail.
    """

    def summary_frame(
        self,
        *,
        uids: list[str] | None = None,
        metadata_fields: list[str] | None = None,
        data_vars: list[str] | None = None,
        features: list[str] | None = None,
    ) -> pd.DataFrame:
        target_uids = list(uids or self.uid_name_index().keys())
        if not target_uids:
            return pd.DataFrame()

        requested_metadata = [str(field) for field in metadata_fields or ()]
        requested_features = [str(feature) for feature in features or ()]
        requested_data_vars = [str(data_var) for data_var in data_vars or ()]

        with self._connect() as conn:
            placeholders = ", ".join("?" for _ in target_uids)
            sample_rows = conn.execute(
                f"""
                SELECT sample_id, uid, alias
                FROM sample
                WHERE uid IN ({placeholders})
                ORDER BY sample_id
                """,
                target_uids,
            ).fetchall()

            sample_ids = [int(row["sample_id"]) for row in sample_rows]
            id_to_uid = {int(row["sample_id"]): str(row["uid"]) for row in sample_rows}
            rows: dict[str, dict[str, Any]] = {
                str(row["uid"]): {"uid": str(row["uid"]), "alias": str(row["alias"])} for row in sample_rows
            }

            if requested_metadata and sample_ids:
                metadata_placeholders = ", ".join("?" for _ in requested_metadata)
                sample_id_placeholders = ", ".join("?" for _ in sample_ids)
                metadata_rows = conn.execute(
                    f"""
                    SELECT sample_id, key, value_text, value_int, value_real, value_bool, value_json
                    FROM sample_metadata_flat
                    WHERE sample_id IN ({sample_id_placeholders})
                      AND key IN ({metadata_placeholders})
                    ORDER BY sample_id, key
                    """,
                    [*sample_ids, *requested_metadata],
                ).fetchall()
                for row in metadata_rows:
                    uid = id_to_uid[int(row["sample_id"])]
                    rows[uid][str(row["key"])] = self._decode_metadata_value(row)

            if (requested_features or requested_data_vars) and sample_ids:
                sample_id_placeholders = ", ".join("?" for _ in sample_ids)
                projection_rows = conn.execute(
                    f"""
                    SELECT sample_id, key, value_real, value_text
                    FROM sample_summary_projection
                    WHERE sample_id IN ({sample_id_placeholders})
                    ORDER BY sample_id, key
                    """,
                    sample_ids,
                ).fetchall()
                for row in projection_rows:
                    key = str(row["key"])
                    if key not in requested_features and not any(
                        key.startswith(f"{data_var}.") for data_var in requested_data_vars
                    ):
                        continue
                    uid = id_to_uid[int(row["sample_id"])]
                    rows[uid][key] = float(row["value_real"]) if row["value_real"] is not None else row["value_text"]

        ordered_rows = [rows.setdefault(uid, {"uid": uid, "alias": ""}) for uid in target_uids]
        return pd.DataFrame(ordered_rows)

    def metadata_frame(self, *, uids: list[str] | None = None) -> pd.DataFrame:
        target_uids = list(uids or self.uid_name_index().keys())
        if not target_uids:
            return pd.DataFrame()

        with self._connect() as conn:
            placeholders = ", ".join("?" for _ in target_uids)
            rows = conn.execute(
                f"""
                SELECT s.uid, m.key, m.value_text, m.value_int, m.value_real, m.value_bool, m.value_json
                FROM sample AS s
                LEFT JOIN sample_metadata_flat AS m
                  ON s.sample_id = m.sample_id
                WHERE s.uid IN ({placeholders})
                ORDER BY s.sample_id, m.key
                """,
                target_uids,
            ).fetchall()

        bucket: dict[str, dict[str, Any]] = {uid: {} for uid in target_uids}
        for row in rows:
            uid = str(row["uid"])
            key = row["key"]
            if key is None:
                continue
            bucket[uid][str(key)] = self._decode_metadata_value(row)
        return pd.DataFrame([bucket[uid] for uid in target_uids if uid in bucket])

    def _ensure_schema(self, conn: sqlite3.Connection) -> None:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS sample (
                sample_id INTEGER PRIMARY KEY AUTOINCREMENT,
                uid TEXT NOT NULL UNIQUE,
                alias TEXT NOT NULL,
                payload_id TEXT NOT NULL UNIQUE,
                metadata_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sample_metadata_flat (
                sample_id INTEGER NOT NULL,
                key TEXT NOT NULL,
                value_text TEXT,
                value_int INTEGER,
                value_real REAL,
                value_bool INTEGER,
                value_json TEXT,
                PRIMARY KEY (sample_id, key),
                FOREIGN KEY (sample_id) REFERENCES sample(sample_id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_sample_metadata_flat_text
                ON sample_metadata_flat (key, value_text);
            CREATE INDEX IF NOT EXISTS idx_sample_metadata_flat_int
                ON sample_metadata_flat (key, value_int);
            CREATE INDEX IF NOT EXISTS idx_sample_metadata_flat_real
                ON sample_metadata_flat (key, value_real);
            CREATE TABLE IF NOT EXISTS sample_slot_presence (
                sample_id INTEGER NOT NULL,
                slot_name TEXT NOT NULL,
                exists_flag INTEGER NOT NULL,
                model_type TEXT,
                data_category TEXT,
                h5_path TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (sample_id, slot_name),
                FOREIGN KEY (sample_id) REFERENCES sample(sample_id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_sample_slot_presence_slot
                ON sample_slot_presence (slot_name, exists_flag);
            CREATE TABLE IF NOT EXISTS sample_summary_projection (
                sample_id INTEGER NOT NULL,
                key TEXT NOT NULL,
                value_real REAL,
                value_text TEXT,
                unit TEXT,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (sample_id, key),
                FOREIGN KEY (sample_id) REFERENCES sample(sample_id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_sample_summary_projection_real
                ON sample_summary_projection (key, value_real);
            """
        )
        if self._schema_version(conn) == 0:
            self._set_schema_version(conn, _SQLITE_H5_SCHEMA_VERSION_V1)

    def _build_transfer_artifact(
        self,
        sample: SampleBaseModel,
        *,
        categories: list[str] | None,
        conn: sqlite3.Connection,
    ) -> tuple[_SqliteTransferArtifact, dict[str, Any]]:
        data_dict = self.ctx.sample_data_dict(sample, categories)
        payload_id = self._resolve_payload_id(sample, conn=conn)
        timestamp = self._now_text()
        metadata_json = json.dumps(sample.metadata.model_dump(), ensure_ascii=False, default=str)

        metadata_rows: list[_SqliteMetadataArtifact] = []
        for key, value in sample.metadata.to_flatten_dict(sep="@").items():
            columns = self._metadata_value_columns(value)
            metadata_rows.append(
                _SqliteMetadataArtifact(
                    key=str(key),
                    value_text=columns["value_text"],
                    value_int=columns["value_int"],
                    value_real=columns["value_real"],
                    value_bool=columns["value_bool"],
                    value_json=columns["value_json"],
                )
            )

        presence_rows = [
            _SqlitePresenceArtifact(
                slot_name=slot_name,
                exists_flag=1,
                model_type=data.__class__.__name__,
                data_category=self.ctx.sampleset.sample_schema.category(slot_name).value,
                h5_path=f"/samples/{payload_id}/slots/{slot_name}",
                updated_at=timestamp,
            )
            for slot_name, data in data_dict.items()
        ]

        summary_rows = [
            _SqliteSummaryArtifact(
                key=key,
                value_real=payload.get("value_real"),
                value_text=payload.get("value_text"),
                unit=payload.get("unit"),
                updated_at=timestamp,
            )
            for key, payload in self._build_summary_rows(data_dict).items()
        ]

        return (
            _SqliteTransferArtifact(
                sample_row=_SqliteSampleUpsertArtifact(
                    uid=sample.uid,
                    alias=sample.alias,
                    payload_id=payload_id,
                    metadata_json=metadata_json,
                    timestamp=timestamp,
                ),
                metadata_rows=metadata_rows,
                presence_rows=presence_rows,
                summary_rows=summary_rows,
            ),
            data_dict,
        )

    def _flush_transfer_artifacts(
        self,
        conn: sqlite3.Connection,
        artifacts: list[_SqliteTransferArtifact],
    ) -> dict[str, float]:
        if not artifacts:
            return {
                "sample_seconds": 0.0,
                "metadata_seconds": 0.0,
                "presence_seconds": 0.0,
                "summary_seconds": 0.0,
            }
        self._ensure_schema(conn)
        sample_started = perf_counter()
        sample_ids = self._batch_upsert_sample_rows(conn, artifacts)
        sample_seconds = perf_counter() - sample_started
        target_sample_ids = list(sample_ids.values())
        metadata_started = perf_counter()
        self._delete_sample_projection_rows(conn, table="sample_metadata_flat", sample_ids=target_sample_ids)
        self._insert_metadata_artifacts(conn, sample_ids=sample_ids, artifacts=artifacts)
        metadata_seconds = perf_counter() - metadata_started
        presence_started = perf_counter()
        self._delete_sample_projection_rows(conn, table="sample_slot_presence", sample_ids=target_sample_ids)
        self._insert_presence_artifacts(conn, sample_ids=sample_ids, artifacts=artifacts)
        presence_seconds = perf_counter() - presence_started
        summary_started = perf_counter()
        self._delete_sample_projection_rows(conn, table="sample_summary_projection", sample_ids=target_sample_ids)
        self._insert_summary_artifacts(conn, sample_ids=sample_ids, artifacts=artifacts)
        summary_seconds = perf_counter() - summary_started
        return {
            "sample_seconds": sample_seconds,
            "metadata_seconds": metadata_seconds,
            "presence_seconds": presence_seconds,
            "summary_seconds": summary_seconds,
        }

    def _flatten_metadata_rows(self, rows: list[sqlite3.Row]) -> dict[str, dict[str, Any]]:
        flattened_by_uid: dict[str, dict[str, Any]] = {}
        for row in rows:
            uid = str(row["uid"])
            metadata_dict = json.loads(str(row["metadata_json"]))
            metadata = self.ctx.metadata_from_dict(metadata_dict)
            flattened_by_uid[uid] = {str(key): value for key, value in metadata.to_flatten_dict(sep="@").items()}
        return flattened_by_uid


def _save_sample_set_legacy_v1(
    sampleset: Any,
    base_dir: str | Path,
    *,
    categories: list[str] | None = None,
) -> _SqliteWriteMetrics:
    """将样本集写入旧版 v1 `SET_SQLITE_H5` 仓库。"""

    target_dir = Path(base_dir).resolve()
    ctx = StorageContext(
        sampleset,
        base_dir=target_dir,
        storage_scheme=StorageScheme.SET_SQLITE_H5,
    )
    strategy = _LegacySetSqliteH5V1Strategy(ctx)
    strategy.prepare_layout()
    with strategy.write_session() as session:
        for sample in sampleset.values():
            session.save_sample(sample, categories)
    return strategy._last_write_metrics or _SqliteWriteMetrics()


def _validate_sample_set_legacy_v1(
    sample_set_type: type[Any],
    base_dir: str | Path,
    *,
    categories: list[str] | None = None,
    metadata_fields: list[str] | None = None,
    data_vars: list[str] | None = None,
    features: list[str] | None = None,
) -> dict[str, Any]:
    """读取旧版 v1 `SET_SQLITE_H5` 仓库并返回最小校验结果。"""

    probe_set = sample_set_type()
    ctx = StorageContext(
        probe_set,
        base_dir=Path(base_dir).resolve(),
        storage_scheme=StorageScheme.SET_SQLITE_H5,
    )
    strategy = _LegacySetSqliteH5V1Strategy(ctx)
    strategy._refresh_cache()
    uids = list(strategy.uid_name_index().keys())
    metadata_frame = strategy.metadata_frame(uids=uids)
    summary_frame = strategy.summary_frame(
        uids=uids,
        metadata_fields=metadata_fields,
        data_vars=data_vars,
        features=features,
    )
    loaded_fields = {uid: strategy._load_sample_fields_from_resources(uid, categories=categories) for uid in uids}
    presence = {uid: strategy.sample_presence(uid, uid) for uid in uids}
    return {
        "sample_count": len(uids),
        "uids": uids,
        "metadata_frame": metadata_frame,
        "summary_frame": summary_frame,
        "loaded_fields": loaded_fields,
        "presence": presence,
    }


def _save_sample_set_experimental_v2(
    sampleset: Any,
    base_dir: str | Path,
    *,
    categories: list[str] | None = None,
) -> _SqliteWriteMetrics:
    """兼容保留的当前 `SET_SQLITE_H5 v2` 写入 helper。

    Stability:
        Private / implementation detail.
    """

    target_dir = Path(base_dir).resolve()
    ctx = StorageContext(
        sampleset,
        base_dir=target_dir,
        storage_scheme=StorageScheme.SET_SQLITE_H5,
    )
    strategy = _SetSqliteH5Strategy(ctx)
    strategy.prepare_layout()
    with strategy.write_session() as session:
        for sample in sampleset.values():
            session.save_sample(sample, categories)
    return strategy._last_write_metrics or _SqliteWriteMetrics()


def _validate_sample_set_experimental_v2(
    sample_set_type: type[Any],
    base_dir: str | Path,
    *,
    categories: list[str] | None = None,
    metadata_fields: list[str] | None = None,
    data_vars: list[str] | None = None,
    features: list[str] | None = None,
) -> dict[str, Any]:
    """兼容保留的当前 `SET_SQLITE_H5 v2` 校验 helper。

    Stability:
        Private / implementation detail.
    """

    probe_set = sample_set_type()
    ctx = StorageContext(
        probe_set,
        base_dir=Path(base_dir).resolve(),
        storage_scheme=StorageScheme.SET_SQLITE_H5,
    )
    strategy = _SetSqliteH5Strategy(ctx)
    strategy._refresh_cache()
    uids = list(strategy.uid_name_index().keys())
    metadata_frame = strategy.metadata_frame(uids=uids)
    summary_frame = strategy.summary_frame(
        uids=uids,
        metadata_fields=metadata_fields,
        data_vars=data_vars,
        features=features,
    )
    loaded_fields = {uid: strategy._load_sample_fields_from_resources(uid, categories=categories) for uid in uids}
    presence = {uid: strategy.sample_presence(uid, uid) for uid in uids}
    return {
        "sample_count": len(uids),
        "uids": uids,
        "metadata_frame": metadata_frame,
        "summary_frame": summary_frame,
        "loaded_fields": loaded_fields,
        "presence": presence,
    }


class _SetSqliteH5ReadSession(_StorageReadSession):
    """`SET_SQLITE_H5` 读取会话，复用 SQLite 连接与 H5 只读句柄。"""

    def __init__(self, strategy: _SetSqliteH5Strategy) -> None:
        super().__init__(strategy)
        self._strategy = strategy
        self._conn: sqlite3.Connection | None = None
        self._h5_file: h5py.File | None = None

    def __enter__(self) -> "_SetSqliteH5ReadSession":
        self._conn = self._strategy._connect(
            timeout=_SQLITE_H5_LOCK_TIMEOUT_SECONDS,
            isolation_level=None,
        )
        try:
            self._strategy._ensure_schema(self._conn)
            self._strategy._begin_reader_transaction(self._conn)
            self._h5_file = h5py.File(self._strategy.ctx.sqlite_payload_h5_path(), "r")
        except Exception:  # noqa: BLE001
            if self._h5_file is not None:
                self._h5_file.close()
                self._h5_file = None
            if self._conn is not None:
                self._conn.rollback()
                self._conn.close()
                self._conn = None
            raise
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        del exc_type, exc, tb
        if self._h5_file is not None:
            self._h5_file.close()
            self._h5_file = None
        if self._conn is not None:
            self._conn.rollback()
            self._conn.close()
            self._conn = None

    def load_sample(
        self,
        uid: str,
        name: str,
        categories: list[str] | None = None,
    ) -> SampleBaseModel:
        del name
        if self._h5_file is None:
            raise RuntimeError("SET_SQLITE_H5 读取会话尚未打开")
        return self._strategy._load_sample_from_resources(uid, categories=categories, h5_file=self._h5_file)

    def load_sample_fields(
        self,
        uid: str,
        name: str,
        categories: list[str],
    ) -> dict[str, object]:
        del name
        if self._h5_file is None:
            raise RuntimeError("SET_SQLITE_H5 读取会话尚未打开")
        return self._strategy._load_sample_fields_from_resources(uid, categories=categories, h5_file=self._h5_file)

    def load_many_sample_fields(
        self,
        items: list[tuple[str, str]],
        categories: list[str],
    ) -> dict[str, dict[str, object]]:
        if self._h5_file is None:
            raise RuntimeError("SET_SQLITE_H5 读取会话尚未打开")
        loaded: dict[str, dict[str, object]] = {uid: {} for uid, _ in items}
        if not items or not categories:
            return loaded

        selected = self._strategy.resolve_load_categories(categories)
        path_groups: dict[str, list[tuple[str, str]]] = {}
        for uid, _ in items:
            presence_rows = self._strategy._presence_rows(uid)
            for category in selected:
                row_info = presence_rows.get(category)
                if row_info is None or not row_info.exists_flag:
                    continue
                path_groups.setdefault(row_info.h5_path, []).append((uid, category))

        for h5_path, refs in path_groups.items():
            payload = self._strategy._read_payload_path(self._h5_file, h5_path)
            for uid, category in refs:
                loaded[uid][category] = self._strategy.ctx.deserialize_container(category, payload)
        return loaded

    def sample_presence(
        self,
        uid: str,
        name: str,
    ) -> dict[str, bool]:
        del name
        return self._strategy.sample_presence(uid, uid)


class _SetSqliteH5WriteSession(_StorageWriteSession):
    """`SET_SQLITE_H5` 写入会话，复用 SQLite 连接与 H5 写句柄。"""

    def __init__(self, strategy: _SetSqliteH5Strategy) -> None:
        super().__init__(strategy)
        self._strategy = strategy
        self._conn: sqlite3.Connection | None = None
        self._h5_file: h5py.File | None = None
        self._pending_artifacts: list[_SqliteTransferArtifact] = []
        self._metrics = _SqliteWriteMetrics()

    def __enter__(self) -> "_SetSqliteH5WriteSession":
        self._conn = self._strategy._connect(
            timeout=_SQLITE_H5_LOCK_TIMEOUT_SECONDS,
            isolation_level=None,
        )
        try:
            self._strategy._ensure_schema(self._conn)
            self._strategy._begin_writer_transaction(self._conn)
            self._h5_file = h5py.File(self._strategy.ctx.sqlite_payload_h5_path(), "a")
            self._h5_file.require_group("samples")
        except Exception:  # noqa: BLE001
            if self._h5_file is not None:
                self._h5_file.close()
                self._h5_file = None
            if self._conn is not None:
                self._conn.rollback()
                self._conn.close()
                self._conn = None
            raise
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        if self._conn is not None and exc_type is None:
            self._flush_pending()
        if self._h5_file is not None:
            self._h5_file.close()
            self._h5_file = None
        if self._conn is not None:
            if exc_type is None:
                self._conn.commit()
            else:
                self._conn.rollback()
            self._conn.close()
            self._conn = None
        self._pending_artifacts.clear()
        refresh_started = perf_counter()
        self._strategy._refresh_cache()
        self._metrics.refresh_cache_seconds += perf_counter() - refresh_started
        self._strategy._last_write_metrics = self._metrics
        del exc_type, exc, tb

    def save_sample(self, sample: SampleBaseModel, categories: list[str] | None = None) -> None:
        if self._conn is None or self._h5_file is None:
            raise RuntimeError("SET_SQLITE_H5 写入会话尚未打开")
        artifact_started = perf_counter()
        artifact, data_dict = self._strategy._build_transfer_artifact(
            sample,
            categories=categories,
            conn=self._conn,
        )
        self._metrics.artifact_seconds += perf_counter() - artifact_started
        payload_started = perf_counter()
        self._strategy._write_payload(
            artifact.sample_row.payload_id,
            sample,
            data_dict,
            artifact.sample_row.timestamp,
            h5_file=self._h5_file,
        )
        self._metrics.payload_seconds += perf_counter() - payload_started
        self._metrics.sample_count += 1
        sample._storage_payload_id = artifact.sample_row.payload_id
        self._pending_artifacts.append(artifact)
        if len(self._pending_artifacts) >= _SQLITE_H5_WRITE_FLUSH_BATCH_SIZE:
            self._flush_pending()

    def _flush_pending(self) -> None:
        if self._conn is None or not self._pending_artifacts:
            return
        timings = self._strategy._flush_transfer_artifacts(self._conn, self._pending_artifacts)
        self._metrics.flush_count += 1
        self._metrics.sample_seconds += timings["sample_seconds"]
        self._metrics.metadata_seconds += timings["metadata_seconds"]
        self._metrics.presence_seconds += timings["presence_seconds"]
        self._metrics.summary_seconds += timings["summary_seconds"]
        self._pending_artifacts.clear()


__all__ = ["_SetSqliteH5Strategy"]
