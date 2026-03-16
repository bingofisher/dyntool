"""基础设施层序列化辅助。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from ..domain.serialization import StructuredPayload, normalize_payload


def to_jsonable(payload: Any) -> Any:
    """将对象转换为 JSON 可序列化结构。"""

    if isinstance(payload, StructuredPayload):
        return to_jsonable(payload.to_dict())
    if isinstance(payload, np.ndarray):
        return payload.tolist()
    if isinstance(payload, np.generic):
        return payload.item()
    if isinstance(payload, dict):
        return {str(k): to_jsonable(v) for k, v in payload.items()}
    if isinstance(payload, (list, tuple)):
        return [to_jsonable(v) for v in payload]
    return payload


def payload_to_json(payload: StructuredPayload | Mapping[str, Any]) -> str:
    """将载荷编码为 JSON 字符串。"""

    normalized = normalize_payload(payload)
    return json.dumps(to_jsonable(normalized), ensure_ascii=False, indent=2)


def payload_from_json(text: str) -> StructuredPayload:
    """从 JSON 字符串恢复载荷。"""

    data = json.loads(text)
    if not isinstance(data, Mapping):
        raise TypeError("StructuredPayload JSON 顶层必须是对象")
    return normalize_payload(data)


def dump_payload(path: str | Path, payload: StructuredPayload | Mapping[str, Any]) -> Path:
    """将载荷写入 JSON 文件。"""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(payload_to_json(payload), encoding="utf-8")
    return target


def load_payload(path: str | Path) -> StructuredPayload:
    """从 JSON 文件读取载荷。"""

    return payload_from_json(Path(path).read_text(encoding="utf-8"))


__all__ = [
    "to_jsonable",
    "payload_to_json",
    "payload_from_json",
    "dump_payload",
    "load_payload",
]
