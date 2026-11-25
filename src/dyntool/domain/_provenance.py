"""Private / implementation detail：模型版本、计算依据与样本结果状态。"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, is_dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from importlib.metadata import version
from typing import Any
from uuid import uuid4

import numpy as np

LIBRARY_VERSION = version("dyntool")


class _ResultProvenance:
    """记录可解释的计算依据；缺少历史依据时保持来源未知。"""

    @staticmethod
    def unknown() -> dict[str, Any]:
        return {"revision": uuid4().hex, "status": "unknown"}

    @classmethod
    def validate(cls, record: dict[str, Any]) -> dict[str, Any]:
        """校验可恢复的计算依据并返回快照，不凭状态标签伪造有效记录。"""
        if not isinstance(record, dict) or record.get("status") not in {"unknown", "fresh", "stale"}:
            raise ValueError("结果追溯状态无效")
        if not isinstance(record.get("revision"), str) or not record["revision"]:
            raise ValueError("结果追溯缺少载荷版本")
        if record["status"] in {"fresh", "stale"}:
            for key in ("operation", "algorithm", "library_version", "computed_at"):
                if not isinstance(record.get(key), str) or not record[key]:
                    raise ValueError(f"结果追溯缺少有效计算依据：{key}")
            for key in ("parameters", "inputs", "input_units", "output_units"):
                if not isinstance(record.get(key), dict):
                    raise ValueError(f"结果追溯缺少有效计算依据：{key}")
            for key in ("inputs", "input_units", "output_units"):
                if any(
                    not isinstance(name, str) or not isinstance(value, str) or not value
                    for name, value in record[key].items()
                ):
                    raise ValueError(f"结果追溯计算依据无效：{key}")
            try:
                computed_at = datetime.fromisoformat(record["computed_at"])
            except ValueError as error:
                raise ValueError("结果追溯计算时间格式无效") from error
            if computed_at.utcoffset() != timedelta(0):
                raise ValueError("结果追溯计算时间必须包含 UTC 时区")
        if "history" in record:
            history = record["history"]
            if not isinstance(history, list) or any(
                not isinstance(entry, dict)
                or not isinstance(entry.get("operation"), str)
                or not entry["operation"]
                or not isinstance(entry.get("parameters"), dict)
                or not isinstance(entry.get("input_revision"), str)
                or not entry["input_revision"]
                for entry in history
            ):
                raise ValueError("结果追溯历史记录缺少有效的操作、参数或输入版本")
        return deepcopy(record)

    @classmethod
    def parameter(cls, value: Any) -> Any:
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, np.ndarray):
            return value.tolist()
        if isinstance(value, np.generic):
            return value.item()
        if is_dataclass(value) and not isinstance(value, type):
            return cls.parameter(asdict(value))
        if isinstance(value, dict):
            return {str(key): cls.parameter(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [cls.parameter(item) for item in value]
        if hasattr(value, "_provenance") and hasattr(value, "current_units"):
            return {"revision": value._provenance["revision"], "units": value.current_units()}
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        raise TypeError(f"计算参数不能记录为可追溯数据：{type(value).__name__}")

    @classmethod
    def computed(cls, source: Any, result: Any, action: str, parameters: dict[str, Any]) -> None:
        result.__dict__["_provenance"] = {
            "revision": uuid4().hex,
            "status": "fresh",
            "operation": action,
            "parameters": cls.parameter(parameters),
            "inputs": {"source": source._provenance["revision"]},
            "input_units": source.current_units(),
            "output_units": result.current_units(),
            "algorithm": f"dyntool.{action}",
            "library_version": LIBRARY_VERSION,
            "computed_at": datetime.now(timezone.utc).isoformat(),
            "history": [
                *deepcopy(source._provenance.get("history", [])),
                {
                    "operation": action,
                    "parameters": cls.parameter(parameters),
                    "input_revision": source._provenance["revision"],
                },
            ],
        }


class _SampleResultState:
    """管理槽位依据、依赖失效与部分提交后的权威状态。"""

    def __init__(self, sample: Any) -> None:
        self.sample = sample

    def restore(self, field: Any, model: Any) -> None:
        key = str(field)
        record = self.sample._slot_state.get(key)
        if record is None:
            record = deepcopy(model._provenance)
            self.sample._slot_state[key] = record
        model.__dict__["_provenance"] = _ResultProvenance.validate(record)

    def updated(self, field: Any, model: Any) -> None:
        key = str(field)
        record = deepcopy(model._provenance) if model is not None else _ResultProvenance.unknown()
        inputs = record.get("inputs", {})
        source_revision = inputs.pop("source", None)
        revisions = [source_revision, *[entry["input_revision"] for entry in reversed(record.get("history", []))]]
        by_revision: dict[str, list[str]] = {}
        for slot, state in self.sample._slot_state.items():
            by_revision.setdefault(state["revision"], []).append(slot)
        for revision in revisions:
            for slot in by_revision.get(revision, []):
                if slot == key:
                    record.setdefault("historical_inputs", {})[slot] = revision
                else:
                    inputs[slot] = revision
        if inputs:
            record["inputs"] = inputs
        previous = self.sample._slot_state.get(key, {}).get("revision")
        self.sample._slot_state[key] = record
        if model is not None:
            model.__dict__["_provenance"] = deepcopy(record)
        if previous != record["revision"]:
            self.invalidate(self.sample._slot_state)

    def invalidate(self, states: dict[str, dict[str, Any]]) -> None:
        # 每轮只允许 fresh 变为 stale；无变化时结束，不依赖槽位插入顺序。
        changed = True
        while changed:
            changed = False
            for key, record in states.items():
                if record.get("status") == "fresh" and any(
                    states.get(source, {}).get("revision") != revision
                    or states.get(source, {}).get("status") == "stale"
                    for source, revision in record.get("inputs", {}).items()
                ):
                    record["status"] = "stale"
                    changed = True
                    model = self.sample._data_map.get(self.sample._resolve_field(key))
                    if model is not None and states is self.sample._slot_state:
                        model.__dict__["_provenance"] = deepcopy(record)

    def projected(
        self, categories: list[str], *, existing: bool, base: dict[str, dict[str, Any]] | None = None
    ) -> dict[str, dict[str, Any]]:
        states = deepcopy(self.sample._committed_slot_state if base is None else base) if existing else {}
        for key in categories:
            if key in self.sample._slot_state:
                states[key] = deepcopy(self.sample._slot_state[key])
        self.invalidate(states)
        return states
