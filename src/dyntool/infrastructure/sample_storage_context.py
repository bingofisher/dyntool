"""样本存储策略共享的上下文辅助工具。"""

from __future__ import annotations

import json
import types
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

if TYPE_CHECKING:
    from ..domain.samples.base import SampleBaseModel
    from ..domain.samples.sets import SampleSetBase


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

    def category_fields(self) -> list[str]:
        """返回样本模式中允许进入存储流程的槽位名称列表。"""

        return list(self.sampleset.sample_schema.slot_names(include_storage_only=True))

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
            return self.category_fields()

        resolved: list[str] = []
        seen: set[str] = set()
        for raw_name in categories:
            slot = self.sampleset.sample_schema.slot(str(raw_name))
            if not slot.include_in_storage:
                raise ValueError(f"槽位 '{slot.name}' 未启用存储，不能参与存储读写。")
            if slot.name in seen:
                continue
            resolved.append(slot.name)
            seen.add(slot.name)
        return resolved

    def attr_data_format(self) -> AttrDataFormat:
        """解析属性数据载荷格式配置。

        Returns:
            AttrDataFormat: 当前生效的属性数据导出格式枚举。

        Raises:
            ValueError: 配置值不属于 `csv` 或 `npy` 时抛出。

        Notes:
            该配置读取自 `data_options["attr_data_format"]`；未提供时默认使用 `csv`。
            这里返回真实枚举对象，后续策略实现据此选择文件扩展名和序列化路径。
        """

        return self._resolved_data_options.attr_data_format

    def decimal_round(self) -> int | None:
        """返回浮点数导出时的小数位截断精度。"""

        return self._resolved_data_options.decimal_round

    def float_dtype(self) -> str | None:
        """返回浮点数组导出时的目标 dtype 名称。"""

        return self._resolved_data_options.float_dtype

    def h5_dataset_options(self) -> dict[str, Any]:
        """返回当前样本存储 H5 dataset 写入选项。"""

        return self._resolved_data_options.h5_dataset_options.copy()

    def resolve_name(self, sample: SampleBaseModel) -> str:
        """解析样本在当前存储方案下对应的文件名或目录名。

        Args:
            sample: 需要落盘的样本对象。

        Returns:
            str: 最终使用的文件名或目录名。

        Raises:
            ValueError: `name_resolver` 返回空字符串时抛出。

        Notes:
            当未提供 `name_resolver` 时默认使用 `sample.uid`。
            自定义解析器的上下文字典固定包含 `uid`、`alias`、`storage_scheme` 三个键。
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
        if not resolved:
            raise ValueError("name_resolver returned an empty file name")
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

        selected = self.resolve_storage_categories(categories)
        out: dict[str, Any] = {}
        for category in selected:
            field = sample.sample_schema.resolve_field(category)
            data = sample.data_vars.get(field)
            if data is None:
                continue
            if not hasattr(data, "to_dict") or not hasattr(data.__class__, "from_dict"):
                raise TypeError(f"样本字段 '{category}' 不支持 to_dict/from_dict。")
            out[category] = data
        return out

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
            仅浮点值会被舍入或强制转换 dtype，其它类型保持原样。
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
            return {k: self.apply_precision_payload(v) for k, v in payload.items()}
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
        """将数据容器对象序列化为可存储的字典载荷。"""

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
        """返回样本集级 H5 文件路径。"""

        return self.base_dir / self.set_filename

    def sqlite_index_path(self) -> Path:
        """杩斿洖 SQLite 绱㈠紩鏂囦欢璺緞銆?"""

        return self.base_dir / DEFAULT_SQLITE_INDEX_FILENAME

    def sqlite_payload_h5_path(self) -> Path:
        """杩斿洖 SQLite + H5 鏍锋湰闆?payload H5 璺緞銆?"""

        return self.base_dir / DEFAULT_SQLITE_PAYLOAD_H5_FILENAME

    def metadata_table_path(self) -> Path:
        """返回元数据索引表路径。"""

        return self.base_dir / METADATA_TABLE_FILENAME

    def load_metadata_table(self) -> pd.DataFrame:
        """读取元数据索引表；不存在时返回空表。"""

        path = self.metadata_table_path()
        if not path.exists():
            return pd.DataFrame(columns=METADATA_TABLE_COLUMNS)
        return pd.read_csv(path, encoding=CSV_ENCODING_UTF8_SIG)

    def save_metadata_table(self, df: pd.DataFrame) -> None:
        """保存元数据索引表。"""

        self.metadata_table_path().parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(self.metadata_table_path(), index=False, encoding=CSV_ENCODING_UTF8_SIG)

    def upsert_metadata_table_row(self, sample: SampleBaseModel, name: str) -> None:
        """向元数据索引表写入或更新单个样本条目。

        Args:
            sample: 需要写入索引的样本对象。
            name: 样本在当前存储方案下的文件名或目录名。

        Notes:
            表中至少维护 `uid`、文件名、别名和 `metadata` 的 JSON 展平结果。
            若表中已存在相同 `uid` 的旧记录，会先删除再追加新行。
        """

        df = self.load_metadata_table()
        row: dict[str, Any] = {
            META_COL_UID: sample.uid,
            META_COL_NAME: name,
            META_COL_ALIAS: sample.alias,
            META_COL_METADATA_JSON: json.dumps(sample.metadata.model_dump(), ensure_ascii=False, default=str),
        }
        row.update(sample.metadata.to_flatten_dict(sep="@"))
        if META_COL_UID in df.columns:
            df = df[df[META_COL_UID] != sample.uid]
        df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
        self.save_metadata_table(pd.DataFrame(df))

    def float_format(self) -> str | None:
        """返回 `pandas` 导出浮点列时可复用的格式化字符串。"""

        if self.decimal_round() is None:
            return None
        return f"%.{self.decimal_round()}f"

    def prepare_container_for_csv(self, category: str, data: Any) -> Any:
        """将数据容器转换为适合 CSV 导出的标准化对象。"""

        return self.deserialize_container(category, self.serialize_container(data))
