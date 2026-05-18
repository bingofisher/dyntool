"""Web 工作台运行时服务。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from dyntool import AccelSeries, DefaultSample, DefaultSampleSet, SampleDomain, VibrationTestMetadata


SLOT_NAMES = ("accel", "vel", "disp", "force", "freqspec", "respspec", "otovl", "zvl", "fdmvl", "fpvdv")


def build_demo_sample_set() -> DefaultSampleSet:
    """构造 Web 首屏可用的演示样本集。"""

    axis = np.linspace(0.0, 10.0, 512)
    samples = []
    for index in range(3):
        accel = AccelSeries.from_arrays(
            axis,
            np.sin(axis * (index + 1)) * (1.0 + index * 0.2),
            axis_unit="s",
            data_unit="m/s^2",
        )
        sample = DefaultSample.from_models(
            accel=accel,
            sample_domain=SampleDomain.VIBRATION_TEST,
            metadata_cls=VibrationTestMetadata,
            case=f"C-{index + 1}",
            point=f"P-{index + 1}",
            instr=f"ACC-{index + 1}",
            dir="Z",
            record=f"R-{index + 1}",
            timestamp=f"2026-04-28 09:0{index}:00",
        )
        sample.set_alias(f"Web 样本 {index + 1}")
        samples.append(sample)
    return DefaultSampleSet.from_samples(samples, sample_domain=SampleDomain.VIBRATION_TEST)


def summarize_sample_set(sample_set: object, *, name: str = "主样本集 / Web") -> dict[str, Any]:
    """构造主样本集摘要。"""

    items = list(sample_set.items())  # type: ignore[attr-defined]
    first_sample = items[0][1] if items else None
    metadata_fields = []
    if first_sample is not None:
        metadata_fields = list(getattr(type(first_sample.metadata), "model_fields", {}).keys())
    return {
        "name": name,
        "class_name": type(sample_set).__name__,
        "sample_count": len(sample_set),  # type: ignore[arg-type]
        "metadata_fields": metadata_fields,
        "storage_binding": "Web 内存运行态",
    }


def build_capability(sample_set: object) -> dict[str, Any]:
    """构造能力快照。"""

    slots = sorted({name for _, sample in _iter_capability_samples(sample_set) for name in _sample_slots(sample)})
    return {
        "data_slots": slots,
        "eval_results": [name for name in ("zvl", "otovl", "fdmvl", "fpvdv") if name in slots],
        "scalar_frame": True,
        "series_frame": bool(slots),
        "peaks_frame": any(name in slots for name in ("accel", "vel", "disp", "force")),
    }


def resolve_first_sample(sample_set: object, selected_uid: str = "") -> tuple[str, object]:
    """解析首个或指定样本。"""

    items = list(sample_set.items())  # type: ignore[attr-defined]
    if not items:
        raise ValueError("当前主样本集为空。")
    if selected_uid:
        for uid, sample in items:
            if str(uid) == selected_uid or str(getattr(sample, "alias", "")) == selected_uid:
                return str(uid), sample
        raise ValueError(f"未找到样本：{selected_uid}")
    uid, sample = items[0]
    return str(uid), sample


def ensure_directory(path_text: str) -> Path:
    """校验目录路径。"""

    path = Path(path_text).expanduser().resolve()
    if not path.exists():
        raise ValueError(f"路径不存在：{path}")
    if not path.is_dir():
        raise ValueError(f"路径不是目录：{path}")
    return path


def scope_uids(state_scope: dict[str, str], *, saved_subsets: list[dict[str, Any]] | None = None) -> list[str]:
    """从当前工作范围解析 UID 列表。"""

    scope_kind = state_scope.get("scope_kind")
    if scope_kind == "saved_subset":
        target = state_scope.get("target", "")
        for subset in saved_subsets or []:
            if subset.get("name") == target:
                return [str(uid) for uid in subset.get("uids", [])]
        return []
    if scope_kind not in {"uid_list", "temporary_selection"}:
        return []
    target = state_scope.get("target", "")
    return [item.strip() for item in target.split(",") if item.strip()]


def scope_first_uid(state_scope: dict[str, str], *, saved_subsets: list[dict[str, Any]] | None = None) -> str:
    """返回当前工作范围中的首个 UID。"""

    uids = scope_uids(state_scope, saved_subsets=saved_subsets)
    return uids[0] if uids else ""


def _iter_capability_samples(sample_set: object) -> list[tuple[str, object]]:
    items = list(sample_set.items())  # type: ignore[attr-defined]
    if len(items) <= 8:
        return [(str(uid), sample) for uid, sample in items]
    return [(str(uid), sample) for uid, sample in items[:8]]


def _sample_slots(sample: object) -> tuple[str, ...]:
    return tuple(name for name in SLOT_NAMES if getattr(sample, name, None) is not None)
