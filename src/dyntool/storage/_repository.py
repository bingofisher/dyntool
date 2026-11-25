"""存储仓库自动识别与完整性检查。"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Literal

import h5py
import pandas as pd
import numpy as np

from ..compute.units import get_unit_registry
from ..domain._provenance import _ResultProvenance
from ..domain.constants import parse_label_unit, SAMPLE_ATTR_TO_DATA_CATEGORY
from ..domain.models import DataModelBase
from ..infrastructure._storage_commit import _WriteMarker
from ..infrastructure.sample_storage_sqlite_h5_payload import _read_group_payload
from ..infrastructure.sample_storage_sqlite_h5_projection import _build_summary_rows

from ..infrastructure.storage_constants import (
    DATA_NPZ_FILENAME,
    DEFAULT_SQLITE_INDEX_FILENAME,
    DEFAULT_SQLITE_PAYLOAD_H5_FILENAME,
    H5_ATTR_METADATA_JSON,
    H5_ATTR_UID,
    META_COL_NAME,
    META_COL_UID,
    META_COL_METADATA_JSON,
    METADATA_JSON_FILENAME,
    METADATA_TABLE_FILENAME,
)
from .types import StorageRepositoryReport, StorageScheme

_H5_SUFFIXES = {".h5", ".hdf5", ".hdf"}
_InspectLevel = Literal["quick", "deep"]
_StorageKind = Literal["sample", "sample_set"]


class _RepositoryPayloadInspector:
    """只读核对 SQLite 投影、H5 单位和可重算摘要。"""

    def __init__(self, conn: sqlite3.Connection, h5_file: h5py.File, issues: list[str]) -> None:
        self.conn = conn
        self.h5_file = h5_file
        self.issues = issues

    @classmethod
    def validate_units(cls, payload: dict[str, Any]) -> None:
        """递归验证载荷的单位声明，不猜测未记录的自定义模型类型。"""
        if "_dyntool" in payload:
            _ResultProvenance.validate(payload["_dyntool"])
        for unit in payload.get("_units", {}).values():
            get_unit_registry().Unit(unit)
        for key, value in payload.items():
            if key != "_units" and isinstance(value, dict):
                cls.validate_units(value)

    @classmethod
    def restore_slot(
        cls,
        name: str,
        payload: dict[str, Any],
        states: dict[str, Any],
        *,
        model_type: type[DataModelBase] | None = None,
    ) -> DataModelBase:
        """按正式类别或已注册索引类型恢复槽位，不猜测未知扩展。"""
        cls.validate_units(payload)
        if model_type is None:
            category = SAMPLE_ATTR_TO_DATA_CATEGORY.get(name, name)
            try:
                model_type = DataModelBase.from_category(category)
            except (KeyError, ValueError) as error:
                raise ValueError(f"检查受限：无法解析槽位类型 {name}") from error
        model = model_type.from_dict(payload)
        record = states.get(name)
        if record is not None:
            _ResultProvenance.validate(record)
            stored = payload.get("_dyntool")
            if stored is not None:
                left = {key: value for key, value in stored.items() if key != "status"}
                right = {key: value for key, value in record.items() if key != "status"}
                if left != right:
                    raise ValueError(f"追溯载荷版本或计算依据不一致：{name}")
                if stored["status"] != record["status"] and (stored["status"], record["status"]) != ("fresh", "stale"):
                    raise ValueError(f"追溯状态不得从过期或未知提升为有效：{name}")
            if record["status"] == "fresh" and any(
                states.get(source, {}).get("revision") != revision or states.get(source, {}).get("status") == "stale"
                for source, revision in record.get("inputs", {}).items()
            ):
                raise ValueError(f"有效结果的输入依据不一致：{name}")
        return model

    @classmethod
    def check_slots(cls, payloads: dict[str, Any], metadata: dict[str, Any], location: str, issues: list[str]) -> None:
        """各策略共用恢复校验，错误包含实际位置和槽位名。"""
        states = metadata.get("_dyntool_state", {})
        for name, payload in payloads.items():
            try:
                cls.restore_slot(name, payload, states)
            except Exception as error:
                issues.append(f"payload 单位或内容无效：{location}/{name}：{error}")

    @classmethod
    def check_h5_slots(cls, group: h5py.Group, issues: list[str]) -> None:
        """读取各槽位的完整载荷并定位无效单位或损坏数据集。"""
        metadata = json.loads(str(group.attrs.get(H5_ATTR_METADATA_JSON, "{}")))
        for name, node in group.items():
            if not isinstance(node, h5py.Group):
                issues.append(f"槽位不是 Group：{group.name}/{name}")
                continue
            try:
                cls.restore_slot(name, _read_group_payload(node), metadata.get("_dyntool_state", {}))
            except Exception as error:
                issues.append(f"payload 单位或内容无效：{node.name}：{error}")

    def check(self) -> None:
        rows = self.conn.execute(
            "SELECT p.*, s.uid, s.payload_id, s.metadata_json FROM sample_slot_presence p JOIN sample s USING(sample_id)"
        ).fetchall()
        projections_by_sample: dict[int, list[sqlite3.Row]] = {}
        for projection in self.conn.execute(
            "SELECT sample_id, key, value_real, value_text, unit FROM sample_summary_projection"
        ):
            projections_by_sample.setdefault(projection["sample_id"], []).append(projection)
        for row in rows:
            if not row["exists_flag"]:
                continue
            path = str(row["h5_path"])
            expected_path = f"/samples/{row['payload_id']}/slots/{row['slot_name']}"
            if path != expected_path:
                self.issues.append(f"槽位索引与 payload 版本不一致：{row['uid']}：{path}")
            if path not in self.h5_file:
                continue
            try:
                payload = _read_group_payload(self.h5_file[path])
                states = json.loads(row["metadata_json"]).get("_dyntool_state", {})
                model_type = next(
                    (kind for kind in DataModelBase._registry.values() if kind.__name__ == str(row["model_type"])), None
                )
                if model_type is None:
                    raise ValueError(f"检查受限：无法解析已登记模型类型 {row['model_type']}")
                model = self.restore_slot(str(row["slot_name"]), payload, states, model_type=model_type)
                expected = _build_summary_rows({str(row["slot_name"]): model})
                projections = projections_by_sample.get(row["sample_id"], [])
                missing = set(expected) - {str(projection["key"]) for projection in projections}
                for key in sorted(missing):
                    self.issues.append(f"摘要缺失：{row['uid']}：{key}")
                for projection in projections:
                    key = str(projection["key"])
                    if key == "_dyntool_state":
                        if json.loads(projection["value_text"]) != states:
                            self.issues.append(f"追溯与摘要不一致：{row['uid']}")
                        continue
                    if key not in expected:
                        continue
                    actual = expected[key]
                    left, right = projection["value_real"], actual["value_real"]
                    same_number = (
                        left is None
                        and right is None
                        or (
                            left is not None
                            and right is not None
                            and np.isclose(left, right, rtol=1e-7, atol=1e-12, equal_nan=True)
                        )
                    )
                    if (
                        not same_number
                        or projection["value_text"] != actual["value_text"]
                        or projection["unit"] != actual["unit"]
                    ):
                        self.issues.append(f"摘要与 payload 不一致：{row['uid']}：{key}")
            except Exception as exc:
                self.issues.append(f"payload 单位或内容无效：{path}：{exc}")


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
    marker_root = target if target.is_dir() else target.parent
    for marker in sorted(marker_root.glob(_WriteMarker.pattern)):
        try:
            reason = marker.read_text(encoding="utf-8")
        except OSError as exc:
            reason = str(exc)
        issues.append(f"发现未完成写入标记：{marker}；原因：{reason}")
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

    target = Path(path)
    root = target if target.is_dir() else target.parent
    if (root / DEFAULT_SQLITE_INDEX_FILENAME).exists():
        conn = sqlite3.connect((root / DEFAULT_SQLITE_INDEX_FILENAME).resolve().as_uri() + "?mode=ro", uri=True)
        try:
            conn.execute("BEGIN")
            conn.execute("SELECT name FROM sqlite_master LIMIT 1").fetchone()
            _WriteMarker.check(root)
        finally:
            conn.close()
    else:
        _WriteMarker.check(root)
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
        if any(
            child.suffix.lower() == ".json"
            for child in path.iterdir()
            if child.is_file() and not child.name.startswith(".dyntool-")
        ):
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
        if any(
            child.suffix.lower() == ".json"
            for child in path.iterdir()
            if child.is_file() and not child.name.startswith(".dyntool-")
        ):
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
        sample_files = [
            child
            for child in path.iterdir()
            if child.is_file() and not child.name.startswith(".dyntool-") and child.suffix.lower() == ".json"
        ]
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
            _RepositoryPayloadInspector.check_slots(
                payload.get("data", {}), payload.get("metadata", {}), str(path), issues
            )
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
                _RepositoryPayloadInspector.check_h5_slots(h5_file, issues)
        except Exception as exc:  # noqa: BLE001
            issues.append(f"单样本 H5 检查失败: {exc}")
    return 1


def _inspect_set_h5(path: Path, *, level: _InspectLevel, issues: list[str]) -> int | None:
    if path.is_dir():
        candidates = [
            item
            for item in path.iterdir()
            if item.suffix.lower() in _H5_SUFFIXES and not item.name.startswith(".dyntool-")
        ]
        if len(candidates) != 1:
            issues.append("SET_H5 目录需包含唯一集合文件，请指定具体 H5 路径")
            return None
        path = candidates[0]
    if path.suffix.lower() not in _H5_SUFFIXES:
        issues.append("SET_H5 必须使用 H5 后缀")
        return None
    try:
        with h5py.File(path, "r") as h5_file:
            sample_ids = [name for name in h5_file if not name.startswith(".dyntool-")]
            if level == "deep":
                for uid in sample_ids:
                    node = h5_file[uid]
                    if not isinstance(node, h5py.Group):
                        issues.append(f"样本节点不是 Group: {uid}")
                        continue
                    if H5_ATTR_METADATA_JSON not in node.attrs:
                        issues.append(f"样本组缺少 metadata_json 属性: {uid}")
                    _RepositoryPayloadInspector.check_h5_slots(node, issues)
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
        conn = sqlite3.connect(index_path.resolve().as_uri() + "?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        required_tables = {"sample", "sample_slot_presence", "sample_summary_projection"}
        table_rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        table_names = {str(row["name"]) for row in table_rows}
        user_version = int(conn.execute("PRAGMA user_version").fetchone()[0])
        if user_version > 2:
            issues.append(f"SQLite schema 版本 {user_version} 高于支持的版本 2")
        for table_name in sorted(required_tables - table_names):
            issues.append(f"SQLite 索引缺少数据表: {table_name}")
        if user_version < 2 and "sample_metadata_flat" not in table_names:
            issues.append("SQLite 索引缺少 v1 metadata 表：sample_metadata_flat")
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
                    _RepositoryPayloadInspector(conn, h5_file, issues).check()
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
            try:
                metadata = json.loads(str(row.get(META_COL_METADATA_JSON, "{}")))
            except (TypeError, ValueError) as error:
                issues.append(f"属性样本 metadata 无效：{row.get(META_COL_UID, '')}：{error}")
                continue
            name = str(row.get(META_COL_NAME, "")).strip()
            if not name:
                continue
            found_any = False
            for category_dir in category_dirs:
                for suffix in (".csv", ".npy"):
                    payload_path = category_dir / f"{name}{suffix}"
                    if not payload_path.exists():
                        continue
                    found_any = True
                    try:
                        if suffix == ".csv":
                            frame = pd.read_csv(payload_path)
                            for column in frame.columns:
                                _, unit = parse_label_unit(column)
                                if unit:
                                    get_unit_registry().Unit(unit)
                            kind = DataModelBase.from_category(
                                SAMPLE_ATTR_TO_DATA_CATEGORY.get(category_dir.name, category_dir.name)
                            )
                            model = kind.from_pandas(frame.set_index(frame.columns[0]))
                            recovered = model.to_dict()
                            recovered.pop("_dyntool", None)
                            _RepositoryPayloadInspector.restore_slot(
                                category_dir.name, recovered, metadata.get("_dyntool_state", {})
                            )
                        else:
                            payload = np.load(payload_path, allow_pickle=True).item()
                            _RepositoryPayloadInspector.restore_slot(
                                category_dir.name, payload, metadata.get("_dyntool_state", {})
                            )
                    except Exception as error:
                        issues.append(f"属性 payload 单位或内容无效：{payload_path}：{error}")
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
                continue
            try:
                metadata_payload = json.loads((child / METADATA_JSON_FILENAME).read_text(encoding="utf-8"))
                with np.load(child / DATA_NPZ_FILENAME, allow_pickle=True) as payload:
                    _RepositoryPayloadInspector.check_slots(
                        {category: payload[category].item() for category in payload.files},
                        metadata_payload.get("metadata", metadata_payload),
                        str(child),
                        issues,
                    )
            except Exception as error:
                issues.append(f"目录 payload 单位或内容无效：{child}：{error}")
    return len(valid_dirs)


__all__ = [
    "detect_storage_scheme",
    "inspect_storage_repository",
    "validate_detected_scheme",
]
