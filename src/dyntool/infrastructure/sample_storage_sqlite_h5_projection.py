"""`SET_SQLITE_H5` 的 projection 与 summary helper。"""

from __future__ import annotations

import json
import sqlite3
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd

from .sample_storage_sqlite_h5_types import (
    _SqliteMetadataArtifact,
    _SqlitePresenceArtifact,
    _SqliteSummaryArtifact,
)

if TYPE_CHECKING:
    from .sample_storage_sqlite_h5 import _SetSqliteH5Strategy


def _metadata_value_columns(value: Any) -> dict[str, Any]:
    """将 metadata 值映射到 v1 扁平列。"""

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


def _decode_metadata_value(row: sqlite3.Row) -> Any:
    """从 v1 扁平列解码 metadata 值。"""

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


def _flatten_metadata_rows(strategy: _SetSqliteH5Strategy, rows: list[sqlite3.Row]) -> dict[str, dict[str, Any]]:
    """将 metadata_json 扁平化为 metadata frame 所需结构。"""

    flattened_by_uid: dict[str, dict[str, Any]] = {}
    for row in rows:
        uid = str(row["uid"])
        metadata_dict = json.loads(str(row["metadata_json"]))
        metadata = strategy.ctx.metadata_from_dict(metadata_dict)
        flattened_by_uid[uid] = {str(key): value for key, value in metadata.to_flatten_dict(sep="@").items()}
    return flattened_by_uid


def _summary_scalar_row(
    value: float | str | None,
    *,
    unit: str | None = None,
) -> dict[str, Any]:
    """构建单个 summary 标量行。"""

    if value is None:
        return {"value_real": None, "value_text": None, "unit": unit}
    if isinstance(value, (int, float, np.floating, np.integer)):
        return {"value_real": float(value), "value_text": None, "unit": unit}
    return {"value_real": None, "value_text": str(value), "unit": unit}


