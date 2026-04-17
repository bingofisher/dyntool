"""样本集视图导出相关 internal support。"""

from __future__ import annotations

from typing import Any, Callable, Iterable, Mapping

import numpy as np
import pandas as pd

from ..constants import DataCategory
from ..models import DataModelBase
from .types import SampleLoadMode


def metadata_value(sample: Any, field: str) -> str:
    """读取 metadata 扁平字段。"""

    flattened = sample.metadata.to_flatten_dict(sep="@")
    value = flattened.get(field)
    return "" if value is None else str(value)


def scalar_feature_value(sample: Any, feature: str) -> float:
    """计算样本级标量特征。"""

    normalized = str(feature).strip().lower()
    if normalized == "pga":
        return float(sample.pga())
    if normalized == "pgv":
        return float(sample.pgv())
    if normalized == "pgd":
        return float(sample.pgd())
    if normalized == "absmax":
        return float(sample.compute.feature.absmax())
    if normalized == "rms":
        return float(sample.compute.feature.rms())
    if normalized == "mean":
        return float(sample.compute.feature.mean())
    if normalized == "std":
        return float(sample.compute.feature.std())
    if normalized == "crest_factor":
        return float(sample.compute.feature.crest_factor())
    raise KeyError(f"不支持的标量特征: {feature}")


def supports_scalar_data_var(sample_set: Any, data_var: str | DataCategory) -> bool:
    """判断 data_var 是否具有标量表格导出能力。"""

    spec = sample_set.sample_schema.field_spec(data_var)
    return getattr(spec.model_type, "axis_field", None) is None


def validate_scalar_data_vars(sample_set: Any, data_vars: Iterable[str] | None) -> None:
    """验证 requested data_vars 是否全部是标量结果。"""

    invalid: list[str] = []
    for data_var in data_vars or ():
        if not supports_scalar_data_var(sample_set, data_var):
            field = sample_set.sample_schema.resolve_field(data_var)
            invalid.append(str(field.value))
    if invalid:
        quoted = ", ".join(f"'{name}'" for name in invalid)
        raise ValueError(
            f"data_var {quoted} 不是标量结果，不能用于 scalar_frame()/compare_with()，请改用 "
            "series_frame()、图件导出或自定义比较逻辑。"
        )


def build_scalar_frame(
    sample_set: Any,
    *,
    metadata_fields: Iterable[str] | None = None,
    data_vars: Iterable[str] | None = None,
    features: Iterable[str] | None = None,
    uids: Iterable[str] | None = None,
    criteria: Mapping[str, Any] | None = None,
    filter: Callable[[Any], bool] | None = None,
    sort_by: str | None = None,
    dropna: bool = False,
    strict: bool = True,
    view_options: Any | None = None,
) -> pd.DataFrame:
    """组合 metadata、标量 data_var 与派生特征为表格。"""

    requested_metadata = [str(field) for field in metadata_fields or ()]
    requested_data_vars = [str(name) for name in data_vars or ()]
    requested_features = [str(name) for name in features or ()]
    validate_scalar_data_vars(sample_set, requested_data_vars)

    if sample_set.storage is not None and sample_set.storage_dirty is False and filter is None and sort_by is None:
        selected_uids = list(sample_set.find(uids=uids, criteria=criteria).keys())
        try:
            frame = sample_set.storage.summary_frame(
                uids=selected_uids,
                metadata_fields=requested_metadata,
                data_vars=requested_data_vars,
                features=requested_features,
            )
            if strict:
                data_var_columns = {
                    data_var: [column for column in frame.columns if str(column).startswith(f"{data_var}.")]
                    for data_var in requested_data_vars
                }
                required_columns = [
                    *requested_metadata,
                    *requested_features,
                    *[column for columns in data_var_columns.values() for column in columns],
                ]
                missing_columns = [column for column in requested_features if column not in frame.columns]
                missing_data_vars = [data_var for data_var, columns in data_var_columns.items() if not columns]
                if missing_columns or missing_data_vars:
                    raise RuntimeError("摘要层暂不支持当前标量字段")
                if required_columns:
                    subset = frame[[column for column in required_columns if column in frame.columns]]
                    if subset.isna().any(axis=None):
                        first_missing = next(
                            (column for column in subset.columns if subset[column].isna().any()),
                            None,
                        )
                        if first_missing is not None:
                            raise ValueError(f"摘要层缺少列 '{first_missing}' 的有效值")
            if dropna and not frame.empty:
                reserved_columns = {"uid", "alias", *requested_metadata}
                value_columns = [column for column in frame.columns if column not in reserved_columns]
                if value_columns:
                    frame = frame.dropna(axis=0, how="all", subset=value_columns)
            return frame.reset_index(drop=True)
        except RuntimeError:
            pass

    rows: list[dict[str, Any]] = []
    selected = sample_set.find_many(
        uids=uids,
        criteria=criteria,
        filter=filter,
        sort_by=sort_by,
        view_options=sample_set._with_load_mode(view_options, load_mode=SampleLoadMode.EAGER),
    )

    for sample in selected.values():
        row: dict[str, Any] = {"uid": sample.uid, "alias": sample.alias}
        for field in requested_metadata:
            row[field] = metadata_value(sample, field)
        for data_var in requested_data_vars:
            model = sample.get_data_var(data_var)
            if model is None:
                if strict:
                    raise ValueError(f"样本 '{sample.uid}' 缺少 data_var '{data_var}'")
                row[str(data_var)] = np.nan
                continue
            for key, value in model.to_scalar_record().items():
                row[f"{data_var}.{key}"] = value
        for feature in requested_features:
            try:
                row[feature] = scalar_feature_value(sample, feature)
            except Exception:
                if strict:
                    raise
                row[feature] = np.nan
        rows.append(row)

    frame = pd.DataFrame(rows)
    if dropna and not frame.empty:
        reserved_columns = {"uid", "alias", *requested_metadata}
        value_columns = [column for column in frame.columns if column not in reserved_columns]
        if value_columns:
            frame = frame.dropna(axis=0, how="all", subset=value_columns)
    return frame.reset_index(drop=True)


