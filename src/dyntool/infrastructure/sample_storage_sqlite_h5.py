"""`SET_SQLITE_H5` 鏍锋湰闆嗗瓨鍌ㄧ瓥鐣ャ€?"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import uuid4

import h5py
import numpy as np
import pandas as pd

from .sample_storage_strategy_base import _StorageStrategy
from .storage_constants import H5_ATTR_UNIT

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


class _SetSqliteH5Strategy(_StorageStrategy):
    """浣跨敤 SQLite 绱㈠紩鍜?H5 payload 鐨勬牱鏈泦瀛樺偍绛栫暐銆?"""

    def __init__(self, ctx: Any) -> None:
        super().__init__(ctx)
        self._sample_rows_by_uid: dict[str, _SqliteSampleRow] = {}
        self._presence_rows_by_uid: dict[str, dict[str, _SqlitePresenceRow]] = {}

    def prepare_layout(self) -> None:
        self.ctx.base_dir.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            self._ensure_schema(conn)
        with h5py.File(self.ctx.sqlite_payload_h5_path(), "a") as h5_file:
            h5_file.require_group("samples")

    def uid_name_index(self) -> dict[str, str]:
        self._refresh_cache()
        return {uid: uid for uid in self._sample_rows_by_uid}

    def save_sample(self, sample: SampleBaseModel, categories: list[str] | None = None) -> None:
        data_dict = self.ctx.sample_data_dict(sample, categories)
        payload_id = self._resolve_payload_id(sample)
        timestamp = self._now_text()
        metadata_json = json.dumps(sample.metadata.model_dump(), ensure_ascii=False, default=str)

        self._write_payload(payload_id, sample, data_dict, timestamp)

        with self._connect() as conn:
            self._ensure_schema(conn)
            sample_id = self._upsert_sample_row(
                conn,
                sample=sample,
                payload_id=payload_id,
                metadata_json=metadata_json,
                timestamp=timestamp,
            )
            self._replace_metadata_rows(conn, sample_id=sample_id, metadata=sample.metadata.to_flatten_dict(sep="@"))
            self._replace_presence_rows(
                conn,
                sample_id=sample_id,
                data_dict=data_dict,
                payload_id=payload_id,
                timestamp=timestamp,
            )
            conn.commit()

        sample._storage_payload_id = payload_id
        self._refresh_cache()

    def load_sample(
        self,
        uid: str,
        name: str,
        categories: list[str] | None = None,
    ) -> SampleBaseModel:
        del name
        row = self._sample_row(uid)
        if row is None:
            raise FileNotFoundError(f"鏈壘鍒板瓨鍌ㄤ腑鐨勬牱鏈? {uid}")

        sample = self.ctx.sampleset.sample_type(
            metadata=self.ctx.metadata_from_dict(json.loads(row.metadata_json)),
        )
        sample._restore_alias_internal(row.alias)
        sample._storage_payload_id = row.payload_id

        selected_categories = set(self.resolve_load_categories(categories))
        if not selected_categories:
            return sample

        presence_rows = self._presence_rows(uid)
        payload_path = self.ctx.sqlite_payload_h5_path()
        with h5py.File(payload_path, "r") as h5_file:
            for category in selected_categories:
                row_info = presence_rows.get(category)
                if row_info is None or not row_info.exists_flag:
                    continue
                if row_info.h5_path not in h5_file:
                    raise FileNotFoundError(f"H5 payload 涓己灏戞Ы浣? {category}: {row_info.h5_path}")
                category_group = h5_file[row_info.h5_path]
                if not isinstance(category_group, h5py.Group):
                    raise TypeError(f"H5 payload 妲戒綅涓嶆槸 Group: {row_info.h5_path}")
                sample.update(
                    **{category: self.ctx.deserialize_container(category, self._read_group_payload(category_group))}
                )
        return sample

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
        """杩斿洖褰撳墠鏍锋湰闆嗙殑 metadata 鎵佸钩琛ㄣ€?"""

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

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.ctx.sqlite_index_path())
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

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
            """
        )

    def _refresh_cache(self) -> None:
        with self._connect() as conn:
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

    def _resolve_payload_id(self, sample: SampleBaseModel) -> str:
        cached_payload_id = getattr(sample, "_storage_payload_id", None)
        if isinstance(cached_payload_id, str) and cached_payload_id:
            return cached_payload_id
        row = self._sample_row(sample.uid)
        if row is not None:
            return row.payload_id
        return uuid4().hex

    def _sample_row(self, uid: str) -> _SqliteSampleRow | None:
        if uid in self._sample_rows_by_uid:
            return self._sample_rows_by_uid[uid]
        self._refresh_cache()
        return self._sample_rows_by_uid.get(uid)

    def _presence_rows(self, uid: str) -> dict[str, _SqlitePresenceRow]:
        if uid not in self._presence_rows_by_uid:
            self._refresh_cache()
        return self._presence_rows_by_uid.get(uid, {})

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

    def _write_payload(
        self,
        payload_id: str,
        sample: SampleBaseModel,
        data_dict: dict[str, Any],
        timestamp: str,
    ) -> None:
        with h5py.File(self.ctx.sqlite_payload_h5_path(), "a") as h5_file:
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
                raise TypeError(f"H5 瀛樺偍鏆備笉鏀寔瀵硅薄鏁扮粍瀛楁: {key}")
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


__all__ = ["_SetSqliteH5Strategy"]
