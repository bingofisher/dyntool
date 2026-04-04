"""存储仓库自动识别与完整性检查。"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Literal

import h5py
import pandas as pd

from ..infrastructure.storage_constants import (
    DATA_NPZ_FILENAME,
    DEFAULT_SQLITE_INDEX_FILENAME,
    DEFAULT_SQLITE_PAYLOAD_H5_FILENAME,
    H5_ATTR_METADATA_JSON,
    H5_ATTR_UID,
    META_COL_NAME,
    META_COL_UID,
    METADATA_JSON_FILENAME,
    METADATA_TABLE_FILENAME,
)
from .types import StorageRepositoryReport, StorageScheme

_H5_SUFFIXES = {".h5", ".hdf5", ".hdf"}
_InspectLevel = Literal["quick", "deep"]
_StorageKind = Literal["sample", "sample_set"]


def detect_storage_scheme(
    path: str | Path,
    *,
    kind: _StorageKind | None = None,
) -> StorageScheme:
    """根据路径和存储签名自动识别正式存储方案。"""

    target = Path(path)
    if kind == "sample":
        return _detect_sample_scheme(target)
    if kind == "sample_set":
        return _detect_sample_set_scheme(target)
    if target.is_dir():
        return _detect_sample_set_scheme(target)
    if target.suffix.lower() == ".json":
        return StorageScheme.SAMPLE_JSON
    if target.suffix.lower() in _H5_SUFFIXES:
        return _detect_h5_scheme(target)
    raise ValueError(f"无法从路径自动识别 storage_scheme: {target}")


def inspect_storage_repository(
    path: str | Path,
    *,
    storage_scheme: StorageScheme | None = None,
    level: _InspectLevel = "quick",
) -> StorageRepositoryReport:
    """检查存储仓库的结构与完整性。"""

    target = Path(path)
    issues: list[str] = []
    warnings: list[str] = []
    detected_scheme: StorageScheme | None = None
    if target.exists():
        try:
            detected_scheme = detect_storage_scheme(target)
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"自动识别失败: {exc}")
    elif storage_scheme is None:
        warnings.append("路径不存在，无法自动识别 storage_scheme")

    effective_scheme = storage_scheme or detected_scheme
    if effective_scheme is None:
        issues.append("无法确定 storage_scheme")
        return StorageRepositoryReport(
            path=target,
            detected_scheme=detected_scheme,
            requested_scheme=storage_scheme,
            level=level,
            exists=target.exists(),
            is_valid=False,
            issues=tuple(issues),
            warnings=tuple(warnings),
            sample_count=None,
        )

    if storage_scheme is not None and detected_scheme is not None and storage_scheme is not detected_scheme:
        issues.append(f"显式 storage_scheme={storage_scheme.value} 与自动识别结果 {detected_scheme.value} 不一致")

    sample_count = _inspect_by_scheme(target, effective_scheme, level=level, issues=issues, warnings=warnings)
    return StorageRepositoryReport(
        path=target,
        detected_scheme=detected_scheme,
        requested_scheme=storage_scheme,
        level=level,
        exists=target.exists(),
        is_valid=not issues,
        issues=tuple(issues),
        warnings=tuple(warnings),
        sample_count=sample_count,
    )


def validate_detected_scheme(
    path: str | Path,
    *,
    requested_scheme: StorageScheme | None,
    kind: _StorageKind,
) -> StorageScheme:
    """在读路径上解析并校验显式 `storage_scheme`。"""

    detected = detect_storage_scheme(path, kind=kind)
    if requested_scheme is not None and requested_scheme is not detected:
        raise ValueError(
            f"storage_scheme 与路径实际结构不一致: 显式值为 {requested_scheme.value}，自动识别为 {detected.value}"
        )
    return requested_scheme or detected


def _detect_sample_scheme(path: Path) -> StorageScheme:
    if path.is_dir():
        h5_files = [child for child in path.iterdir() if child.is_file() and child.suffix.lower() in _H5_SUFFIXES]
        if h5_files and any(_detect_h5_scheme(child) is StorageScheme.SET_H5 for child in h5_files):
            return StorageScheme.SET_H5
        if any(child.suffix.lower() == ".json" for child in path.iterdir() if child.is_file()):
            return StorageScheme.SAMPLE_JSON
        if h5_files:
            return StorageScheme.SAMPLE_H5
        raise ValueError(f"无法识别单样本目录结构: {path}")
    suffix = path.suffix.lower()
    if suffix == ".json":
        return StorageScheme.SAMPLE_JSON
    if suffix in _H5_SUFFIXES:
        detected = _detect_h5_scheme(path)
        if detected is StorageScheme.SET_H5:
            raise ValueError(f"路径更像样本集 H5，而不是单样本 H5: {path}")
        return detected
    raise ValueError(f"无法识别单样本存储方案: {path}")


def _detect_sample_set_scheme(path: Path) -> StorageScheme:
    if path.is_dir():
        if (path / DEFAULT_SQLITE_INDEX_FILENAME).exists() and (path / DEFAULT_SQLITE_PAYLOAD_H5_FILENAME).exists():
            return StorageScheme.SET_SQLITE_H5
        if (path / METADATA_TABLE_FILENAME).exists():
            return StorageScheme.SET_ATTR_TABLE
        if any((child / METADATA_JSON_FILENAME).exists() for child in path.iterdir() if child.is_dir()):
            return StorageScheme.SET_DIR
        h5_files = [child for child in path.iterdir() if child.is_file() and child.suffix.lower() in _H5_SUFFIXES]
        if h5_files and any(_detect_h5_scheme(child) is StorageScheme.SET_H5 for child in h5_files):
            return StorageScheme.SET_H5
        if any(child.suffix.lower() == ".json" for child in path.iterdir() if child.is_file()):
            return StorageScheme.SAMPLE_JSON
        if h5_files:
            return StorageScheme.SAMPLE_H5
        raise ValueError(f"无法识别样本集目录结构: {path}")
    if path.suffix.lower() in _H5_SUFFIXES:
        detected = _detect_h5_scheme(path)
        if detected is StorageScheme.SAMPLE_H5:
            raise ValueError(f"路径更像单样本 H5，而不是样本集 H5: {path}")
        return StorageScheme.SET_H5
    raise ValueError(f"无法识别样本集存储方案: {path}")


def _detect_h5_scheme(path: Path) -> StorageScheme:
    if not path.exists():
        return StorageScheme.SET_H5
    with h5py.File(path, "r") as h5_file:
        if H5_ATTR_UID in h5_file.attrs or H5_ATTR_METADATA_JSON in h5_file.attrs:
            return StorageScheme.SAMPLE_H5
        return StorageScheme.SET_H5


def _inspect_by_scheme(
    path: Path,
    scheme: StorageScheme,
    *,
    level: _InspectLevel,
    issues: list[str],
    warnings: list[str],
) -> int | None:
    if not path.exists():
        issues.append(f"路径不存在: {path}")
        return None

    if scheme is StorageScheme.SAMPLE_JSON:
        return _inspect_sample_json(path, level=level, issues=issues)
    if scheme is StorageScheme.SAMPLE_H5:
        return _inspect_sample_h5(path, level=level, issues=issues)
    if scheme is StorageScheme.SET_H5:
        return _inspect_set_h5(path, level=level, issues=issues)
    if scheme is StorageScheme.SET_SQLITE_H5:
        return _inspect_set_sqlite_h5(path, level=level, issues=issues)
    if scheme is StorageScheme.SET_ATTR_TABLE:
        return _inspect_set_attr_table(path, level=level, issues=issues, warnings=warnings)
    if scheme is StorageScheme.SET_DIR:
        return _inspect_set_dir(path, level=level, issues=issues)
    issues.append(f"不支持的 storage_scheme: {scheme.value}")
    return None


def _inspect_sample_json(path: Path, *, level: _InspectLevel, issues: list[str]) -> int | None:
    if path.is_dir():
        sample_files = [child for child in path.iterdir() if child.is_file() and child.suffix.lower() == ".json"]
        if not sample_files:
            issues.append("SAMPLE_JSON 目录下未找到 .json 样本文件")
            return None
        if level == "deep":
            for sample_file in sample_files:
                _inspect_sample_json(sample_file, level=level, issues=issues)
        return len(sample_files)
    if path.suffix.lower() != ".json":
        issues.append("单样本 JSON 必须使用 .json 后缀")
        return None
    if level == "deep":
        try:
            with open(path, encoding="utf-8") as file:
                payload = json.load(file)
            if "metadata" not in payload:
                issues.append("单样本 JSON 缺少 metadata 段")
        except Exception as exc:  # noqa: BLE001
            issues.append(f"单样本 JSON 解析失败: {exc}")
    return 1


def _inspect_sample_h5(path: Path, *, level: _InspectLevel, issues: list[str]) -> int | None:
    if path.is_dir():
        sample_files = [child for child in path.iterdir() if child.is_file() and child.suffix.lower() in _H5_SUFFIXES]
        if not sample_files:
            issues.append("SAMPLE_H5 目录下未找到 H5 样本文件")
            return None
        if level == "deep":
            for sample_file in sample_files:
                _inspect_sample_h5(sample_file, level=level, issues=issues)
        return len(sample_files)
    if path.suffix.lower() not in _H5_SUFFIXES:
        issues.append("单样本 H5 必须使用 H5 后缀")
        return None
    if level == "deep":
        try:
            with h5py.File(path, "r") as h5_file:
                if H5_ATTR_UID not in h5_file.attrs:
                    issues.append("单样本 H5 缺少 uid 属性")
                if H5_ATTR_METADATA_JSON not in h5_file.attrs:
                    issues.append("单样本 H5 缺少 metadata_json 属性")
        except Exception as exc:  # noqa: BLE001
            issues.append(f"单样本 H5 检查失败: {exc}")
    return 1


def _inspect_set_h5(path: Path, *, level: _InspectLevel, issues: list[str]) -> int | None:
    if path.suffix.lower() not in _H5_SUFFIXES:
        issues.append("SET_H5 必须使用 H5 后缀")
        return None
    try:
        with h5py.File(path, "r") as h5_file:
            sample_ids = list(h5_file.keys())
            if level == "deep":
                for uid in sample_ids:
                    node = h5_file[uid]
                    if not isinstance(node, h5py.Group):
                        issues.append(f"样本节点不是 Group: {uid}")
                        continue
                    if H5_ATTR_METADATA_JSON not in node.attrs:
                        issues.append(f"样本组缺少 metadata_json 属性: {uid}")
    except Exception as exc:  # noqa: BLE001
        issues.append(f"SET_H5 检查失败: {exc}")
        return None
    return len(sample_ids)


def _inspect_set_sqlite_h5(path: Path, *, level: _InspectLevel, issues: list[str]) -> int | None:
    if not path.is_dir():
        issues.append("SET_SQLITE_H5 必须是目录")
        return None
    index_path = path / DEFAULT_SQLITE_INDEX_FILENAME
    payload_path = path / DEFAULT_SQLITE_PAYLOAD_H5_FILENAME
    if not index_path.exists():
        issues.append("缺少 index.sqlite")
    if not payload_path.exists():
        issues.append("缺少 payload.h5")
    if issues:
        return None

    conn: sqlite3.Connection | None = None
    try:
        conn = sqlite3.connect(index_path)
        conn.row_factory = sqlite3.Row
        required_tables = {"sample", "sample_slot_presence", "sample_summary_projection"}
        table_rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        table_names = {str(row["name"]) for row in table_rows}
        user_version = int(conn.execute("PRAGMA user_version").fetchone()[0])
        for table_name in sorted(required_tables - table_names):
            issues.append(f"SQLite 索引缺少数据表: {table_name}")
        if user_version < 2 and "sample_metadata_flat" not in table_names:
            issues.append("SQLite 绱㈠紩缂哄皯 v1 metadata 琛? sample_metadata_flat")
        sample_rows = conn.execute("SELECT uid, payload_id FROM sample ORDER BY uid").fetchall()
        sample_count = len(sample_rows)
        if level == "deep" and not issues:
            with h5py.File(payload_path, "r") as h5_file:
                if "samples" not in h5_file:
                    issues.append("payload.h5 缺少 /samples 根组")
                else:
                    samples_group = h5_file["samples"]
                    for row in sample_rows:
                        payload_id = str(row["payload_id"])
                        if payload_id not in samples_group:
                            issues.append(f"payload.h5 缺少 payload 组: {payload_id}")
                    presence_rows = conn.execute(
                        "SELECT slot_name, h5_path FROM sample_slot_presence WHERE exists_flag = 1"
                    ).fetchall()
                    for row in presence_rows:
                        h5_path = str(row["h5_path"])
                        if h5_path not in h5_file:
                            issues.append(f"payload.h5 缺少槽位路径: {h5_path}")
        return sample_count
    except Exception as exc:  # noqa: BLE001
        issues.append(f"SET_SQLITE_H5 检查失败: {exc}")
        return None
    finally:
        try:
            if conn is not None:
                conn.close()
        except Exception:  # noqa: BLE001
            pass


def _inspect_set_attr_table(
    path: Path,
    *,
    level: _InspectLevel,
    issues: list[str],
    warnings: list[str],
) -> int | None:
    if not path.is_dir():
        issues.append("SET_ATTR_TABLE 必须是目录")
        return None
    metadata_path = path / METADATA_TABLE_FILENAME
    if not metadata_path.exists():
        issues.append("缺少 metadata.csv")
        return None
    try:
        metadata_df = pd.read_csv(metadata_path)
    except Exception as exc:  # noqa: BLE001
        issues.append(f"metadata.csv 读取失败: {exc}")
        return None

    sample_count = int(len(metadata_df))
    required_columns = {META_COL_UID, META_COL_NAME}
    missing_columns = required_columns - set(metadata_df.columns)
    for column in sorted(missing_columns):
        issues.append(f"metadata.csv 缺少列: {column}")

    if level == "deep" and not metadata_df.empty:
        category_dirs = [child for child in path.iterdir() if child.is_dir()]
        if not category_dirs:
            warnings.append("未发现属性分类目录")
        for _, row in metadata_df.iterrows():
            name = str(row.get(META_COL_NAME, "")).strip()
            if not name:
                continue
            found_any = False
            for category_dir in category_dirs:
                if (category_dir / f"{name}.csv").exists() or (category_dir / f"{name}.npy").exists():
                    found_any = True
                    break
            if not found_any:
                issues.append(f"属性样本缺少任何分类文件: {name}")
    return sample_count


def _inspect_set_dir(path: Path, *, level: _InspectLevel, issues: list[str]) -> int | None:
    if not path.is_dir():
        issues.append("SET_DIR 必须是目录")
        return None
    sample_dirs = [child for child in path.iterdir() if child.is_dir()]
    valid_dirs: list[Path] = []
    for child in sample_dirs:
        metadata_path = child / METADATA_JSON_FILENAME
        if metadata_path.exists():
            valid_dirs.append(child)
        elif level == "deep":
            issues.append(f"样本目录缺少 metadata.json: {child.name}")
    if not valid_dirs:
        issues.append("未发现合法样本子目录")
        return 0
    if level == "deep":
        for child in valid_dirs:
            if not (child / DATA_NPZ_FILENAME).exists():
                issues.append(f"样本目录缺少 data.npz: {child.name}")
    return len(valid_dirs)


__all__ = [
    "detect_storage_scheme",
    "inspect_storage_repository",
    "validate_detected_scheme",
]