def build_series_frame(
    sample_set: Any,
    data_var: str | DataCategory,
    *,
    metadata_fields: Iterable[str] | None = None,
    uids: Iterable[str] | None = None,
    criteria: Mapping[str, Any] | None = None,
    filter: Callable[[Any], bool] | None = None,
    sort_by: str | None = None,
    strict: bool = True,
    view_options: Any | None = None,
) -> pd.DataFrame:
    """按公共索引外连接同一 data_var 的多样本序列表。"""

    from ..compute_api import ensure_multiindex_metadata, normalize_series_frame

    field = sample_set.sample_schema.resolve_field(data_var)
    selected = sample_set.find_many(
        uids=uids,
        criteria=criteria,
        filter=filter,
        sort_by=sort_by,
        view_options=sample_set._with_load_mode(view_options, load_mode=SampleLoadMode.EAGER),
    )
    exported: list[tuple[Any, pd.DataFrame]] = []
    model_type: type[DataModelBase] | None = None
    for sample in selected.values():
        model = sample.get_data_var(field)
        if model is None:
            if strict:
                raise ValueError(f"样本 '{sample.uid}' 缺少 data_var '{field.value}'")
            continue
        if model_type is None:
            model_type = type(model)
        elif type(model) is not model_type:
            raise TypeError("series_frame() 要求所有样本的 data_var 类型一致")
        exported.append((sample, normalize_series_frame(model)))

    if not exported:
        return pd.DataFrame()

    template_columns = list(exported[0][1].columns)
    union_index = exported[0][1].index
    index_name = exported[0][1].index.name
    for _, frame in exported[1:]:
        if frame.index.name != index_name:
            raise TypeError("series_frame() 要求所有序列表具有相同的索引名称")
        union_index = union_index.union(frame.index)

    output = pd.DataFrame(index=union_index)
    output.index.name = index_name
    requested_metadata = [str(field_name) for field_name in metadata_fields or ()]
    for sample in selected.values():
        model = sample.get_data_var(field)
        if model is None:
            sample_frame = pd.DataFrame(index=union_index, columns=template_columns, dtype=float)
        else:
            sample_frame = normalize_series_frame(model).reindex(union_index)
        prefix = ensure_multiindex_metadata(sample, metadata_fields=requested_metadata)
        sample_frame = sample_frame.rename(columns={column: (*prefix, str(column)) for column in sample_frame.columns})
        output = output.join(sample_frame, how="outer")

    if output.columns.empty:
        output.columns = pd.MultiIndex.from_arrays([[]])
    else:
        output.columns = pd.MultiIndex.from_tuples(list(output.columns))
    return output


def build_peaks_frame(
    sample_set: Any,
    *,
    source: str = "accel",
    metadata_fields: Iterable[str] | None = None,
    uids: Iterable[str] | None = None,
    criteria: Mapping[str, Any] | None = None,
    filter: Callable[[Any], bool] | None = None,
    sort_by: str | None = None,
    strict: bool = True,
    view_options: Any | None = None,
    **kwargs: Any,
) -> pd.DataFrame:
    """将多峰检测结果按峰序号展开为表。"""

    from ..compute_api import ensure_multiindex_metadata

    selected = sample_set.find_many(
        uids=uids,
        criteria=criteria,
        filter=filter,
        sort_by=sort_by,
        view_options=sample_set._with_load_mode(view_options, load_mode=SampleLoadMode.EAGER),
    )
    requested_metadata = [str(field_name) for field_name in metadata_fields or ()]
    payloads: list[tuple[Any, dict[str, Any]]] = []
    max_peaks = 0
    for sample in selected.values():
        try:
            payload = sample.compute.feature.peaks(source=source, **kwargs)
        except Exception:
            if strict:
                raise
            payload = {"peak_indices": np.asarray([], dtype=float), "peak_values": np.asarray([], dtype=float)}
        payloads.append((sample, payload))
        max_peaks = max(max_peaks, int(len(np.asarray(payload.get("peak_indices", [])))))

    if max_peaks == 0:
        raise ValueError("没有可导出的峰值结果")

    output = pd.DataFrame(index=pd.Index(range(max_peaks), name="peak_rank"))
    for sample, payload in payloads:
        peak_indices = np.asarray(payload.get("peak_indices", []), dtype=float)
        peak_values = np.asarray(payload.get("peak_values", []), dtype=float)
        sample_frame = pd.DataFrame(
            {
                "peak_index": pd.Series(peak_indices, dtype=float),
                "peak_value": pd.Series(peak_values, dtype=float),
            }
        ).reindex(output.index)
        prefix = ensure_multiindex_metadata(sample, metadata_fields=requested_metadata)
        sample_frame = sample_frame.rename(columns={column: (*prefix, str(column)) for column in sample_frame.columns})
        output = output.join(sample_frame, how="outer")

    output.columns = pd.MultiIndex.from_tuples(list(output.columns))
    return output


__all__ = [
    "build_peaks_frame",
    "build_scalar_frame",
    "build_series_frame",
    "metadata_value",
    "scalar_feature_value",
    "supports_scalar_data_var",
    "validate_scalar_data_vars",
]