def _build_summary_rows(data_dict: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """从样本槽位构建 summary projection 行。"""

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
                    rows[f"{slot_name}.{key}"] = _summary_scalar_row(value, unit=unit)

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
                    rows[f"{slot_name}@sample_count"] = _summary_scalar_row(sample_count)
                if dt is not None:
                    rows[f"{slot_name}@dt"] = _summary_scalar_row(dt, unit="second")
                if start is not None and end is not None:
                    rows[f"{slot_name}@duration"] = _summary_scalar_row(
                        float(end) - float(start),
                        unit="second",
                    )

        unit_map = data.current_units() if hasattr(data, "current_units") else {}
        value_unit = unit_map.get("value") if isinstance(unit_map, dict) else None
        if slot_name == "accel" and hasattr(data, "pga"):
            rows["pga"] = _summary_scalar_row(data.pga(), unit=value_unit)
        if slot_name == "vel" and hasattr(data, "pgv"):
            rows["pgv"] = _summary_scalar_row(data.pgv(), unit=value_unit)
        if slot_name == "disp" and hasattr(data, "pgd"):
            rows["pgd"] = _summary_scalar_row(data.pgd(), unit=value_unit)
    return rows


def _build_presence_artifacts(
    strategy: _SetSqliteH5Strategy,
    data_dict: dict[str, Any],
    *,
    payload_id: str,
    timestamp: str,
) -> list[_SqlitePresenceArtifact]:
    """构建槽位存在性 projection artifact。"""

    return [
        _SqlitePresenceArtifact(
            slot_name=slot_name,
            exists_flag=1,
            model_type=data.__class__.__name__,
            data_category=strategy.ctx.sampleset.sample_schema.category(slot_name).value,
            h5_path=f"/samples/{payload_id}/slots/{slot_name}",
            updated_at=timestamp,
        )
        for slot_name, data in data_dict.items()
    ]


def _build_summary_artifacts(
    data_dict: dict[str, Any],
    *,
    timestamp: str,
) -> list[_SqliteSummaryArtifact]:
    """构建 summary artifact 列表。"""

    return [
        _SqliteSummaryArtifact(
            key=key,
            value_real=payload.get("value_real"),
            value_text=payload.get("value_text"),
            unit=payload.get("unit"),
            updated_at=timestamp,
        )
        for key, payload in _build_summary_rows(data_dict).items()
    ]


def _build_metadata_artifacts(flattened_metadata: dict[str, Any]) -> list[_SqliteMetadataArtifact]:
    """构建 legacy v1 metadata artifact 列表。"""

    metadata_rows: list[_SqliteMetadataArtifact] = []
    for key, value in flattened_metadata.items():
        columns = _metadata_value_columns(value)
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
    return metadata_rows


def _load_sample_rows(
    conn: sqlite3.Connection,
    *,
    uids: list[str] | None,
    columns: str,
) -> list[sqlite3.Row]:
    """按需读取目标样本行，未指定 UID 时直接按 sample_id 顺序扫描。"""

    if uids:
        placeholders = ", ".join("?" for _ in uids)
        return conn.execute(
            f"""
            SELECT {columns}
            FROM sample
            WHERE uid IN ({placeholders})
            ORDER BY sample_id
            """,
            uids,
        ).fetchall()
    return conn.execute(
        f"""
        SELECT {columns}
        FROM sample
        ORDER BY sample_id
        """
    ).fetchall()


def _escape_like_value(value: str) -> str:
    """转义 SQLite LIKE 条件中的通配符。"""

    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _projection_request(
    *,
    requested_features: list[str],
    requested_data_vars: list[str],
) -> tuple[set[str], tuple[str, ...]]:
    """归一化 summary projection 的特征键与数据变量前缀。"""

    feature_keys = {str(feature) for feature in requested_features}
    data_var_prefixes = tuple(f"{data_var}." for data_var in requested_data_vars if data_var)
    return feature_keys, data_var_prefixes


def _query_projection_rows(
    conn: sqlite3.Connection,
    *,
    sample_ids: list[int],
    feature_keys: set[str],
    data_var_prefixes: tuple[str, ...],
) -> list[sqlite3.Row]:
    """只读取命中的 projection 行，避免先拉回全量样本 summary。"""

    if not sample_ids or (not feature_keys and not data_var_prefixes):
        return []

    sample_id_placeholders = ", ".join("?" for _ in sample_ids)
    predicates: list[str] = []
    params: list[int | str] = [*sample_ids]

    if feature_keys:
        ordered_feature_keys = sorted(feature_keys)
        feature_placeholders = ", ".join("?" for _ in ordered_feature_keys)
        predicates.append(f"key IN ({feature_placeholders})")
        params.extend(ordered_feature_keys)

    if data_var_prefixes:
        predicates.extend("key LIKE ? ESCAPE '\\'" for _ in data_var_prefixes)
        params.extend(f"{_escape_like_value(prefix)}%" for prefix in data_var_prefixes)

    return conn.execute(
        f"""
        SELECT sample_id, key, value_real, value_text
        FROM sample_summary_projection
        WHERE sample_id IN ({sample_id_placeholders})
          AND ({" OR ".join(predicates)})
        ORDER BY sample_id, key
        """,
        params,
    ).fetchall()


def _query_metadata_frame_v2(
    strategy: _SetSqliteH5Strategy,
    *,
    uids: list[str] | None = None,
) -> pd.DataFrame:
    """读取 v2 metadata frame。"""

    with strategy._connect() as conn:
        strategy._ensure_schema(conn)
        target_uids = list(uids) if uids is not None else None
        rows = _load_sample_rows(conn, uids=target_uids, columns="sample_id, uid, metadata_json")

    ordered_uids = target_uids or [str(row["uid"]) for row in rows]
    if not ordered_uids:
        return pd.DataFrame()
    bucket = _flatten_metadata_rows(strategy, rows)
    return pd.DataFrame([bucket.get(uid, {}) for uid in ordered_uids])


def _query_summary_frame_v2(
    strategy: _SetSqliteH5Strategy,
    *,
    conn: sqlite3.Connection | None = None,
    uids: list[str] | None = None,
    metadata_fields: list[str] | None = None,
    data_vars: list[str] | None = None,
    features: list[str] | None = None,
) -> pd.DataFrame:
    """读取 v2 summary frame。"""

    requested_metadata = [str(field) for field in metadata_fields or ()]
    requested_features = [str(feature) for feature in features or ()]
    requested_data_vars = [str(data_var) for data_var in data_vars or ()]
    feature_keys, data_var_prefixes = _projection_request(
        requested_features=requested_features,
        requested_data_vars=requested_data_vars,
    )
    owned_conn = conn is None
    db_conn = conn or strategy._connect()
    try:
        if owned_conn:
            strategy._ensure_schema(db_conn)
        target_uids = list(uids) if uids is not None else None
        sample_columns = "sample_id, uid, alias, metadata_json" if requested_metadata else "sample_id, uid, alias"
        sample_rows = _load_sample_rows(db_conn, uids=target_uids, columns=sample_columns)

        ordered_uids = target_uids or [str(row["uid"]) for row in sample_rows]
        if not ordered_uids:
            return pd.DataFrame()

        sample_ids = [int(row["sample_id"]) for row in sample_rows]
        id_to_uid = {int(row["sample_id"]): str(row["uid"]) for row in sample_rows}
        rows: dict[str, dict[str, Any]] = {
            str(row["uid"]): {"uid": str(row["uid"]), "alias": str(row["alias"])} for row in sample_rows
        }

        if requested_metadata and sample_ids:
            metadata_by_uid = _flatten_metadata_rows(strategy, sample_rows)
            for uid, flattened in metadata_by_uid.items():
                target_row = rows[uid]
                for field_name in requested_metadata:
                    if field_name in flattened:
                        target_row[field_name] = flattened[field_name]

        projection_rows = _query_projection_rows(
            db_conn,
            sample_ids=sample_ids,
            feature_keys=feature_keys,
            data_var_prefixes=data_var_prefixes,
        )
        if projection_rows:
            _merge_projection_rows(
                rows=rows,
                projection_rows=projection_rows,
                id_to_uid=id_to_uid,
                requested_feature_keys=feature_keys,
                requested_data_var_prefixes=data_var_prefixes,
            )
    finally:
        if owned_conn:
            db_conn.close()

    ordered_rows = [rows.setdefault(uid, {"uid": uid, "alias": ""}) for uid in ordered_uids]
    return pd.DataFrame(ordered_rows)


def _query_metadata_frame_v1(
    strategy: _SetSqliteH5Strategy,
    *,
    uids: list[str] | None = None,
) -> pd.DataFrame:
    """读取 legacy v1 metadata frame。"""

    with strategy._connect() as conn:
        target_uids = list(uids) if uids is not None else None
        if target_uids:
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
        else:
            rows = conn.execute(
                """
                SELECT s.uid, m.key, m.value_text, m.value_int, m.value_real, m.value_bool, m.value_json
                FROM sample AS s
                LEFT JOIN sample_metadata_flat AS m
                  ON s.sample_id = m.sample_id
                ORDER BY s.sample_id, m.key
                """
            ).fetchall()

    ordered_uids = target_uids or list(dict.fromkeys(str(row["uid"]) for row in rows))
    if not ordered_uids:
        return pd.DataFrame()

    bucket: dict[str, dict[str, Any]] = {uid: {} for uid in ordered_uids}
    for row in rows:
        uid = str(row["uid"])
        key = row["key"]
        if key is None:
            continue
        bucket[uid][str(key)] = _decode_metadata_value(row)
    return pd.DataFrame([bucket[uid] for uid in ordered_uids if uid in bucket])


def _query_summary_frame_v1(
    strategy: _SetSqliteH5Strategy,
    *,
    conn: sqlite3.Connection | None = None,
    uids: list[str] | None = None,
    metadata_fields: list[str] | None = None,
    data_vars: list[str] | None = None,
    features: list[str] | None = None,
) -> pd.DataFrame:
    """读取 legacy v1 summary frame。"""

    requested_metadata = [str(field) for field in metadata_fields or ()]
    requested_features = [str(feature) for feature in features or ()]
    requested_data_vars = [str(data_var) for data_var in data_vars or ()]
    feature_keys, data_var_prefixes = _projection_request(
        requested_features=requested_features,
        requested_data_vars=requested_data_vars,
    )
    owned_conn = conn is None
    db_conn = conn or strategy._connect()
    try:
        target_uids = list(uids) if uids is not None else None
        sample_rows = _load_sample_rows(db_conn, uids=target_uids, columns="sample_id, uid, alias")

        ordered_uids = target_uids or [str(row["uid"]) for row in sample_rows]
        if not ordered_uids:
            return pd.DataFrame()

        sample_ids = [int(row["sample_id"]) for row in sample_rows]
        id_to_uid = {int(row["sample_id"]): str(row["uid"]) for row in sample_rows}
        rows: dict[str, dict[str, Any]] = {
            str(row["uid"]): {"uid": str(row["uid"]), "alias": str(row["alias"])} for row in sample_rows
        }

        if requested_metadata and sample_ids:
            metadata_placeholders = ", ".join("?" for _ in requested_metadata)
            sample_id_placeholders = ", ".join("?" for _ in sample_ids)
            metadata_rows = db_conn.execute(
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
                rows[uid][str(row["key"])] = _decode_metadata_value(row)

        projection_rows = _query_projection_rows(
            db_conn,
            sample_ids=sample_ids,
            feature_keys=feature_keys,
            data_var_prefixes=data_var_prefixes,
        )
        if projection_rows:
            _merge_projection_rows(
                rows=rows,
                projection_rows=projection_rows,
                id_to_uid=id_to_uid,
                requested_feature_keys=feature_keys,
                requested_data_var_prefixes=data_var_prefixes,
            )
    finally:
        if owned_conn:
            db_conn.close()

    ordered_rows = [rows.setdefault(uid, {"uid": uid, "alias": ""}) for uid in ordered_uids]
    return pd.DataFrame(ordered_rows)


def _merge_projection_rows(
    *,
    rows: dict[str, dict[str, Any]],
    projection_rows: list[sqlite3.Row],
    id_to_uid: dict[int, str],
    requested_feature_keys: set[str],
    requested_data_var_prefixes: tuple[str, ...],
) -> None:
    """将 projection 查询结果合并到 summary 行。"""

    for row in projection_rows:
        key = str(row["key"])
        if key not in requested_feature_keys and not (
            requested_data_var_prefixes and key.startswith(requested_data_var_prefixes)
        ):
            continue
        uid = id_to_uid[int(row["sample_id"])]
        rows[uid][key] = float(row["value_real"]) if row["value_real"] is not None else row["value_text"]


__all__ = [
    "_build_metadata_artifacts",
    "_build_presence_artifacts",
    "_build_summary_artifacts",
    "_build_summary_rows",
    "_decode_metadata_value",
    "_flatten_metadata_rows",
    "_metadata_value_columns",
    "_query_metadata_frame_v1",
    "_query_metadata_frame_v2",
    "_query_summary_frame_v1",
    "_query_summary_frame_v2",
    "_summary_scalar_row",
]
