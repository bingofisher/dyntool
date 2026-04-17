"""`SET_SQLITE_H5` 存储策略实现。"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import TYPE_CHECKING, Any
from uuid import uuid4

import h5py
import pandas as pd

from .sample_storage_context import StorageContext
from .sample_storage_sqlite_h5_payload import (
    _load_many_sample_fields as _load_many_sample_fields_impl,
    _load_sample_fields_from_resources as _load_sample_fields_from_resources_impl,
    _load_sample_from_resources as _load_sample_from_resources_impl,
    _read_group_payload as _read_group_payload_impl,
    _read_payload_path as _read_payload_path_impl,
    _write_group as _write_group_impl,
    _write_payload as _write_payload_impl,
    _write_payload_group as _write_payload_group_impl,
)
from .sample_storage_sqlite_h5_projection import (
    _build_metadata_artifacts,
    _build_presence_artifacts,
    _build_summary_artifacts,
    _build_summary_rows as _build_summary_rows_impl,
    _decode_metadata_value as _decode_metadata_value_impl,
    _flatten_metadata_rows as _flatten_metadata_rows_impl,
    _metadata_value_columns as _metadata_value_columns_impl,
    _query_metadata_frame_v1,
    _query_metadata_frame_v2,
    _query_summary_frame_v1,
    _query_summary_frame_v2,
    _summary_scalar_row as _summary_scalar_row_impl,
)
from .sample_storage_sqlite_h5_schema import (
    _ensure_current_schema,
    _ensure_legacy_v1_schema,
    _schema_version as _schema_version_impl,
    _set_schema_version as _set_schema_version_impl,
    _table_names as _table_names_impl,
)
from .sample_storage_sqlite_h5_sessions import _SetSqliteH5ReadSession, _SetSqliteH5WriteSession
from .sample_storage_sqlite_h5_types import (
    _SQLITE_H5_LOCK_TIMEOUT_SECONDS,
    _SQLITE_H5_WRITE_FLUSH_BATCH_SIZE as _SQLITE_H5_WRITE_FLUSH_BATCH_SIZE_DEFAULT,
    _SqliteFlushResult,
    _SqlitePresenceRow,
    _SqliteSampleRow,
    _SqliteSampleUpsertArtifact,
    _SqliteTransferArtifact,
    _SqliteWriteMetrics,
)
from .sample_storage_strategy_base import _StorageReadSession, _StorageStrategy, _StorageWriteSession
from ..storage.types import StorageScheme

if TYPE_CHECKING:
    from ..domain.samples.base import SampleBaseModel


_SQLITE_H5_WRITE_FLUSH_BATCH_SIZE = _SQLITE_H5_WRITE_FLUSH_BATCH_SIZE_DEFAULT


class _SetSqliteH5Strategy(_StorageStrategy):
    """基于 SQLite 索引与 H5 payload 的样本集存储策略。"""

    def __init__(self, ctx: Any) -> None:
        super().__init__(ctx)
        self._sample_rows_by_uid: dict[str, _SqliteSampleRow] = {}
        self._sample_uid_by_id: dict[int, str] = {}
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
        return _load_many_sample_fields_impl(
            self,
            items=items,
            categories=categories,
        )

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
        return _query_summary_frame_v2(
            self,
            uids=uids,
            metadata_fields=metadata_fields,
            data_vars=data_vars,
            features=features,
        )

    def _summary_frame_from_conn(
        self,
        conn: sqlite3.Connection,
        *,
        uids: list[str] | None = None,
        metadata_fields: list[str] | None = None,
        data_vars: list[str] | None = None,
        features: list[str] | None = None,
    ) -> pd.DataFrame:
        return _query_summary_frame_v2(
            self,
            conn=conn,
            uids=uids,
            metadata_fields=metadata_fields,
            data_vars=data_vars,
            features=features,
        )

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

        return _query_metadata_frame_v2(self, uids=uids)

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
        _ensure_current_schema(conn)

    @staticmethod
    def _schema_version(conn: sqlite3.Connection) -> int:
        return _schema_version_impl(conn)

    @staticmethod
    def _set_schema_version(conn: sqlite3.Connection, version: int) -> None:
        _set_schema_version_impl(conn, version)

    @staticmethod
    def _table_names(conn: sqlite3.Connection) -> set[str]:
        return _table_names_impl(conn)

    def _replace_cache(
        self,
        *,
        sample_rows_by_uid: dict[str, _SqliteSampleRow],
        presence_rows_by_uid: dict[str, dict[str, _SqlitePresenceRow]],
    ) -> None:
        self._sample_rows_by_uid = dict(sample_rows_by_uid)
        self._sample_uid_by_id = {row.sample_id: uid for uid, row in self._sample_rows_by_uid.items()}
        self._presence_rows_by_uid = {uid: dict(presence_rows_by_uid.get(uid, {})) for uid in self._sample_rows_by_uid}
        for uid in self._sample_rows_by_uid:
            self._presence_rows_by_uid.setdefault(uid, {})

    def _apply_cache_update(
        self,
        *,
        sample_rows_by_uid: dict[str, _SqliteSampleRow],
        presence_rows_by_uid: dict[str, dict[str, _SqlitePresenceRow]],
    ) -> None:
        for uid, sample_row in sample_rows_by_uid.items():
            previous_uid = self._sample_uid_by_id.get(sample_row.sample_id)
            if previous_uid is not None and previous_uid != uid:
                self._sample_rows_by_uid.pop(previous_uid, None)
                self._presence_rows_by_uid.pop(previous_uid, None)
            self._sample_rows_by_uid[uid] = sample_row
            self._sample_uid_by_id[sample_row.sample_id] = uid
            self._presence_rows_by_uid[uid] = dict(presence_rows_by_uid.get(uid, {}))

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

        sample_rows_by_uid = {
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
        presence_rows_by_uid: dict[str, dict[str, _SqlitePresenceRow]] = {uid: {} for uid in sample_rows_by_uid}
        for row in presence_rows:
            uid = str(row["uid"])
            presence_rows_by_uid.setdefault(uid, {})[str(row["slot_name"])] = _SqlitePresenceRow(
                slot_name=str(row["slot_name"]),
                exists_flag=bool(row["exists_flag"]),
                model_type=str(row["model_type"]) if row["model_type"] is not None else None,
                data_category=str(row["data_category"]) if row["data_category"] is not None else None,
                h5_path=str(row["h5_path"]),
                updated_at=str(row["updated_at"]),
            )
        self._replace_cache(
            sample_rows_by_uid=sample_rows_by_uid,
            presence_rows_by_uid=presence_rows_by_uid,
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
        metadata_json = self._metadata_json(sample)

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
                presence_rows=_build_presence_artifacts(
                    self,
                    data_dict,
                    payload_id=payload_id,
                    timestamp=timestamp,
                ),
                summary_rows=_build_summary_artifacts(
                    data_dict,
                    timestamp=timestamp,
                ),
            ),
            data_dict,
        )

    def _flush_transfer_artifacts(
        self,
        conn: sqlite3.Connection,
        artifacts: list[_SqliteTransferArtifact],
    ) -> _SqliteFlushResult:
        if not artifacts:
            return _SqliteFlushResult()
        self._ensure_schema(conn)
        sample_started = perf_counter()
        sample_rows_by_uid = self._batch_upsert_sample_rows(conn, artifacts)
        sample_seconds = perf_counter() - sample_started
        sample_ids = {uid: row.sample_id for uid, row in sample_rows_by_uid.items()}
        metadata_started = perf_counter()
        metadata_seconds = perf_counter() - metadata_started
        presence_started = perf_counter()
        self._sync_presence_artifacts(conn, sample_ids=sample_ids, artifacts=artifacts)
        presence_seconds = perf_counter() - presence_started
        summary_started = perf_counter()
        self._sync_summary_artifacts(conn, sample_ids=sample_ids, artifacts=artifacts)
        summary_seconds = perf_counter() - summary_started
        return _SqliteFlushResult(
            sample_seconds=sample_seconds,
            metadata_seconds=metadata_seconds,
            presence_seconds=presence_seconds,
            summary_seconds=summary_seconds,
            sample_rows_by_uid=sample_rows_by_uid,
            presence_rows_by_uid=self._presence_rows_from_artifacts(artifacts),
        )

    def _batch_upsert_sample_rows(
        self,
        conn: sqlite3.Connection,
        artifacts: list[_SqliteTransferArtifact],
    ) -> dict[str, _SqliteSampleRow]:
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
            SELECT sample_id, uid, alias, payload_id, metadata_json, created_at, updated_at
            FROM sample
            WHERE uid IN ({uid_placeholders})
            """,
            uids,
        ).fetchall()
        return {
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

    @staticmethod
    def _delete_stale_projection_rows(
        conn: sqlite3.Connection,
        *,
        table: str,
        key_column: str,
        active_keys_by_sample_id: dict[int, list[str]],
    ) -> None:
        if table not in {"sample_slot_presence", "sample_summary_projection", "sample_metadata_flat"}:
            raise ValueError(f"不支持的 projection 表: {table}")
        if key_column not in {"slot_name", "key"}:
            raise ValueError(f"不支持的 projection 键列: {key_column}")
        for sample_id, active_keys in active_keys_by_sample_id.items():
            if active_keys:
                placeholders = ", ".join("?" for _ in active_keys)
                conn.execute(
                    f"DELETE FROM {table} WHERE sample_id = ? AND {key_column} NOT IN ({placeholders})",
                    [sample_id, *active_keys],
                )
                continue
            conn.execute(f"DELETE FROM {table} WHERE sample_id = ?", (sample_id,))

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

    def _presence_rows_from_artifacts(
        self,
        artifacts: list[_SqliteTransferArtifact],
    ) -> dict[str, dict[str, _SqlitePresenceRow]]:
        presence_rows_by_uid: dict[str, dict[str, _SqlitePresenceRow]] = {}
        for artifact in artifacts:
            presence_rows_by_uid[artifact.sample_row.uid] = {
                item.slot_name: _SqlitePresenceRow(
                    slot_name=item.slot_name,
                    exists_flag=bool(item.exists_flag),
                    model_type=item.model_type,
                    data_category=item.data_category,
                    h5_path=item.h5_path,
                    updated_at=item.updated_at,
                )
                for item in artifact.presence_rows
            }
        return presence_rows_by_uid

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

    def _sync_presence_artifacts(
        self,
        conn: sqlite3.Connection,
        *,
        sample_ids: dict[str, int],
        artifacts: list[_SqliteTransferArtifact],
    ) -> None:
        active_slots_by_sample_id: dict[int, list[str]] = {}
        rows: list[tuple[int, str, int, str | None, str | None, str, str]] = []
        for artifact in artifacts:
            sample_id = sample_ids[artifact.sample_row.uid]
            active_slots_by_sample_id[sample_id] = [item.slot_name for item in artifact.presence_rows]
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

        self._delete_stale_projection_rows(
            conn,
            table="sample_slot_presence",
            key_column="slot_name",
            active_keys_by_sample_id=active_slots_by_sample_id,
        )
        if not rows:
            return
        conn.executemany(
            """
            INSERT INTO sample_slot_presence
                (sample_id, slot_name, exists_flag, model_type, data_category, h5_path, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(sample_id, slot_name) DO UPDATE SET
                exists_flag = excluded.exists_flag,
                model_type = excluded.model_type,
                data_category = excluded.data_category,
                h5_path = excluded.h5_path,
                updated_at = excluded.updated_at
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

    def _sync_summary_artifacts(
        self,
        conn: sqlite3.Connection,
        *,
        sample_ids: dict[str, int],
        artifacts: list[_SqliteTransferArtifact],
    ) -> None:
        active_keys_by_sample_id: dict[int, list[str]] = {}
        rows: list[tuple[int, str, float | None, str | None, str | None, str]] = []
        for artifact in artifacts:
            sample_id = sample_ids[artifact.sample_row.uid]
            active_keys_by_sample_id[sample_id] = [item.key for item in artifact.summary_rows]
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

        self._delete_stale_projection_rows(
            conn,
            table="sample_summary_projection",
            key_column="key",
            active_keys_by_sample_id=active_keys_by_sample_id,
        )
        if not rows:
            return
        conn.executemany(
            """
            INSERT INTO sample_summary_projection
                (sample_id, key, value_real, value_text, unit, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(sample_id, key) DO UPDATE SET
                value_real = excluded.value_real,
                value_text = excluded.value_text,
                unit = excluded.unit,
                updated_at = excluded.updated_at
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
        return _load_sample_from_resources_impl(
            self,
            uid,
            categories=categories,
            h5_file=h5_file,
        )

    def _load_sample_fields_from_resources(
        self,
        uid: str,
        *,
        categories: list[str] | None,
        h5_file: h5py.File | None = None,
    ) -> dict[str, object]:
        return _load_sample_fields_from_resources_impl(
            self,
            uid,
            categories=categories,
            h5_file=h5_file,
        )

    def _read_payload_path(self, h5_file: h5py.File, h5_path: str) -> dict[str, Any]:
        return _read_payload_path_impl(self, h5_file, h5_path)

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
        return _flatten_metadata_rows_impl(self, rows)

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
        _write_payload_impl(
            self,
            payload_id,
            sample,
            data_dict,
            timestamp,
            h5_file=h5_file,
        )

    def _write_group(self, group: h5py.Group, category: str, data: Any) -> None:
        _write_group_impl(self, group, category, data)

    def _write_payload_group(self, group: h5py.Group, payload: dict[str, Any]) -> None:
        _write_payload_group_impl(self, group, payload)

    def _read_group_payload(self, group: h5py.Group) -> dict[str, Any]:
        return _read_group_payload_impl(group)

    @staticmethod
    def _metadata_value_columns(value: Any) -> dict[str, Any]:
        return _metadata_value_columns_impl(value)

    @staticmethod
    def _decode_metadata_value(row: sqlite3.Row) -> Any:
        return _decode_metadata_value_impl(row)

    @staticmethod
    def _now_text() -> str:
        return datetime.now().isoformat(timespec="seconds")

    @staticmethod
    def _summary_scalar_row(
        value: float | str | None,
        *,
        unit: str | None = None,
    ) -> dict[str, Any]:
        return _summary_scalar_row_impl(value, unit=unit)

    def _build_summary_rows(self, data_dict: dict[str, Any]) -> dict[str, dict[str, Any]]:
        return _build_summary_rows_impl(data_dict)

    @staticmethod
    def _metadata_json(sample: SampleBaseModel) -> str:
        return json.dumps(sample.metadata.model_dump(), ensure_ascii=False, default=str)


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
        return _query_summary_frame_v1(
            self,
            uids=uids,
            metadata_fields=metadata_fields,
            data_vars=data_vars,
            features=features,
        )

    def metadata_frame(self, *, uids: list[str] | None = None) -> pd.DataFrame:
        return _query_metadata_frame_v1(self, uids=uids)

    def _summary_frame_from_conn(
        self,
        conn: sqlite3.Connection,
        *,
        uids: list[str] | None = None,
        metadata_fields: list[str] | None = None,
        data_vars: list[str] | None = None,
        features: list[str] | None = None,
    ) -> pd.DataFrame:
        return _query_summary_frame_v1(
            self,
            conn=conn,
            uids=uids,
            metadata_fields=metadata_fields,
            data_vars=data_vars,
            features=features,
        )

    def _ensure_schema(self, conn: sqlite3.Connection) -> None:
        _ensure_legacy_v1_schema(conn)

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
        metadata_json = self._metadata_json(sample)

        return (
            _SqliteTransferArtifact(
                sample_row=_SqliteSampleUpsertArtifact(
                    uid=sample.uid,
                    alias=sample.alias,
                    payload_id=payload_id,
                    metadata_json=metadata_json,
                    timestamp=timestamp,
                ),
                metadata_rows=_build_metadata_artifacts(sample.metadata.to_flatten_dict(sep="@")),
                presence_rows=_build_presence_artifacts(
                    self,
                    data_dict,
                    payload_id=payload_id,
                    timestamp=timestamp,
                ),
                summary_rows=_build_summary_artifacts(
                    data_dict,
                    timestamp=timestamp,
                ),
            ),
            data_dict,
        )

    def _flush_transfer_artifacts(
        self,
        conn: sqlite3.Connection,
        artifacts: list[_SqliteTransferArtifact],
    ) -> _SqliteFlushResult:
        if not artifacts:
            return _SqliteFlushResult()
        self._ensure_schema(conn)
        sample_started = perf_counter()
        sample_rows_by_uid = self._batch_upsert_sample_rows(conn, artifacts)
        sample_seconds = perf_counter() - sample_started
        sample_ids = {uid: row.sample_id for uid, row in sample_rows_by_uid.items()}
        target_sample_ids = list(sample_ids.values())
        metadata_started = perf_counter()
        self._delete_sample_projection_rows(conn, table="sample_metadata_flat", sample_ids=target_sample_ids)
        self._insert_metadata_artifacts(conn, sample_ids=sample_ids, artifacts=artifacts)
        metadata_seconds = perf_counter() - metadata_started
        presence_started = perf_counter()
        self._sync_presence_artifacts(conn, sample_ids=sample_ids, artifacts=artifacts)
        presence_seconds = perf_counter() - presence_started
        summary_started = perf_counter()
        self._sync_summary_artifacts(conn, sample_ids=sample_ids, artifacts=artifacts)
        summary_seconds = perf_counter() - summary_started
        return _SqliteFlushResult(
            sample_seconds=sample_seconds,
            metadata_seconds=metadata_seconds,
            presence_seconds=presence_seconds,
            summary_seconds=summary_seconds,
            sample_rows_by_uid=sample_rows_by_uid,
            presence_rows_by_uid=self._presence_rows_from_artifacts(artifacts),
        )

    def _flatten_metadata_rows(self, rows: list[sqlite3.Row]) -> dict[str, dict[str, Any]]:
        return _flatten_metadata_rows_impl(self, rows)


def _save_sample_set_with_strategy(
    strategy_cls: type[_SetSqliteH5Strategy],
    sampleset: Any,
    base_dir: str | Path,
    *,
    categories: list[str] | None = None,
) -> _SqliteWriteMetrics:
    """按给定 strategy 保存样本集。"""

    target_dir = Path(base_dir).resolve()
    ctx = StorageContext(
        sampleset,
        base_dir=target_dir,
        storage_scheme=StorageScheme.SET_SQLITE_H5,
    )
    strategy = strategy_cls(ctx)
    strategy.prepare_layout()
    with strategy.write_session() as session:
        for sample in sampleset.values():
            session.save_sample(sample, categories)
    return strategy._last_write_metrics or _SqliteWriteMetrics()


def _validate_sample_set_with_strategy(
    strategy_cls: type[_SetSqliteH5Strategy],
    sample_set_type: type[Any],
    base_dir: str | Path,
    *,
    categories: list[str] | None = None,
    metadata_fields: list[str] | None = None,
    data_vars: list[str] | None = None,
    features: list[str] | None = None,
) -> dict[str, Any]:
    """按给定 strategy 读取最小校验结果。"""

    probe_set = sample_set_type()
    ctx = StorageContext(
        probe_set,
        base_dir=Path(base_dir).resolve(),
        storage_scheme=StorageScheme.SET_SQLITE_H5,
    )
    strategy = strategy_cls(ctx)
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


def _save_sample_set_legacy_v1(
    sampleset: Any,
    base_dir: str | Path,
    *,
    categories: list[str] | None = None,
) -> _SqliteWriteMetrics:
    """将样本集写入旧版 v1 `SET_SQLITE_H5` 仓库。"""
    return _save_sample_set_with_strategy(
        _LegacySetSqliteH5V1Strategy,
        sampleset,
        base_dir,
        categories=categories,
    )


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
    return _validate_sample_set_with_strategy(
        _LegacySetSqliteH5V1Strategy,
        sample_set_type,
        base_dir,
        categories=categories,
        metadata_fields=metadata_fields,
        data_vars=data_vars,
        features=features,
    )


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

    return _save_sample_set_with_strategy(
        _SetSqliteH5Strategy,
        sampleset,
        base_dir,
        categories=categories,
    )


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

    return _validate_sample_set_with_strategy(
        _SetSqliteH5Strategy,
        sample_set_type,
        base_dir,
        categories=categories,
        metadata_fields=metadata_fields,
        data_vars=data_vars,
        features=features,
    )


__all__ = ["_SetSqliteH5Strategy"]
