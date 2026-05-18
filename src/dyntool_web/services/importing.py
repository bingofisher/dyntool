"""Web 真实仓库导入服务。"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

import dyntool.storage as dt_storage
from dyntool import StorageScheme, VibrationTestMetadata, VibrationTestSampleSet
from dyntool.storage import SampleLoadMode

from ..state import WebSessionState
from .runtime import build_capability, build_demo_sample_set, summarize_sample_set


def preview_repository(state: WebSessionState, source_path: str) -> dict[str, Any]:
    """轻量预览真实样本集仓库。"""

    path = _resolve_repository_path(source_path)
    state.remember_path(path)
    report = dt_storage.inspect_storage_repository(
        path,
        storage_scheme=StorageScheme.SET_SQLITE_H5,
        level="quick",
    )
    metadata_mode = ""
    categories: tuple[str, ...] = ()
    sample_set = None
    if report.is_valid:
        sample_set = _load_repository(path)
        metadata_mode = _metadata_mode(sample_set)
        categories = _available_categories(sample_set)
        state.import_preview_cache = {
            "source_path": str(path),
            "sample_set": sample_set,
            "report": report,
            "metadata_mode": metadata_mode,
            "categories": categories,
        }
    task = state.add_task(
        "导入轻量预览",
        "已完成" if report.is_valid else "有问题",
        "1 / 1",
        f"样本数：{report.sample_count}；存储：{_scheme_name(report.detected_scheme)}",
    )
    return {
        "source_path": str(path),
        "detected_scheme": _scheme_name(report.detected_scheme),
        "sample_count": report.sample_count,
        "metadata_mode": metadata_mode,
        "available_series_categories": list(categories),
        "allow_execute": bool(report.is_valid),
        "issues": list(report.issues),
        "warnings": list(report.warnings),
        "task": asdict(task),
    }


def bind_repository(state: WebSessionState, source_path: str, *, demo: bool) -> dict[str, Any]:
    """绑定 demo 或真实仓库为当前主样本集。"""

    path = _resolve_repository_path(source_path)
    state.remember_path(path)
    if demo:
        sample_set = build_demo_sample_set()
        binding = "Web demo / memory"
        preview_reused = False
    else:
        cached = state.import_preview_cache if state.import_preview_cache.get("source_path") == str(path) else {}
        if cached:
            report = cached["report"]
            sample_set = cached["sample_set"]
            preview_reused = True
        else:
            report = dt_storage.inspect_storage_repository(
                path,
                storage_scheme=StorageScheme.SET_SQLITE_H5,
                level="quick",
            )
            if not report.is_valid:
                raise ValueError("真实仓库检查未通过：" + "；".join(report.issues))
            sample_set = _load_repository(path)
            preview_reused = False
        binding = f"{_scheme_name(report.detected_scheme)} / read_only"
    state.mark_primary_changed()
    state.primary_runtime = sample_set
    state.primary_summary = summarize_sample_set(sample_set, name=f"主样本集 / {path.name}")
    state.primary_summary["storage_binding"] = binding
    state.capability = build_capability(sample_set)
    task = state.add_task(
        "绑定主样本集",
        "已完成",
        "1 / 1",
        f"已绑定 {len(sample_set)} 个样本；{binding}",
    )
    return {
        "primary": state.primary_summary,
        "capability": state.capability,
        "task": asdict(task),
        "preview_reused": preview_reused,
    }


def _load_repository(path: Path) -> VibrationTestSampleSet:
    return VibrationTestSampleSet.from_storage(
        path,
        storage_scheme=StorageScheme.SET_SQLITE_H5,
        load_mode=SampleLoadMode.LAZY,
    )


def _resolve_repository_path(source_path: str) -> Path:
    path = Path(source_path).expanduser().resolve()
    if not path.exists():
        raise ValueError(f"路径不存在：{path}")
    if path.is_file():
        path = path.parent
    if _looks_like_repository(path):
        return path
    child_repositories = [item for item in path.iterdir() if item.is_dir() and _looks_like_repository(item)]
    if len(child_repositories) == 1:
        return child_repositories[0].resolve()
    if child_repositories:
        names = "；".join(item.name for item in child_repositories[:8])
        raise ValueError(f"当前目录下存在多个候选样本集仓库，请指定其中一个：{names}")
    return path


def _looks_like_repository(path: Path) -> bool:
    return (path / "index.sqlite").is_file() and (path / "payload.h5").is_file()


def _metadata_mode(sample_set: object) -> str:
    for _, sample in sample_set.items():  # type: ignore[attr-defined]
        metadata = getattr(sample, "metadata", None)
        if isinstance(metadata, VibrationTestMetadata):
            return "vibration_test_metadata"
        return type(metadata).__name__ if metadata is not None else ""
    return ""


def _available_categories(sample_set: object) -> tuple[str, ...]:
    for _, sample in sample_set.items():  # type: ignore[attr-defined]
        return tuple(
            name
            for name in ("accel", "vel", "disp", "force", "freqspec", "respspec", "otovl", "zvl", "fdmvl", "fpvdv")
            if getattr(sample, name, None) is not None
        )
    return ()


def _scheme_name(value: object) -> str:
    if isinstance(value, StorageScheme):
        return value.name
    return str(value)
