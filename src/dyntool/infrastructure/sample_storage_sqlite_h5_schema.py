"""`SET_SQLITE_H5` 的 schema 与迁移 helper。"""

from __future__ import annotations

import json
import sqlite3

from .sample_storage_sqlite_h5_types import (
    _SQLITE_H5_SCHEMA_VERSION_V1,
    _SQLITE_H5_SCHEMA_VERSION_V2,
)


def _schema_version(conn: sqlite3.Connection) -> int:
    """读取当前 schema 版本。"""

    return int(conn.execute("PRAGMA user_version").fetchone()[0])


def _set_schema_version(conn: sqlite3.Connection, version: int) -> None:
    """写入 schema 版本。"""

    conn.execute(f"PRAGMA user_version = {int(version)}")


def _table_names(conn: sqlite3.Connection) -> set[str]:
    """读取当前 SQLite 表集合。"""

    rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    return {str(row["name"]) for row in rows}


def _ensure_v2_schema_objects(conn: sqlite3.Connection) -> None:
    """确保 v2 schema 所需对象存在。"""

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


def _drop_v1_metadata_flat(conn: sqlite3.Connection) -> None:
    """删除 v1 的扁平 metadata 表。"""

    conn.executescript(
        """
        DROP INDEX IF EXISTS idx_sample_metadata_flat_text;
        DROP INDEX IF EXISTS idx_sample_metadata_flat_int;
        DROP INDEX IF EXISTS idx_sample_metadata_flat_real;
        DROP TABLE IF EXISTS sample_metadata_flat;
        """
    )


def _migrate_v1_to_v2(conn: sqlite3.Connection) -> None:
    """执行 v1 到 v2 的原地迁移。"""

    rows = conn.execute("SELECT sample_id, metadata_json FROM sample ORDER BY sample_id").fetchall()
    for row in rows:
        metadata_json = row["metadata_json"]
        try:
            json.loads(str(metadata_json))
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"SET_SQLITE_H5 v1 -> v2 迁移失败，metadata_json 无法解析: {exc}") from exc
    _drop_v1_metadata_flat(conn)
    _ensure_v2_schema_objects(conn)
    _set_schema_version(conn, _SQLITE_H5_SCHEMA_VERSION_V2)


def _ensure_current_schema(conn: sqlite3.Connection) -> None:
    """确保当前正式 v2 schema 可用，并在需要时执行迁移。"""

    table_names = _table_names(conn)
    version = _schema_version(conn)
    if version >= _SQLITE_H5_SCHEMA_VERSION_V2:
        _ensure_v2_schema_objects(conn)
        if "sample_metadata_flat" in table_names:
            _drop_v1_metadata_flat(conn)
        if version != _SQLITE_H5_SCHEMA_VERSION_V2:
            _set_schema_version(conn, _SQLITE_H5_SCHEMA_VERSION_V2)
        return
    if "sample" in table_names and "sample_metadata_flat" in table_names:
        _migrate_v1_to_v2(conn)
        return
    _ensure_v2_schema_objects(conn)
    _set_schema_version(conn, _SQLITE_H5_SCHEMA_VERSION_V2)


def _ensure_legacy_v1_schema(conn: sqlite3.Connection) -> None:
    """确保 legacy v1 schema 存在。"""

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
    if _schema_version(conn) == 0:
        _set_schema_version(conn, _SQLITE_H5_SCHEMA_VERSION_V1)


__all__ = [
    "_drop_v1_metadata_flat",
    "_ensure_current_schema",
    "_ensure_legacy_v1_schema",
    "_ensure_v2_schema_objects",
    "_migrate_v1_to_v2",
    "_schema_version",
    "_set_schema_version",
    "_table_names",
]
