"""存储策略共享的单位、序列化与路径上下文。"""

from __future__ import annotations

from dataclasses import dataclass
from copy import deepcopy
from contextlib import closing
import json
import types
import re
from threading import RLock
from pathlib import Path
from typing import TYPE_CHECKING, Any, Union, get_args, get_origin

import numpy as np
import pandas as pd

from .storage_constants import (
    CSV_ENCODING_UTF8_SIG,
    DEFAULT_SQLITE_INDEX_FILENAME,
    DEFAULT_SQLITE_PAYLOAD_H5_FILENAME,
    DEFAULT_SET_H5_FILENAME,
    META_COL_ALIAS,
    META_COL_METADATA_JSON,
    META_COL_NAME,
    META_COL_UID,
    METADATA_TABLE_COLUMNS,
    METADATA_TABLE_FILENAME,
)
from .storage_options import ResolvedStorageDataOptions, resolve_storage_data_options
from .data_storage import DataStorage
from ..storage.types import AttrDataFormat, NameResolver, StorageScheme
from ..domain._provenance import _SampleResultState

if TYPE_CHECKING:
    from ..domain.samples.base import SampleBaseModel
    from ..domain.samples.sets import SampleSetBase


@dataclass(slots=True)
class _SampleWritePlan:
    """统一非空槽位更新、metadata 与 alias；未选择的数据由存储策略保留。"""

    uid: str
    alias: str
    metadata: dict[str, Any]
    data: dict[str, Any]

    @classmethod
    def build(
        cls,
        context: StorageContext,
        sample: SampleBaseModel,
        categories: list[str] | None,
        stored_states: dict[str, dict[str, Any]] | None = None,
    ) -> _SampleWritePlan:
        updates: dict[str, Any] = {}
        precision_states: dict[str, dict[str, Any]] = {}
        for category in context.resolve_storage_categories(categories):
            field = sample.sample_schema.resolve_field(category)
            value = sample.data_vars.get(field)
            if value is None:
                continue
            if not hasattr(value, "to_dict") or not hasattr(type(value), "from_dict"):
                raise TypeError(f"样本字段 '{category}' 不支持 to_dict/from_dict。")
            if context.decimal_round() is not None or context.float_dtype() is not None:
                from copy import deepcopy
                from uuid import uuid5, NAMESPACE_URL
                from ..domain.models._model_payload import _ModelPayloadCodec

                original = value
                value = context.deserialize_container(category, context.serialize_container(value))
                if not _ModelPayloadCodec.equal(original.to_dict(), value.to_dict()):
                    record = deepcopy(original._provenance)
                    options = {
                        "decimal_round": context.decimal_round(),
                        "float_dtype": context.float_dtype(),
                        "units": original.current_units(),
                    }
                    record["revision"] = uuid5(
                        NAMESPACE_URL, record["revision"] + json.dumps(options, sort_keys=True)
                    ).hex
                    record["storage_precision"] = options
                    value.__dict__["_provenance"] = record
                    precision_states[category] = record
            updates[category] = value
        states = _SampleResultState(sample).projected(
            list(updates),
            existing=stored_states is not None or sample.uid in context._uid_names,
            base=context.stored_result_state(sample.uid) if stored_states is None else stored_states,
        )
        states.update(precision_states)
        _SampleResultState(sample).invalidate(states)
        for category, model in tuple(updates.items()):
            from copy import deepcopy

            if model._provenance != states[category]:
                clone = deepcopy(model)
                clone.__dict__["_provenance"] = states[category]
                updates[category] = clone
        metadata = sample.metadata.model_dump()
        metadata["_dyntool_state"] = states
        return cls(sample.uid, sample.alias, metadata, updates)


class _SampleNameReservation:
    """单写者会话内维护名称归属和输入顺序预约。"""

    def __init__(self) -> None:
        self.owners: dict[str, str] | None = None

    def reset(self) -> None:
        self.owners = None

    def reserve(self, strategy: Any, sample: Any, name: str) -> None:
        if self.owners is None:
            self.owners = {value.casefold(): uid for uid, value in strategy.uid_name_index().items()}
        key = name.casefold()
        owner = self.owners.get(key)
        if owner is not None and owner != sample.uid:
            raise ValueError(f"命名冲突：名称 {name!r} 已属于 UID {owner}，不能写入 {sample.uid}")
        context = strategy.ctx
        targets = {
            StorageScheme.SAMPLE_JSON: context.base_dir / f"{name}.json",
            StorageScheme.SAMPLE_H5: context.base_dir / f"{name}.h5",
            StorageScheme.SET_DIR: context.base_dir / name,
        }
        target = targets.get(context.storage_scheme)
        if target is not None:
            if not target.resolve().is_relative_to(context.base_dir.resolve()):
                raise ValueError(f"样本目标路径越界：{target}")
            if target.exists() and owner is None:
                raise ValueError(f"目标文件归属未知，拒绝覆盖：{target}")
        self.owners[key] = sample.uid


