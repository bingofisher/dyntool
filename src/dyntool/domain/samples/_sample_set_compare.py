"""样本集比较相关 internal support。"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from ._sample_set_views import validate_scalar_data_vars
from .types import SampleSetComparisonReport


def sample_field_present(sample: Any, field: Any) -> bool:
    """判断样本在指定槽位上是否存在数据。"""

    if sample.get_data_var(field) is not None:
        return True
    storage_set = getattr(sample, "_storage_set", None)
    if storage_set is None or getattr(storage_set, "storage", None) is None:
        return False
    return bool(getattr(sample, "_storage_presence", {}).get(field, False))


def compare_metadata_rows(
    sample_set: Any,
    other: Any,
    *,
    common_uids: list[str],
    metadata_fields: list[str] | None,
) -> pd.DataFrame:
    """构建 metadata 差异表。"""

    rows: list[dict[str, Any]] = []
    for uid in common_uids:
        left_flat = sample_set[uid].metadata.to_flatten_dict(sep="@")
        right_flat = other[uid].metadata.to_flatten_dict(sep="@")
        fields = metadata_fields or sorted(set(left_flat) | set(right_flat))
        for field in fields:
            left_value = left_flat.get(field)
            right_value = right_flat.get(field)
            if left_value != right_value:
                rows.append({"uid": uid, "field": field, "left": left_value, "right": right_value})
    return pd.DataFrame(rows)


def compare_presence_rows(
    sample_set: Any,
    other: Any,
    *,
    common_uids: list[str],
    requested_data_vars: list[str] | None,
) -> pd.DataFrame:
    """构建槽位存在性差异表。"""

    rows: list[dict[str, Any]] = []
    requested_fields = (
        [sample_set.sample_schema.resolve_field(name) for name in requested_data_vars]
        if requested_data_vars
        else list(sample_set.storable_fields())
    )
    for uid in common_uids:
        left_sample = sample_set[uid]
        right_sample = other[uid]
        for field in requested_fields:
            left_present = sample_field_present(left_sample, field)
            right_present = sample_field_present(right_sample, field)
            if left_present != right_present:
                rows.append(
                    {
                        "uid": uid,
                        "field": field.value,
                        "left_present": left_present,
                        "right_present": right_present,
                    }
                )
    return pd.DataFrame(rows)


def compare_scalar_rows(
    sample_set: Any,
    other: Any,
    *,
    common_uids: list[str],
    metadata_fields: list[str] | None,
    data_vars: list[str] | None,
    features: list[str] | None,
    rtol: float,
    atol: float,
) -> pd.DataFrame:
    """构建标量摘要差异表。"""

    if data_vars:
        validate_scalar_data_vars(sample_set, data_vars)
        validate_scalar_data_vars(other, data_vars)
    if not common_uids or (not data_vars and not features):
        return pd.DataFrame()

    left_frame = sample_set.scalar_frame(
        metadata_fields=metadata_fields,
        data_vars=data_vars,
        features=features,
        uids=common_uids,
        strict=False,
    ).set_index("uid", drop=False)
    right_frame = other.scalar_frame(
        metadata_fields=metadata_fields,
        data_vars=data_vars,
        features=features,
        uids=common_uids,
        strict=False,
    ).set_index("uid", drop=False)

    reserved_columns = {"uid", "alias", *(metadata_fields or [])}
    scalar_columns = sorted((set(left_frame.columns) & set(right_frame.columns)) - reserved_columns)
    rows: list[dict[str, Any]] = []
    for uid in common_uids:
        if uid not in left_frame.index or uid not in right_frame.index:
            continue
        for column in scalar_columns:
            left_value = left_frame.at[uid, column]
            right_value = right_frame.at[uid, column]
            if pd.isna(left_value) and pd.isna(right_value):
                continue
            if pd.isna(left_value) or pd.isna(right_value):
                continue
            if isinstance(left_value, (int, float, np.integer, np.floating)) and isinstance(
                right_value, (int, float, np.integer, np.floating)
            ):
                if np.isclose(float(left_value), float(right_value), rtol=rtol, atol=atol):
                    continue
            elif left_value == right_value:
                continue
            rows.append(
                {
                    "uid": uid,
                    "field": str(column),
                    "left": left_value,
                    "right": right_value,
                    "rtol": rtol,
                    "atol": atol,
                }
            )
    return pd.DataFrame(rows)


def compare_sample_sets(
    sample_set: Any,
    other: Any,
    *,
    metadata_fields: list[str] | None,
    data_vars: list[str] | None,
    features: list[str] | None,
    rtol: float,
    atol: float,
    strict_types: bool,
) -> SampleSetComparisonReport:
    """比较两个样本集的结构与摘要层结果。"""

    same_type = type(sample_set) is type(other)
    same_sample_type = sample_set.sample_type is other.sample_type
    if strict_types and not same_sample_type:
        raise TypeError("compare_with() 要求两个样本集的 sample_type 一致")

    if data_vars:
        validate_scalar_data_vars(sample_set, data_vars)
        validate_scalar_data_vars(other, data_vars)

    left_only_uids = tuple(uid for uid in sample_set.keys() if uid not in other)
    right_only_uids = tuple(uid for uid in other.keys() if uid not in sample_set)
    common_uids = tuple(uid for uid in sample_set.keys() if uid in other)

    return SampleSetComparisonReport(
        same_type=same_type,
        same_sample_type=same_sample_type,
        same_size=len(sample_set) == len(other),
        left_only_uids=left_only_uids,
        right_only_uids=right_only_uids,
        common_uids=common_uids,
        metadata_diff=compare_metadata_rows(
            sample_set,
            other,
            common_uids=list(common_uids),
            metadata_fields=metadata_fields,
        ),
        presence_diff=compare_presence_rows(
            sample_set,
            other,
            common_uids=list(common_uids),
            requested_data_vars=data_vars,
        ),
        scalar_diff=compare_scalar_rows(
            sample_set,
            other,
            common_uids=list(common_uids),
            metadata_fields=metadata_fields,
            data_vars=data_vars,
            features=features,
            rtol=rtol,
            atol=atol,
        ),
    )


__all__ = [
    "compare_metadata_rows",
    "compare_presence_rows",
    "compare_sample_sets",
    "compare_scalar_rows",
    "sample_field_present",
]
