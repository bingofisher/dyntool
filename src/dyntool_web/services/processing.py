"""Web 处理服务。"""

from __future__ import annotations

from typing import Any

import numpy as np

from dyntool.compute.solvers import SDOFSolveMethod, WeightType
from dyntool.compute.units import UnitSystem

from ..state import WebSessionState
from .runtime import build_capability, scope_uids, summarize_sample_set


PROCESSING_ACTIONS: tuple[dict[str, Any], ...] = (
    {"action_name": "calc_freqspec", "label": "计算频谱", "defaults": {}},
    {
        "action_name": "calc_respspec",
        "label": "计算响应谱",
        "defaults": {
            "method": "nigam-jennings",
            "calc_unit_system": "",
            "output_unit_system": "",
            "periods": "0.1,0.5,1.0",
        },
    },
    {
        "action_name": "eval_zvl",
        "label": "计算 ZVL",
        "defaults": {
            "freq_range_min": "0.5",
            "freq_range_max": "80",
            "weight_type": "wk",
            "time_windows": "1",
            "calc_unit_system": "",
            "output_unit_system": "",
        },
    },
    {
        "action_name": "eval_otovl",
        "label": "计算 OTOVL",
        "defaults": {
            "freq_range_min": "0.5",
            "freq_range_max": "80",
            "time_windows": "1",
            "calc_unit_system": "",
            "output_unit_system": "",
        },
    },
    {
        "action_name": "eval_fdmvl",
        "label": "计算 FDMVL",
        "defaults": {
            "freq_range_min": "0.5",
            "freq_range_max": "80",
            "calc_unit_system": "",
            "output_unit_system": "",
        },
    },
    {
        "action_name": "eval_fpvdv",
        "label": "计算 FPVDV",
        "defaults": {
            "freq_range_min": "1",
            "freq_range_max": "40",
            "nsup": "4",
            "calc_unit_system": "",
            "output_unit_system": "",
        },
    },
)


def actions_payload() -> dict[str, Any]:
    """返回处理动作默认参数。"""

    return {"actions": list(PROCESSING_ACTIONS)}


def run_processing(
    state: WebSessionState,
    *,
    action_name: str,
    params: dict[str, str],
    strict: bool,
    overwrite: bool,
) -> dict[str, Any]:
    """执行处理动作。"""

    sample_set = _require_runtime(state)
    action = getattr(sample_set, action_name, None)
    if not callable(action):
        raise ValueError(f"当前主样本集不支持处理动作：{action_name}")
    merged_params = _merge_defaults(action_name, params)
    kwargs = _translate_action_kwargs(action_name, merged_params)
    state.start_task("执行分析", f"正在执行处理动作：{action_name}")
    selected_uids = scope_uids(state.current_scope, saved_subsets=state.saved_subsets)
    if selected_uids:
        kwargs["uids"] = selected_uids
    action(strict=strict, overwrite=overwrite, **kwargs)
    state.capability = build_capability(sample_set)
    state.primary_summary = summarize_sample_set(sample_set)
    state.add_task("执行分析", "已完成", "1 / 1", f"已执行处理动作：{action_name}")
    return {"message": f"已执行处理动作：{action_name}", "capability": state.capability}


def build_preview(state: WebSessionState, *, preview_kind: str, data_var: str, row_limit: int) -> dict[str, Any]:
    """生成轻量结果预览。"""

    sample_set = _require_runtime(state)
    state.start_task("生成结果预览", f"正在生成 {preview_kind} 预览。")
    selected_uids = scope_uids(state.current_scope, saved_subsets=state.saved_subsets) or _preview_uids(sample_set)
    if preview_kind == "series_frame":
        frame = sample_set.series_frame(data_var, strict=False, uids=selected_uids).head(row_limit)  # type: ignore[attr-defined]
    else:
        frame = sample_set.scalar_frame(strict=False, uids=selected_uids).head(row_limit)  # type: ignore[attr-defined]
    rows = [[str(index), *(str(value) for value in row)] for index, row in frame.iterrows()]
    payload = {"columns": ["index", *(str(item) for item in frame.columns)], "rows": rows}
    state.store_preview(payload)
    state.add_task("生成结果预览", "已完成", "1 / 1", f"已生成 {preview_kind} 预览。")
    return payload


def _preview_uids(sample_set: object, limit: int = 8) -> list[str]:
    return [str(uid) for uid, _ in list(sample_set.items())[:limit]]  # type: ignore[attr-defined]


def _require_runtime(state: WebSessionState) -> object:
    if state.primary_runtime is None:
        raise ValueError("当前没有可处理的主样本集。")
    return state.primary_runtime


def _merge_defaults(action_name: str, params: dict[str, str]) -> dict[str, str]:
    for item in PROCESSING_ACTIONS:
        if item["action_name"] == action_name:
            return {**item["defaults"], **params}
    return dict(params)


def _translate_action_kwargs(action_name: str, action_params: dict[str, str]) -> dict[str, Any]:
    translated: dict[str, Any] = {}
    if action_name == "calc_respspec":
        translated["method"] = SDOFSolveMethod(action_params.get("method", "nigam-jennings"))
        translated["calc_unit_system"] = _resolve_unit_system(action_params.get("calc_unit_system", ""))
        translated["output_unit_system"] = _resolve_unit_system(action_params.get("output_unit_system", ""))
        translated["periods"] = _parse_periods(action_params.get("periods", ""))
        return {key: value for key, value in translated.items() if value is not None}
    if action_name in {"eval_zvl", "eval_otovl", "eval_fdmvl", "eval_fpvdv"}:
        translated["freq_range"] = _parse_freq_range(
            action_params.get("freq_range_min", ""),
            action_params.get("freq_range_max", ""),
        )
        translated["calc_unit_system"] = _resolve_unit_system(action_params.get("calc_unit_system", ""))
        translated["output_unit_system"] = _resolve_unit_system(action_params.get("output_unit_system", ""))
    if action_name == "eval_zvl":
        translated["weight_type"] = WeightType(action_params.get("weight_type", "wk"))
        translated["time_windows"] = float(action_params.get("time_windows", "1") or 1.0)
    elif action_name == "eval_otovl":
        translated["time_windows"] = float(action_params.get("time_windows", "1") or 1.0)
    elif action_name == "eval_fpvdv":
        translated["nsup"] = int(action_params.get("nsup", "4") or 4)
    return {key: value for key, value in translated.items() if value is not None}


def _resolve_unit_system(value: str) -> UnitSystem | None:
    match value.strip():
        case "":
            return None
        case "si":
            return UnitSystem.si()
        case "engineering":
            return UnitSystem.engineering()
    raise ValueError(f"不支持的单位制：{value}")


def _parse_periods(text: str) -> np.ndarray | None:
    stripped = text.strip()
    if not stripped:
        return None
    return np.asarray([float(item.strip()) for item in stripped.split(",") if item.strip()], dtype=float)


def _parse_freq_range(min_value: str, max_value: str) -> tuple[float, float] | None:
    min_text = min_value.strip()
    max_text = max_value.strip()
    if not min_text and not max_text:
        return None
    if not min_text or not max_text:
        raise ValueError("freq_range 需要同时提供最小值和最大值")
    return (float(min_text), float(max_text))