class StorageContext:
    """样本存储策略共享的上下文对象。

    Attributes:
        sampleset: 当前绑定的样本集，用于解析样本模式、槽位和元数据类型。
        base_dir: 当前存储根目录。
        storage_scheme: 当前生效的存储方案。
        data_options: 控制精度、载荷格式等行为的原始配置字典。
        name_resolver: 可选的样本命名解析器。
        set_filename: 集合级 HDF5 文件名，仅在 `StorageScheme.SET_H5` 下生效。
        data_storage: 底层数据模型持久化辅助对象。
    """

    def __init__(
        self,
        sampleset: "SampleSetBase",
        *,
        base_dir: Path,
        storage_scheme: StorageScheme,
        data_options: dict[str, Any] | None = None,
        name_resolver: NameResolver | None = None,
        set_filename: str = DEFAULT_SET_H5_FILENAME,
        data_storage: DataStorage | None = None,
    ) -> None:
        """初始化样本存储上下文。

        Args:
            sampleset: 当前绑定的样本集对象。
            base_dir: 存储根目录。
            storage_scheme: 当前生效的存储方案。
            data_options: 控制精度、载荷格式等行为的配置字典。
            name_resolver: 可选的样本命名解析器。
            set_filename: 集合级 HDF5 文件名。
            data_storage: 可复用的数据模型持久化辅助对象；未提供时自动创建。
        """

        self._last_write_plan: _SampleWritePlan | None = None
        self._uid_names: dict[str, str] = {}
        self._result_state_cache: dict[str, dict[str, dict[str, Any]]] = {}
        self.write_lock = RLock()
        self.name_reservations = _SampleNameReservation()
        self.sampleset = sampleset
        self.base_dir = base_dir
        self.storage_scheme = storage_scheme
        self._resolved_data_options: ResolvedStorageDataOptions = resolve_storage_data_options(
            storage_scheme,
            data_options,
        )
        self.data_options = self._resolved_data_options.as_dict()
        self.name_resolver = name_resolver
        self.set_filename = set_filename
        self.data_storage = data_storage or DataStorage()
        self._category_fields_cache = tuple(self.sampleset.sample_schema.slot_names(include_storage_only=True))
        self._resolved_categories_cache: dict[tuple[str, ...] | None, tuple[str, ...]] = {
            None: self._category_fields_cache,
        }
        self._metadata_table_cache: pd.DataFrame | None = None

    def stored_result_state(self, uid: str) -> dict[str, dict[str, Any]]:
        """仅读取已持久化 metadata，部分保存不解码旧数组。"""
        if uid in self._result_state_cache:
            return self._result_state_cache[uid]
        name = self._uid_names.get(uid)
        if name is None:
            return {}
        if self.storage_scheme is StorageScheme.SET_SQLITE_H5:
            import sqlite3

            with closing(
                sqlite3.connect(self.sqlite_index_path().resolve().as_uri() + "?mode=ro", uri=True)
            ) as connection:
                row = connection.execute("SELECT metadata_json FROM sample WHERE uid=?", (uid,)).fetchone()
                metadata = json.loads(row[0]) if row is not None else {}
        elif self.storage_scheme in {StorageScheme.SAMPLE_H5, StorageScheme.SET_H5}:
            import h5py

            target = (
                self.base_dir / f"{name}.h5" if self.storage_scheme is StorageScheme.SAMPLE_H5 else self.set_h5_path()
            )
            with h5py.File(target, "r") as file:
                group = file if self.storage_scheme is StorageScheme.SAMPLE_H5 else file[uid]
                metadata = json.loads(str(group.attrs["metadata_json"]))
        elif self.storage_scheme is StorageScheme.SET_ATTR_TABLE:
            rows = self.load_metadata_table()
            metadata = json.loads(str(rows.loc[rows[META_COL_UID] == uid, META_COL_METADATA_JSON].iloc[0]))
        else:
            target = (
                self.base_dir / f"{name}.json"
                if self.storage_scheme is StorageScheme.SAMPLE_JSON
                else (self.base_dir / name / "metadata.json")
            )
            metadata = json.loads(target.read_text(encoding="utf-8"))["metadata"]
        states = metadata.get("_dyntool_state", {})
        self._result_state_cache[uid] = states
        return states

    def category_fields(self) -> list[str]:
        """返回可存储的标准槽位名。"""

        return list(self._category_fields_cache)

    def resolve_storage_categories(
        self,
        categories: list[str] | None = None,
    ) -> list[str]:
        """将调用方传入的类别名解析为标准存储槽位名。

        Args:
            categories: 用户传入的槽位名列表；为 `None` 时表示全部可存储槽位。

        Returns:
            list[str]: 去重后的标准槽位名列表，顺序与输入保持一致。

        Raises:
            ValueError: 指定槽位未启用存储时抛出。

        Notes:
            该方法负责把别名或用户输入统一映射为样本模式中的真实槽位名。
            重复项会被去重，但保留第一次出现的顺序。
        """

        if categories is None:
            return list(self._resolved_categories_cache[None])

        cache_key = tuple(str(raw_name) for raw_name in categories)
        cached = self._resolved_categories_cache.get(cache_key)
        if cached is not None:
            return list(cached)

        resolved: list[str] = []
        seen: set[str] = set()
        for raw_name in cache_key:
            slot = self.sampleset.sample_schema.slot(raw_name)
            if not slot.include_in_storage:
                raise ValueError(f"槽位 '{slot.name}' 未启用存储，不能参与存储读写。")
            if slot.name in seen:
                continue
            resolved.append(slot.name)
            seen.add(slot.name)
        resolved_tuple = tuple(resolved)
        self._resolved_categories_cache[cache_key] = resolved_tuple
        return list(resolved_tuple)

    def attr_data_format(self) -> AttrDataFormat:
        """返回当前生效的属性数据导出格式。

        Returns:
            AttrDataFormat: 当前生效的属性数据导出格式枚举。

        Raises:
            ValueError: 配置值不属于受支持的属性载荷格式时抛出。

        Notes:
            该值来源于 `data_options["attr_data_format"]` 的解析结果。
            调用方未显式传入时，沿用当前存储方案对应的默认值。
        """

        return self._resolved_data_options.attr_data_format

    def decimal_round(self) -> int | None:
        """返回浮点输出的小数舍入位数。"""

        return self._resolved_data_options.decimal_round

    def float_dtype(self) -> str | None:
        """返回浮点输出的目标 dtype。"""

        return self._resolved_data_options.float_dtype

    def h5_dataset_options(self) -> dict[str, Any]:
        """返回 H5 数据集创建选项。"""

        return self._resolved_data_options.h5_dataset_options.copy()

    def resolve_name(self, sample: SampleBaseModel) -> str:
        """解析样本在当前存储方案下对应的文件名或目录名。

        Args:
            sample: 需要落盘命名的样本对象。

        Returns:
            str: 当前存储方案下最终使用的样本名称。

        Raises:
            ValueError: `name_resolver` 返回空字符串时抛出。

        Notes:
            未配置 `name_resolver` 时默认直接使用 `sample.uid`。
            自定义解析器返回值会在此处统一做字符串化和去首尾空白处理。
        """

        if self.name_resolver is None:
            return sample.uid
        candidate = self.name_resolver(
            sample,
            {
                "uid": sample.uid,
                "alias": sample.alias,
                "storage_scheme": self.storage_scheme.value,
            },
        )
        resolved = str(candidate).strip()
        if (
            not resolved
            or resolved in {".", ".."}
            or resolved.endswith((".", " "))
            or re.search(r'[<>:"/\\|?*\x00-\x1f]', resolved)
            or resolved.split(".")[0].upper()
            in {"CON", "PRN", "AUX", "NUL", *[f"COM{i}" for i in range(1, 10)], *[f"LPT{i}" for i in range(1, 10)]}
        ):
            raise ValueError(f"name_resolver 返回了非法文件名：{resolved!r}")
        return resolved

    def sample_data_dict(self, sample: SampleBaseModel, categories: list[str] | None = None) -> dict[str, Any]:
        """提取样本中需要进入存储层的数据容器映射。

        Args:
            sample: 待保存的样本对象。
            categories: 需要保存的槽位列表；为 `None` 时保存全部可存储槽位。

        Returns:
            dict[str, Any]: 槽位名到数据容器对象的映射。

        Raises:
            TypeError: 槽位对象不支持 `to_dict()` / `from_dict()` 协议时抛出。

        Notes:
            仅返回当前样本上存在且非空的槽位。槽位值必须同时支持 `to_dict()` 和
            类级 `from_dict()`，否则后续无法形成可逆的持久化流程。
        """

        return self.write_plan(sample, categories).data

    def write_plan(
        self,
        sample: SampleBaseModel,
        categories: list[str] | None = None,
        *,
        stored_states: dict[str, dict[str, Any]] | None = None,
    ) -> _SampleWritePlan:
        """创建单样本写入计划，不触发未加载槽位的隐式读取。"""
        plan = _SampleWritePlan.build(self, sample, categories, stored_states)
        self._last_write_plan = plan
        return plan

    def apply_precision_to_array(self, value: np.ndarray) -> np.ndarray:
        """按 `data_options` 对数组执行舍入和 dtype 收敛。"""

        arr = np.asarray(value)
        if np.issubdtype(arr.dtype, np.floating):
            decimals = self.decimal_round()
            if decimals is not None:
                arr = np.round(arr, decimals=decimals)
            dtype_name = self.float_dtype()
            if dtype_name is not None:
                arr = arr.astype(dtype_name)
        return arr

    def apply_precision_payload(self, payload: Any) -> Any:
        """递归处理序列化载荷中的浮点精度与 dtype。

        Args:
            payload: 待处理的载荷，可以是数组、标量、容器或嵌套结构。

        Returns:
            Any: 按 `decimal_round` 和 `float_dtype` 收敛后的新载荷。

        Notes:
            该方法会递归遍历 `list`、`tuple`、`dict`、`numpy.ndarray` 和 NumPy 标量。
            仅数值载荷中的浮点值会被舍入或强制转换 dtype；追溯记录的计算参数保持原精度。
        """

        if isinstance(payload, np.ndarray):
            return self.apply_precision_to_array(payload)
        if isinstance(payload, np.generic):
            return self.apply_precision_payload(payload.item())
        if isinstance(payload, list):
            return [self.apply_precision_payload(x) for x in payload]
        if isinstance(payload, tuple):
            return tuple(self.apply_precision_payload(x) for x in payload)
        if isinstance(payload, dict):
            return {
                k: deepcopy(v) if k in {"_dyntool", "_dyntool_state"} else self.apply_precision_payload(v)
                for k, v in payload.items()
            }
        if isinstance(payload, float):
            out = round(payload, self.decimal_round()) if self.decimal_round() is not None else payload
            if self.float_dtype() is not None:
                out = np.array([out], dtype=self.float_dtype()).item()
            return out
        return payload

    def to_jsonable(self, payload: Any) -> Any:
        """将 NumPy/Pandas 友好的载荷递归转换为 JSON 兼容对象。"""

        if isinstance(payload, np.ndarray):
            return payload.tolist()
        if isinstance(payload, np.generic):
            return payload.item()
        if isinstance(payload, list):
            return [self.to_jsonable(x) for x in payload]
        if isinstance(payload, tuple):
            return [self.to_jsonable(x) for x in payload]
        if isinstance(payload, dict):
            return {k: self.to_jsonable(v) for k, v in payload.items()}
        return payload

    def serialize_container(self, data: Any) -> dict[str, Any]:
        """序列化数据容器并应用输出精度设置。"""

        if not hasattr(data, "to_dict"):
            raise TypeError(f"{type(data).__name__} 不支持 to_dict")
        payload = data.to_dict()
        if not isinstance(payload, dict):
            raise TypeError(f"{type(data).__name__}.to_dict() 必须返回 dict")
        return self.apply_precision_payload(payload)

    def deserialize_container(self, category: str, payload: dict[str, Any]) -> Any:
        """根据槽位类型信息将字典载荷反序列化为数据容器对象。"""

        category_type = self.resolve_field_type(category)
        if not hasattr(category_type, "from_dict"):
            raise TypeError(f"{category_type.__name__} 不支持 from_dict")
        return category_type.from_dict(payload)  # type: ignore[union-attr]

    def metadata_from_dict(self, metadata_dict: dict[str, Any]) -> Any:
        """根据样本模式中的元数据类型重建元数据对象。"""

        metadata_type = self.resolve_field_type("metadata")
        if not hasattr(metadata_type, "from_dict"):
            raise TypeError(f"字段 'metadata' 类型不可调用: {metadata_type}")
        return metadata_type.from_dict(metadata_dict)

    def resolve_field_type(self, field_name: str) -> type:
        """解析字段或槽位在当前样本模式下对应的 Python 类型。

        Args:
            field_name: 样本字段名、槽位名或特殊字段 `metadata`。

        Returns:
            type: 解析得到的目标 Python 类型。

        Raises:
            TypeError: 字段注解无法收敛为单一类型时抛出。

        Notes:
            该方法优先从样本模式槽位中取类型；对普通模型字段则读取 Pydantic 注解。
            如果注解是 `X | None` 或 `Union[X, None]`，会自动剥离 `None` 得到真实类型。
        """

        if field_name == "metadata":
            return self.sampleset.sample_schema.metadata_type
        if self.sampleset.sample_schema.has_slot(field_name):
            return self.sampleset.sample_schema.slot(field_name).model_type
        annotation = self.sampleset.sample_type.model_fields[field_name].annotation
        origin = get_origin(annotation)
        if origin in (Union, types.UnionType):
            args = [arg for arg in get_args(annotation) if arg is not type(None)]
            if len(args) == 1:
                annotation = args[0]
        if not isinstance(annotation, type):
            raise TypeError(f"字段 '{field_name}' 的类型注解无法解析为类: {annotation}")
        return annotation

    def set_h5_path(self) -> Path:
        """返回集合 H5 文件路径。"""

        return self.base_dir / self.set_filename

    def sqlite_index_path(self) -> Path:
        """返回 SQLite 索引文件路径。"""

        return self.base_dir / DEFAULT_SQLITE_INDEX_FILENAME

    def sqlite_payload_h5_path(self) -> Path:
        """返回 SQLite 与 H5 组合策略的 payload 文件路径。"""

        return self.base_dir / DEFAULT_SQLITE_PAYLOAD_H5_FILENAME

    def metadata_table_path(self) -> Path:
        """返回元数据索引表路径。"""

        return self.base_dir / METADATA_TABLE_FILENAME

    def load_metadata_table(self) -> pd.DataFrame:
        """读取元数据索引表；不存在时返回空表。"""

        if self._metadata_table_cache is None:
            path = self.metadata_table_path()
            if path.exists():
                self._metadata_table_cache = pd.read_csv(path, encoding=CSV_ENCODING_UTF8_SIG)
            else:
                self._metadata_table_cache = pd.DataFrame(columns=METADATA_TABLE_COLUMNS)
        return self._metadata_table_cache.copy()

    def save_metadata_table(self, df: pd.DataFrame) -> None:
        """保存元数据索引表。"""

        normalized_df = df.reset_index(drop=True).copy()
        self._metadata_table_cache = normalized_df
        self.metadata_table_path().parent.mkdir(parents=True, exist_ok=True)
        normalized_df.to_csv(self.metadata_table_path(), index=False, encoding=CSV_ENCODING_UTF8_SIG)

    def upsert_metadata_table_row(self, sample: SampleBaseModel, name: str) -> None:
        """更新或新增样本元数据索引行。"""

        self.save_metadata_table(self.metadata_table_update(sample, name))

    def metadata_table_update(
        self, sample: SampleBaseModel, name: str, *, metadata: dict[str, Any] | None = None
    ) -> pd.DataFrame:
        """构造更新后的元数据表，提交前不修改缓存或磁盘。"""
        df = self.load_metadata_table()
        row: dict[str, Any] = {
            META_COL_UID: sample.uid,
            META_COL_NAME: name,
            META_COL_ALIAS: sample.alias,
            META_COL_METADATA_JSON: json.dumps(
                metadata if metadata is not None else self.write_plan(sample).metadata, ensure_ascii=False, default=str
            ),
        }
        row.update(sample.metadata.to_flatten_dict(sep="@"))
        columns = list(dict.fromkeys([*df.columns.tolist(), *row.keys()]))
        updated = df.reindex(columns=columns)
        if META_COL_UID in updated.columns:
            updated = updated.loc[updated[META_COL_UID] != sample.uid].reset_index(drop=True)
        updated.loc[len(updated)] = [row.get(column, pd.NA) for column in columns]
        return updated

    def float_format(self) -> str | None:
        """返回 pandas CSV 导出的浮点格式。"""

        if self.decimal_round() is None:
            return None
        return f"%.{self.decimal_round()}f"

    def prepare_container_for_csv(self, category: str, data: Any) -> Any:
        """根据精度设置准备 CSV 导出的数据容器。"""

        return self.deserialize_container(category, self.serialize_container(data))
