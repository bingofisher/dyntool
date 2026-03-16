"""元数据辅助归一化逻辑。"""

from __future__ import annotations

import json
from typing import Any

import pandas as pd


def normalize_extra(value: Any) -> dict[str, Any] | None:
    """将 extra 标准化为 `dict | None`。"""

    if value is None or value == "":
        return None
    if pd.isna(value):
        return None
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError("extra 字段必须是有效 JSON 字符串") from exc
    if not isinstance(value, dict):
        raise TypeError("extra 字段必须是字典或 JSON 字符串")
    return value


def dump_extra(extra: dict[str, Any] | None) -> str:
    """将 extra 序列化为 SQL 友好字符串。"""

    if extra is None:
        return ""
    return json.dumps(extra, ensure_ascii=False)


def denormalize_flat_dict(data: dict[str, Any], sep: str = "@") -> dict[str, Any]:
    """将扁平字典恢复为嵌套字典。"""

    payload: dict[str, Any] = {}
    for raw_key, value in data.items():
        key = str(raw_key)
        if sep not in key:
            payload[key] = value
            continue
        parts = key.split(sep)
        cursor = payload
        for part in parts[:-1]:
            node = cursor.get(part)
            if not isinstance(node, dict):
                node = {}
                cursor[part] = node
            cursor = node
        cursor[parts[-1]] = value
    return payload


__all__ = ["normalize_extra", "dump_extra", "denormalize_flat_dict"]
