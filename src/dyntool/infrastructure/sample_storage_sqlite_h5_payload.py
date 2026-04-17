"""`SET_SQLITE_H5` 的 payload 读写 helper。"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Mapping

import h5py
import numpy as np

from .sample_storage_sqlite_h5_types import _SqlitePresenceRow
from .storage_constants import H5_ATTR_UNIT

if TYPE_CHECKING:
    from ..domain.samples.base import SampleBaseModel
    from .sample_storage_sqlite_h5 import _SetSqliteH5Strategy


def _collect_payload_path_refs(
    *,
    items: list[tuple[str, str]],
    selected_categories: list[str],
    presence_by_uid: Mapping[str, Mapping[str, _SqlitePresenceRow]],
) -> dict[str, list[tuple[str, str]]]:
    """按 H5 路径聚合待读取的槽位引用。"""

    path_groups: dict[str, list[tuple[str, str]]] = {}
    for uid, _ in items:
        presence_rows = presence_by_uid.get(uid, {})
        for category in selected_categories:
            row_info = presence_rows.get(category)
            if row_info is None or not row_info.exists_flag:
                continue
            path_groups.setdefault(row_info.h5_path, []).append((uid, category))
    return path_groups


def _load_many_sample_fields(
    strategy: _SetSqliteH5Strategy,
    *,
    items: list[tuple[str, str]],
    categories: list[str],
    h5_file: h5py.File | None = None,
) -> dict[str, dict[str, object]]:
    """批量读取多个样本的指定槽位。"""

    loaded: dict[str, dict[str, object]] = {uid: {} for uid, _ in items}
    if not categories or not items:
        return loaded

    selected = strategy.resolve_load_categories(categories)
    path_groups = _collect_payload_path_refs(
        items=items,
        selected_categories=selected,
        presence_by_uid={uid: strategy._presence_rows(uid) for uid, _ in items},
    )
    if not path_groups:
        return loaded

    if h5_file is None:
        with h5py.File(strategy.ctx.sqlite_payload_h5_path(), "r") as managed_h5_file:
            return _load_many_sample_fields(
                strategy,
                items=items,
                categories=selected,
                h5_file=managed_h5_file,
            )

    for h5_path, refs in path_groups.items():
        payload = _read_payload_path(strategy, h5_file, h5_path)
        for uid, category in refs:
            loaded[uid][category] = strategy.ctx.deserialize_container(category, payload)
    return loaded


def _load_sample_from_resources(
    strategy: _SetSqliteH5Strategy,
    uid: str,
    *,
    categories: list[str] | None,
    h5_file: h5py.File | None = None,
) -> SampleBaseModel:
    """从 sqlite+h5 资源重建单个样本。"""

    row = strategy._sample_row(uid)
    if row is None:
        raise FileNotFoundError(f"未找到 UID 对应样本: {uid}")

    sample = strategy.ctx.sampleset.sample_type(
        metadata=strategy.ctx.metadata_from_dict(json.loads(row.metadata_json)),
    )
    sample._restore_alias_internal(row.alias)
    sample._storage_payload_id = row.payload_id

    loaded_fields = _load_sample_fields_from_resources(
        strategy,
        uid,
        categories=categories,
        h5_file=h5_file,
    )
    if loaded_fields:
        sample.update(**loaded_fields)
    return sample


def _load_sample_fields_from_resources(
    strategy: _SetSqliteH5Strategy,
    uid: str,
    *,
    categories: list[str] | None,
    h5_file: h5py.File | None = None,
) -> dict[str, object]:
    """读取单个样本的指定槽位。"""

    loaded: dict[str, object] = {}
    selected = strategy.resolve_load_categories(categories)
    if not selected:
        return loaded
    if h5_file is None:
        with h5py.File(strategy.ctx.sqlite_payload_h5_path(), "r") as managed_h5_file:
            return _load_sample_fields_from_resources(
                strategy,
                uid,
                categories=selected,
                h5_file=managed_h5_file,
            )

    for category in selected:
        row_info = strategy._presence_rows(uid).get(category)
        if row_info is None or not row_info.exists_flag:
            continue
        payload = _read_payload_path(strategy, h5_file, row_info.h5_path)
        loaded[category] = strategy.ctx.deserialize_container(category, payload)
    return loaded


def _read_payload_path(
    strategy: _SetSqliteH5Strategy,
    h5_file: h5py.File,
    h5_path: str,
) -> dict[str, Any]:
    """读取指定 H5 路径的 payload。"""

    if h5_path not in h5_file:
        raise FileNotFoundError(f"H5 payload 缺少槽位路径: {h5_path}")
    category_group = h5_file[h5_path]
    if not isinstance(category_group, h5py.Group):
        raise TypeError(f"H5 payload 节点不是 Group: {h5_path}")
    return _read_group_payload(category_group)


def _write_payload(
    strategy: _SetSqliteH5Strategy,
    payload_id: str,
    sample: SampleBaseModel,
    data_dict: dict[str, Any],
    timestamp: str,
    *,
    h5_file: h5py.File | None = None,
) -> None:
    """写入单个样本的 H5 payload。"""

    if h5_file is None:
        with h5py.File(strategy.ctx.sqlite_payload_h5_path(), "a") as managed_h5_file:
            _write_payload(
                strategy,
                payload_id,
                sample,
                data_dict,
                timestamp,
                h5_file=managed_h5_file,
            )
        return

    samples_group = h5_file.require_group("samples")
    if payload_id in samples_group:
        del samples_group[payload_id]
    sample_group = samples_group.create_group(payload_id)
    sample_group.attrs["payload_id"] = payload_id
    sample_group.attrs["uid_snapshot"] = sample.uid
    sample_group.attrs["alias_snapshot"] = sample.alias
    sample_group.attrs["updated_at"] = timestamp
    slots_group = sample_group.create_group("slots")
    for category, data in data_dict.items():
        _write_group(strategy, slots_group, category, data)


def _write_group(
    strategy: _SetSqliteH5Strategy,
    group: h5py.Group,
    category: str,
    data: Any,
) -> None:
    """写入单个槽位 group。"""

    payload = strategy.ctx.serialize_container(data)
    category_group = group.create_group(category)
    _write_payload_group(strategy, category_group, payload)


def _write_payload_group(
    strategy: _SetSqliteH5Strategy,
    group: h5py.Group,
    payload: dict[str, Any],
) -> None:
    """递归写入 payload group。"""

    units = payload.get("_units", {})
    dataset_options = strategy.ctx.h5_dataset_options()
    for key, value in payload.items():
        if key == "_units" or value is None:
            continue
        if isinstance(value, dict):
            _write_payload_group(strategy, group.create_group(key), value)
            continue
        array = np.asarray(value)
        if array.dtype == object:
            raise TypeError(f"H5 不支持 object dtype 数据集: {key}")
        effective_dataset_options = {} if array.shape == () else dataset_options
        dataset = group.create_dataset(key, data=array, **effective_dataset_options)
        unit = units.get(key, "")
        if unit:
            dataset.attrs[H5_ATTR_UNIT] = unit


def _read_group_payload(group: h5py.Group) -> dict[str, Any]:
    """递归读取 payload group。"""

    payload: dict[str, Any] = {}
    units: dict[str, Any] = {}
    for key in group.keys():
        node = group[key]
        if isinstance(node, h5py.Group):
            payload[key] = _read_group_payload(node)
            continue
        if not isinstance(node, h5py.Dataset):
            continue
        value = node[()]
        if isinstance(value, bytes):
            value = value.decode("utf-8")
        payload[key] = value
        if H5_ATTR_UNIT in node.attrs:
            units[key] = node.attrs[H5_ATTR_UNIT]
    if units:
        payload["_units"] = units
    return payload


__all__ = [
    "_collect_payload_path_refs",
    "_load_many_sample_fields",
    "_load_sample_fields_from_resources",
    "_load_sample_from_resources",
    "_read_group_payload",
    "_read_payload_path",
    "_write_group",
    "_write_payload",
    "_write_payload_group",
]
