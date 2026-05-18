"""GUI 真库集成测试辅助工具。"""

from __future__ import annotations

import os
import platform
from pathlib import Path
from time import perf_counter
import tomllib
from itertools import islice

from dyntool import StorageScheme, VibrationTestSampleSet
from dyntool.storage import SampleLoadMode

_PR13_CONFIG_PATH = Path("D:/BaiduSyncdisk/13_CodeRepository/Projects/P-R1-3/configs/paths.toml")


def resolve_pr13_data_dir() -> Path | None:
    """解析 P-R1-3 工程库的真实 data 目录。"""

    env_path = os.environ.get("ADVDYNTOOL_PR13_DATA_DIR", "").strip()
    if env_path:
        candidate = Path(env_path).expanduser().resolve()
        return candidate if candidate.exists() else None

    if not _PR13_CONFIG_PATH.exists():
        return None

    payload = tomllib.loads(_PR13_CONFIG_PATH.read_text(encoding="utf-8"))
    machine = os.environ.get("COMPUTERNAME") or platform.node()
    machine_payload = payload.get("machines", {}).get(machine)
    if not isinstance(machine_payload, dict):
        return None

    external_roots = machine_payload.get("external_roots")
    subdirs = payload.get("subdirs", {})
    if not isinstance(external_roots, list) or not external_roots:
        return None
    if "data" not in subdirs:
        return None

    candidate = (Path(str(external_roots[0])).expanduser() / str(subdirs["data"])).resolve()
    return candidate if candidate.exists() else None


def resolve_pr13_subset_uids(limit: int = 3) -> tuple[str, ...]:
    """返回真实工程库中固定数量的样本 UID。"""

    data_dir = resolve_pr13_data_dir()
    if data_dir is None:
        return ()

    sample_set = VibrationTestSampleSet.from_storage(
        data_dir,
        storage_scheme=StorageScheme.SET_SQLITE_H5,
        load_mode=SampleLoadMode.LAZY,
    )
    return tuple(str(uid) for uid, _ in islice(sample_set.items(), limit))


def record_stage_timing(
    records: list[dict[str, object]],
    stage_name: str,
    started_at: float,
    *,
    sample_count: int | None = None,
    category_count: int | None = None,
    failure_stage: str = "",
    error_summary: str = "",
) -> int:
    """记录单个阶段的耗时与摘要。"""

    duration_ms = int((perf_counter() - started_at) * 1000)
    records.append(
        {
            "stage": stage_name,
            "duration_ms": duration_ms,
            "sample_count": sample_count,
            "category_count": category_count,
            "failure_stage": failure_stage,
            "error_summary": error_summary,
        }
    )
    return duration_ms
