"""Private / implementation detail：结构化载荷的权威字段和重复数据校验。"""

from __future__ import annotations

from inspect import signature
from typing import Any, Mapping

import numpy as np

from ..serialization import StructuredPayload, normalize_payload


class _ModelPayloadCodec:
    """从正式结构恢复模型，兼容只有原始字典的旧载荷。"""

    @classmethod
    def equal(cls, left: Any, right: Any, *, compare_provenance: bool = False) -> bool:
        """比较载荷；交换一致性包含追溯，物理精度判断仅比较数值与单位。"""
        if isinstance(left, Mapping) or isinstance(right, Mapping):
            if not isinstance(left, Mapping) or not isinstance(right, Mapping):
                return False
            keys = (set(left) | set(right)) - {"_dyntool"}
            if compare_provenance and "_dyntool" in left and "_dyntool" in right:
                keys.add("_dyntool")
            return all(
                key in left and key in right and cls.equal(left[key], right[key], compare_provenance=compare_provenance)
                for key in keys
            )
        if left is None or right is None:
            return left is right
        a, b = np.asarray(left), np.asarray(right)
        if a.dtype.kind in "biufc" and b.dtype.kind in "biufc":
            return bool(np.array_equal(a, b, equal_nan=True))
        return bool(np.array_equal(a, b))

    @staticmethod
    def export(model: Any) -> StructuredPayload:
        raw = model.to_dict()
        axis = model.axis_field
        coords = {axis: raw[axis]} if axis is not None and axis in raw else {}
        fields = {key: value for key, value in raw.items() if key not in {"_units", "_dyntool", *coords}}
        return StructuredPayload(
            entity_type=type(model).__name__,
            category=model._normalize_category(model.category),
            coords=coords,
            data_vars=fields,
            units=model.current_units(),
            attrs={"model_type": type(model).__name__, "data_authority": "structured", "_dyntool": raw.get("_dyntool")},
            meta={"raw_dict": raw},
        )

    @classmethod
    def restore(cls, model_type: type, payload: Mapping[str, Any] | StructuredPayload) -> Any:
        normalized = normalize_payload(payload)
        raw = normalized.meta.get("raw_dict")
        for key in set(normalized.coords) & set(normalized.data_vars):
            if not cls.equal(normalized.coords[key], normalized.data_vars[key], compare_provenance=True):
                raise ValueError(f"结构化坐标与值字段不一致：{key}")
        fields = {
            key: value.item()
            if isinstance(value, np.ndarray) and value.ndim == 0 and isinstance(value.item(), Mapping)
            else value
            for key, value in {**normalized.coords, **normalized.data_vars}.items()
        }
        if normalized.units:
            fields["_units"] = normalized.units
        if normalized.attrs.get("_dyntool") is not None:
            fields["_dyntool"] = normalized.attrs["_dyntool"]
        if fields and isinstance(raw, Mapping):
            # 比较重复的字段及单位，缺失的辅助字段仍可兼容旧形态。
            for key in set(fields) & set(raw):
                if not cls.equal(fields[key], raw[key], compare_provenance=True):
                    raise ValueError(f"结构化载荷与重复原始字段不一致：{key}")
        if not normalized.coords and not normalized.data_vars:
            if not isinstance(raw, Mapping):
                raise ValueError("模型载荷缺少结构化数据和受支持的原始数据")
            fields = dict(raw)
        options = {"units": normalized.units or None} if "units" in signature(model_type.from_dict).parameters else {}
        return model_type.from_dict(fields, **options)
