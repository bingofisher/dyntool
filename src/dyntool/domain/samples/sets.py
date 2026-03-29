"""领域样本集基础类。"""

from __future__ import annotations

from collections import UserDict
from pathlib import Path
from typing import Any, Callable, ClassVar, Generic, Iterable, Mapping, Self, TypeVar, cast

import pandas as pd
from pydantic import ValidationError

from ...logging import get_logger
from ..constants import DataCategory, SAMPLE_ATTR_TO_DATA_CATEGORY
from ..enums import SampleDomain
from ..metadata import MetadataBase
from ..models import DataModelBase
from ..runtime.errors import RecoverableIOError
from ..runtime import resolve_sample_set_runtime
from ..serialization import StructuredPayload, normalize_payload
from .base import SampleBase
from .batch import (
    BatchOperationReport,
    OperationResult,
    infer_batch_status,
    make_operation_result,
    run_callable_batch,
    run_vibeval_batch,
    select_sample_items,
)
from .commands import VibEvalCommand
from .namespaces import SampleSetEvaluationNamespace, SampleSetProcessingNamespace
from .types import SampleField, SampleLoadMode

SampleType = TypeVar("SampleType", bound=SampleBase)
logger = get_logger("samples")
_H5_SUFFIXES = {".h5", ".hdf5", ".hdf"}
_DEFAULT_SET_H5_FILENAME = "all_samples.h5"


def _require_storage_mode(value: Any | None) -> None:
    """校验公开 `mode` 参数必须使用正式枚举。"""

    if value is None or type(value).__name__ == "StorageMode":
        return
    raise TypeError("mode 参数必须是 StorageMode 枚举")


def _require_storage_scheme(value: Any | None) -> None:
    """校验公开 `storage_scheme` 参数必须使用正式枚举。"""

    if value is None or type(value).__name__ == "StorageScheme":
        return
    raise TypeError("storage_scheme 参数必须是 StorageScheme 枚举")


def _require_name_resolver(value: Any | None) -> None:
    """校验公开 `name_resolver` 参数。"""

    if value is None or callable(value):
        return
    raise TypeError("name_resolver 参数必须是可调用对象")


class SampleSetBase(Generic[SampleType], UserDict[str, SampleType]):  # type: ignore[type-var]
    """领域样本集抽象基础类。"""

    _sample_type: ClassVar[type[SampleBase]] = SampleBase
    _payload_domain: ClassVar[str] = "default"

    def __init__(
        self,
        samples: dict[str, SampleType] | list[SampleType] | None = None,
    ) -> None:
        super().__init__()
        self._validate_class_configuration()
        self.storage: Any = None
        self.strict: bool = True
        self.storage_dirty: bool = False
        self._last_operation_report: BatchOperationReport[Any] | None = None

        if samples:
            if isinstance(samples, list):
                self.update_from_list(samples)
            elif isinstance(samples, dict):
                self.update(samples)
            else:
                raise TypeError("samples 参数必须是字典或列表类型")

    def __setitem__(self, key: str, item: Any) -> None:
        _ = key
        self._bind_sample_internal(item)
        return
        normalized_key = key.strip()
        expected_type = self.sample_type
        if not isinstance(item, expected_type):
            raise TypeError(f"类型错误: {self.__class__.__name__} 仅接受 {expected_type.__name__} 类型")
        expected_key = item.uid.strip()
        if normalized_key != expected_key:
            normalized_key = expected_key
        item._storage_set = self
        super().__setitem__(normalized_key, item)

    def __getitem__(self, key: str) -> SampleType:
        return super().__getitem__(key.strip())

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}[{self.sample_type.__name__}] ({len(self)} samples)>"

    def _bind_sample_internal(self, sample: SampleType) -> str:
        """内部绑定样本并返回规范化 UID。"""

        expected_type = self.sample_type
        if not isinstance(sample, expected_type):
            raise TypeError(f"类型错误: {self.__class__.__name__} 仅接受 {expected_type.__name__} 类型")
        uid = sample.uid.strip()
        sample._storage_set = self
        super().__setitem__(uid, sample)
        return uid

    def add_sample(self, sample: SampleType) -> SampleType:
        """向样本集添加单个样本。"""

        self._bind_sample_internal(sample)
        if self.storage is not None:
            self.storage_dirty = True
        return sample

    def replace_sample(self, uid: str, sample: SampleType) -> SampleType:
        """按 UID 替换样本集中的样本。"""

        resolved_uid = uid.strip()
        if resolved_uid in self.data:
            self.data.pop(resolved_uid, None)
        self._bind_sample_internal(sample)
        if self.storage is not None:
            self.storage_dirty = True
        return sample

    @property
    def sample_type(self) -> type[SampleType]:
        """返回样本集管理的样本类型。"""

        return cast(type[SampleType], self._sample_type)

    @property
    def sample_schema(self) -> Any:
        """返回样本 schema。"""

        return self.sample_type.sample_schema

    @classmethod
    def supported_categories(cls) -> tuple[DataCategory, ...]:
        """返回当前样本集支持的公开 DataCategory 子集。"""

        return cls._sample_type.supported_categories()

    @classmethod
    def storable_categories(cls) -> tuple[DataCategory, ...]:
        """返回当前样本集允许进入存储流程的 DataCategory 子集。"""

        return cls._sample_type.storable_categories()

    @classmethod
    def supported_fields(cls) -> tuple[SampleField, ...]:
        """返回当前样本集内部使用的 SampleField 列表。"""

        return cls._sample_type.supported_fields()

    @classmethod
    def storable_fields(cls) -> tuple[SampleField, ...]:
        """返回当前样本集可持久化读写的 SampleField 列表。"""

        return cls._sample_type.storable_fields()

    def available_categories(self, uid: str) -> tuple[DataCategory, ...]:
        """返回指定样本当前已加载或可从已绑定 storage 读取的分类。"""

        if uid not in self:
            raise KeyError(f"样本 '{uid}' 不存在于样本集中")
        return self[uid].available_categories()

    @classmethod
    def get_sample_attr_types(cls, *attrs: str) -> dict[str, type]:
        """获取样本字段与槽位的类型注解。"""

        if cls._sample_type is SampleBase:
            raise TypeError("必须使用具体子类调用此方法")
        return cls._sample_type.get_attr_types(*attrs)

    def _validate_class_configuration(self) -> None:
        if self._sample_type is SampleBase:
            raise TypeError(f"类 {self.__class__.__name__} 未正确设置 _sample_type 属性")
        if not issubclass(self._sample_type, SampleBase):
            raise TypeError("_sample_type 必须是 SampleBase 的子类")

    def update(self, other: dict[str, SampleType] | Self) -> None:
        """从字典或另一份样本集更新当前样本集。"""

        if isinstance(other, (SampleSetBase, dict)):
            for key, value in other.items():
                self[key] = value
            return
        raise TypeError("只支持从字典或 SampleSetBase 实例更新")

    def update_from_list(self, samples: list[SampleType]) -> None:
        """从样本列表批量更新样本集。"""

        for sample in samples:
            self[sample.uid] = sample

    def update_data(
        self,
        uid: str,
        data: DataModelBase,
        *,
        strict: bool | None = None,
    ) -> bool:
        """更新指定样本的特定类别数据。"""

        strict_mode = self.strict if strict is None else strict
        if uid not in self:
            message = f"样本 '{uid}' 不存在于样本集中"
            if strict_mode:
                logger.error(f"update_data failed: {message}")
                raise KeyError(message)
            logger.warning(f"update_data skipped: {message}")
            return False
        field = self.sample_schema.resolve_field(data.category)
        self[uid].set_data_var(field, data)
        logger.info(f"update_data done: uid={uid}, field={field.value}")
        return True

    def update_sample(self, uid: str, *, strict: bool | None = None, **patch: Any) -> SampleType:
        """更新指定 UID 的样本。

        Args:
            uid: 待更新样本的 UID。
            strict: 是否覆盖样本更新过程的严格模式。
            **patch: 支持键为 `Sample.update()` 允许的字段，包括 `alias`、
                `metadata`、`data_vars` 以及样本 schema 声明的顶层槽位名。

        Returns:
            更新后的样本对象。
        """

        strict_mode = self.strict if strict is None else strict
        if uid not in self:
            raise KeyError(f"样本 '{uid}' 不存在于样本集中")
        sample = self[uid]
        sample.update(strict=strict_mode, **patch)
        if self.storage is not None:
            self.storage_dirty = True
        return sample

    def update_metadata(self, uid: str, *, strict: bool | None = None, **patch: Any) -> SampleType:
        """更新指定 UID 样本的 metadata 字段。

        Args:
            uid: 待更新样本的 UID。
            strict: 预留的严格模式参数；当前 metadata 校验由 metadata 模型本身负责。
            **patch: 支持键为当前 metadata 类型声明的字段名，例如 VibTest 主线中的
                `case`、`point`、`instr`、`dir`、`record`、`timestamp`、`extra`。

        Returns:
            更新后的样本对象。
        """

        del strict
        if uid not in self:
            raise KeyError(f"样本 '{uid}' 不存在于样本集中")
        sample = self[uid]
        sample.update_metadata(**patch)
        if self.storage is not None:
            self.storage_dirty = True
        return sample

    def load_data(
        self,
        uid: str,
        *,
        categories: Iterable[DataCategory | str] | None = None,
    ) -> SampleType:
        """显式加载指定样本的槽位数据。"""

        if uid not in self:
            raise KeyError(f"样本 '{uid}' 不存在于样本集中")
        normalized_fields = self._categories_to_fields(categories)
        sample = self[uid]
        sample.ensure_loaded(categories=normalized_fields)
        return sample

    def load_many(
        self,
        *,
        uids: Iterable[str] | None = None,
        categories: Iterable[DataCategory | str] | None = None,
        filter: Callable[[SampleType], bool] | None = None,
    ) -> Self:
        """批量显式加载多个样本的槽位数据。"""

        normalized_fields = self._categories_to_fields(categories)
        selected_items = self._select_samples(uid=None, uids=list(uids) if uids is not None else None, filter=filter)
        for _, sample in selected_items:
            sample.ensure_loaded(categories=normalized_fields)
        return self

    def prefetch(
        self,
        *,
        uids: Iterable[str] | None = None,
        categories: Iterable[DataCategory | str] | None = None,
        filter: Callable[[SampleType], bool] | None = None,
    ) -> Self:
        """预热指定样本的槽位数据。"""

        return self.load_many(uids=uids, categories=categories, filter=filter)

    def update_many(
        self,
        *,
        uids: Iterable[str] | None = None,
        criteria: Mapping[str, Any] | None = None,
        filter: Callable[[SampleType], bool] | None = None,
        metadata_patch: Mapping[str, Any] | None = None,
        data_patch: Mapping[str, DataModelBase | None] | None = None,
        alias: str | None = None,
        force_alias: bool = False,
    ) -> Self:
        """批量更新命中样本的 metadata、数据槽位和 alias。"""

        matched = self.find(uids=uids, criteria=criteria, filter=filter)
        for sample in matched.values():
            if metadata_patch:
                sample.update_metadata(**dict(metadata_patch))
            if data_patch:
                sample.update_data(**dict(data_patch))
            if alias is not None:
                sample.set_alias(alias)
            elif force_alias:
                sample.refresh_alias(force=force_alias)
        if self.storage is not None and len(matched) > 0:
            self.storage_dirty = True
        return self

    def delete_many(
        self,
        *,
        uids: Iterable[str] | None = None,
        criteria: Mapping[str, Any] | None = None,
        filter: Callable[[SampleType], bool] | None = None,
    ) -> list[str]:
        """删除命中的样本并返回已删除 UID 列表。"""

        matched = self.find(uids=uids, criteria=criteria, filter=filter)
        removed = list(matched.keys())
        for uid in removed:
            self.data.pop(uid, None)
        if self.storage is not None and removed:
            self.storage_dirty = True
        return removed

    @property
    def last_operation_report(self) -> BatchOperationReport[Any] | None:
        """返回最近一次批处理报告。"""

        return self._last_operation_report

    def get_metadata(self, **metadata_criteria: Any) -> list[MetadataBase]:
        """根据 metadata 等值条件筛选样本元数据。

        Args:
            **metadata_criteria: 支持键为当前 metadata 类型声明的字段名；只有字段值全
                部匹配的样本才会被返回。

        Returns:
            命中样本的 metadata 对象列表。
        """

        return [sample.metadata for sample in self.values() if sample.metadata.match(**metadata_criteria)]

    def get_uids(self, **metadata_criteria: Any) -> list[str]:
        """根据 metadata 等值条件获取匹配样本 UID 列表。

        Args:
            **metadata_criteria: 支持键为当前 metadata 类型声明的字段名；只有字段值全
                部匹配的样本才会被返回。

        Returns:
            命中样本的 UID 列表。
        """

        return [meta.uid for meta in self.get_metadata(**metadata_criteria)]

    def get_uid_by_metadata(self, metadata: MetadataBase) -> str:
        """根据元数据对象获取对应样本 UID。"""

        for uid, sample in self.items():
            if sample.metadata.uid == metadata.uid:
                return uid
        raise KeyError("未找到匹配的样本 UID")

    def get_metadatadf(self, flatten_sep: str = "@") -> pd.DataFrame:
        """将样本元数据转换为扁平化 DataFrame。"""

        if flatten_sep == "@" and self.storage is not None and not self.storage_dirty:
            try:
                return self.storage.metadata_frame(uids=list(self.keys()))
            except RuntimeError:
                pass
        metadata_list = [meta.to_flatten_dict(sep=flatten_sep) for meta in self.get_metadata()]
        return pd.DataFrame(metadata_list)

    def _normalize_requested_categories(
        self,
        categories: Iterable[DataCategory | str] | None = None,
        *,
        load_mode: SampleLoadMode | None = None,
    ) -> list[DataCategory] | None:
        """将公开 `categories` 解析为去重后的 `DataCategory` 列表。"""

        if load_mode is SampleLoadMode.METADATA_ONLY and categories is not None:
            raise ValueError("load_mode=METADATA_ONLY 时不允许同时声明 categories")
        if categories is None:
            return None

        resolved: list[DataCategory] = []
        supported = set(self.supported_categories())
        for raw_category in categories:
            normalized_text = str(raw_category).strip()
            try:
                category = raw_category if isinstance(raw_category, DataCategory) else DataCategory(normalized_text)
            except ValueError as exc:
                category = SAMPLE_ATTR_TO_DATA_CATEGORY.get(normalized_text)
                if category is None:
                    raise ValueError(
                        f"无效的 categories 取值: {raw_category}。请使用 DataCategory 枚举、其 value 字符串，或正式槽位名。"
                    ) from exc
            if category not in supported:
                raise ValueError(f"DataCategory '{category.value}' 不能作为样本加载选择器。")
            if category not in resolved:
                resolved.append(category)
        return resolved or None

    def _categories_to_fields(
        self,
        categories: Iterable[DataCategory | str] | None = None,
        *,
        load_mode: SampleLoadMode | None = None,
    ) -> list[SampleField] | None:
        """把公开 categories 解析为内部 SampleField 列表。"""

        normalized = self._normalize_requested_categories(categories, load_mode=load_mode)
        if normalized is None:
            return None
        return [self.sample_schema.resolve_field(category) for category in normalized]

    def find_by_alias(self, alias: str) -> SampleType | None:
        """按 alias 查找单个样本。"""

        target = str(alias).strip()
        for sample in self.values():
            if sample.alias == target:
                return sample
        return None

    def get_uid_by_alias(self, alias: str) -> str:
        """按 alias 返回样本 UID。"""

        sample = self.find_by_alias(alias)
        if sample is None:
            raise KeyError(f"未找到 alias 对应的样本: {alias}")
        return sample.uid

    def refresh_aliases(self, *, force: bool = False) -> Self:
        """批量刷新样本集内样本 alias。"""

        for sample in self.values():
            sample.refresh_alias(force=force)
        if self.storage is not None:
            self.storage_dirty = True
        return self

    def get_data(self, uid: str, category: str | DataCategory) -> DataModelBase | None:
        """获取指定样本的特定类别数据。"""

        if uid not in self:
            raise KeyError(f"样本 '{uid}' 不存在于样本集中")
        return self[uid].get_data_var(self.sample_schema.resolve_field(category))

    def get_data_dict(self, category: str | DataCategory) -> dict[str, DataModelBase]:
        """获取指定类别的所有样本数据字典。"""

        field = self.sample_schema.resolve_field(category)
        data_dict: dict[str, DataModelBase] = {}
        for uid, sample in self.items():
            data = sample.get_data_var(field)
            if isinstance(data, DataModelBase):
                data_dict[uid] = data
        return data_dict

    def current_units(self) -> dict[str, dict[str, dict[str, str]]]:
        """返回样本集内所有样本的当前单位。"""

        return {uid: sample.current_units() for uid, sample in self.items()}

    def convert_units(
        self,
        units: Mapping[str, Mapping[str, str | None]],
        *,
        replace: bool = True,
    ) -> Self:
        """按槽位批量转换样本集内部数据单位。"""

        if replace:
            for sample in self.values():
                sample.convert_units(units, replace=True)
            return self
        return self.__class__({uid: sample.convert_units(units, replace=False) for uid, sample in self.items()})

    def get_samples(
        self,
        filter: Callable[[SampleType], bool] | None = None,
    ) -> Self:
        """返回符合条件的新样本集。"""

        return self.__class__(dict(self._filtered_items(filter=filter)))

    def get_sample(
        self, filter: Callable[[SampleType], bool] | None = None, *, strict: bool = True
    ) -> SampleType | None:
        """返回唯一匹配的样本。"""

        matched_sample: SampleType | None = None
        for _, sample in self._filtered_items(filter=filter):
            if matched_sample is not None:
                raise ValueError("expected exactly one matched sample")
            matched_sample = sample
        if strict and matched_sample is None:
            raise ValueError("no matched sample found")
        return matched_sample

    def find(
        self,
        *,
        uids: Iterable[str] | None = None,
        criteria: Mapping[str, Any] | None = None,
        filter: Callable[[SampleType], bool] | None = None,
        sort_by: str | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> Self:
        """按 UID、metadata 条件和过滤函数查询样本。"""

        selected_uids = {str(uid).strip() for uid in uids} if uids is not None else None
        criteria_map = dict(criteria or {})
        items = list(self.items())
        if selected_uids is not None:
            items = [(uid, sample) for uid, sample in items if uid in selected_uids]
        if criteria_map:
            items = [
                (uid, sample)
                for uid, sample in items
                if all(getattr(sample.metadata, field, None) == expected for field, expected in criteria_map.items())
            ]
        if filter is not None:
            items = [(uid, sample) for uid, sample in items if filter(sample)]
        if sort_by is not None:
            items.sort(key=lambda item: getattr(item[1].metadata, sort_by, None))
        if offset > 0:
            items = items[offset:]
        if limit is not None:
            items = items[:limit]
        return self.__class__(dict(items))

    def find_one(
        self,
        *,
        uids: Iterable[str] | None = None,
        criteria: Mapping[str, Any] | None = None,
        filter: Callable[[SampleType], bool] | None = None,
        sort_by: str | None = None,
    ) -> SampleType | None:
        """返回按查询条件命中的首个样本。"""

        matched = self.find(uids=uids, criteria=criteria, filter=filter, sort_by=sort_by, limit=1)
        return next(iter(matched.values()), None)

    def count(
        self,
        *,
        uids: Iterable[str] | None = None,
        criteria: Mapping[str, Any] | None = None,
        filter: Callable[[SampleType], bool] | None = None,
    ) -> int:
        """返回按条件命中的样本数量。"""

        return len(self.find(uids=uids, criteria=criteria, filter=filter))

    def exists(
        self,
        *,
        uids: Iterable[str] | None = None,
        criteria: Mapping[str, Any] | None = None,
        filter: Callable[[SampleType], bool] | None = None,
    ) -> bool:
        """判断是否存在按条件命中的样本。"""

        return self.count(uids=uids, criteria=criteria, filter=filter) > 0

    def distinct(
        self,
        field: str,
        *,
        uids: Iterable[str] | None = None,
        criteria: Mapping[str, Any] | None = None,
        filter: Callable[[SampleType], bool] | None = None,
    ) -> tuple[Any, ...]:
        """返回指定 metadata 字段的去重值。"""

        values: list[Any] = []
        for sample in self.find(uids=uids, criteria=criteria, filter=filter).values():
            value = getattr(sample.metadata, field, None)
            if value not in values:
                values.append(value)
        return tuple(values)

    def project_metadata(
        self,
        *,
        fields: Iterable[str] | None = None,
        uids: Iterable[str] | None = None,
        criteria: Mapping[str, Any] | None = None,
        filter: Callable[[SampleType], bool] | None = None,
    ) -> list[dict[str, Any]]:
        """投影返回命中样本的 metadata 字段。"""

        selected_fields = [str(field) for field in fields] if fields is not None else None
        projected: list[dict[str, Any]] = []
        for sample in self.find(uids=uids, criteria=criteria, filter=filter).values():
            metadata_dict = sample.metadata.to_dict()
            if selected_fields is None:
                projected.append(metadata_dict)
                continue
            projected.append({field: metadata_dict.get(field) for field in selected_fields})
        return projected

    def filter(
        self,
        filter: Callable[[SampleType], bool] | None = None,
    ) -> Self:
        """按谓词原位过滤样本集。"""

        filtered = self.get_samples(filter=filter)
        self.clear()
        self.update(filtered)
        return self

    def _filtered_items(
        self,
        *,
        filter: Callable[[SampleType], bool] | None = None,
    ) -> list[tuple[str, SampleType]]:
        """返回符合筛选条件的样本条目。"""

        if filter is None:
            return list(self.items())
        return [(uid, sample) for uid, sample in self.items() if filter(sample)]

    def _on_sample_metadata_changed(self, sample: SampleType, old_uid: str) -> None:
        """在样本元数据变更后重写 UID 索引并标记存储为脏。"""

        new_uid = sample.uid
        if new_uid != old_uid and new_uid in self and self[new_uid] is not sample:
            raise ValueError(f"样本集内已存在 UID 冲突: {new_uid}")
        if old_uid in self.data and self.data[old_uid] is sample:
            del self.data[old_uid]
        self.data[new_uid] = sample
        sample._storage_set = self
        if self.storage is not None:
            self.storage_dirty = True

    def _on_sample_identity_changed(
        self,
        sample: SampleType,
        old_uid: str,
        old_alias: str | None = None,
        *,
        force_alias: bool = False,
    ) -> None:
        """统一处理样本 identity 变化后的重索引。"""

        del old_alias, force_alias
        self._on_sample_metadata_changed(sample, old_uid)

    @classmethod
    def build_from_metadatadf(cls, df: Any) -> Self:
        """从元数据 DataFrame 重建样本集。"""

        df = pd.DataFrame(df)
        if df.empty:
            return cls()
        instance = cls()
        metadata_class = cls._sample_type.sample_schema.metadata_type
        for _, row in df.iterrows():
            try:
                metadata = metadata_class.from_flatten_dict(row.to_dict())  # type: ignore[union-attr]
                sample = cls._sample_type(metadata=metadata)  # type: ignore[call-arg]
                instance[sample.uid] = sample
            except ValidationError:
                continue
            except Exception:
                continue
        return instance

    def connect_storage(
        self,
        base_dir: str | Path,
        *,
        strict: bool | None = None,
        **kwargs: Any,
    ) -> Self:
        """为当前样本集绑定存储上下文。

        Args:
            base_dir: 样本集根目录、集合文件路径或容器目录。
            strict: 是否覆盖当前样本集的严格模式。`None` 表示保留现有设置。
            **kwargs: 支持键包括 `mode`、`storage_scheme`、`data_options`、
                `name_resolver`、`set_filename`。这些键分别用于控制创建/打开模式、
                存储方案、底层存储配置、样本命名解析和集合级文件名。

        Returns:
            当前样本集对象本身。
        """

        _require_storage_mode(kwargs.get("mode"))
        _require_storage_scheme(kwargs.get("storage_scheme"))
        _require_name_resolver(kwargs.get("name_resolver"))

        result = cast(
            Self,
            resolve_sample_set_runtime(self, action="connect_storage").connect_sample_set_storage(
                self,
                str(base_dir),
                **kwargs,
            ),
        )
        if strict is not None:
            result.strict = strict
        return result

    def _conversion_fields(
        self,
        categories: list[DataCategory | str] | None,
    ) -> list[SampleField]:
        """返回转换前需要保证可用的内部槽位列表。"""

        resolved = self._categories_to_fields(categories)
        if resolved is not None:
            return resolved
        return list(self.storable_fields())

    def _resolve_conversion_target(
        self,
        path: str | Path,
        *,
        storage_scheme: Any,
        set_filename: str | None,
    ) -> tuple[Path, str | None]:
        """解析转换目标的规范根路径与集合文件名。"""

        resolved_path = Path(path).resolve()
        scheme_value = str(getattr(storage_scheme, "value", storage_scheme))
        if scheme_value == "set_h5":
            if resolved_path.suffix.lower() in _H5_SUFFIXES:
                return resolved_path.parent, resolved_path.name
            return resolved_path, set_filename or _DEFAULT_SET_H5_FILENAME
        return resolved_path, set_filename

    def _matches_current_storage_target(
        self,
        *,
        target_base_dir: Path,
        storage_scheme: Any,
        target_set_filename: str | None,
    ) -> bool:
        """判断转换目标是否与当前已连接存储等价。"""

        if self.storage is None or getattr(self.storage, "base_dir", None) is None:
            return False

        current_scheme = getattr(self.storage, "storage_scheme", None)
        current_scheme_value = str(getattr(current_scheme, "value", current_scheme))
        target_scheme_value = str(getattr(storage_scheme, "value", storage_scheme))
        current_base_dir = Path(self.storage.base_dir).resolve()
        if current_scheme_value != target_scheme_value or current_base_dir != target_base_dir:
            return False
        if target_scheme_value != "set_h5":
            return True

        current_set_filename = str(getattr(self.storage, "set_filename", _DEFAULT_SET_H5_FILENAME))
        resolved_target_set_filename = str(target_set_filename or _DEFAULT_SET_H5_FILENAME)
        return current_set_filename == resolved_target_set_filename

    def _ensure_conversion_source_ready(
        self,
        *,
        items: list[tuple[str, SampleType]],
        required_fields: list[SampleField],
    ) -> None:
        """确保转换前所需槽位已在内存中可用。"""

        for _, sample in items:
            pending_fields = [field for field in required_fields if not sample.is_loaded(field)]
            if not pending_fields:
                continue
            source_storage = getattr(getattr(sample, "_storage_set", None), "storage", None)
            if source_storage is None:
                if sample.load_mode in {SampleLoadMode.LAZY, SampleLoadMode.METADATA_ONLY}:
                    raise RuntimeError(
                        "当前样本集存在未完全加载的样本，且缺少可用于补载的源存储连接，无法转换储存模式。"
                    )
                continue
            sample.ensure_loaded(categories=pending_fields)

    def _is_full_storage_conversion(
        self,
        *,
        categories: list[DataCategory | str] | None,
        filter: Callable[[SampleType], bool] | None,
    ) -> bool:
        """判断当前转换是否覆盖整个样本集及全部可存储槽位。"""

        if filter is not None:
            return False
        if categories is None:
            return True
        return set(self._conversion_fields(categories)) == set(self.storable_fields())

    def _build_conversion_snapshot(
        self,
        *,
        items: list[tuple[str, SampleType]],
        strict: bool,
    ) -> Self:
        """基于当前样本状态构建用于落盘的独立快照。"""

        snapshot = self.__class__()
        snapshot.strict = strict
        for _, sample in items:
            cloned = cast(SampleType, sample.model_copy(deep=True))
            snapshot[cloned.uid] = cloned
        return snapshot

    def convert_storage(
        self,
        path: str | Path,
        *,
        mode: Any | None = None,
        storage_scheme: Any,
        data_options: dict[str, Any] | None = None,
        categories: list[DataCategory | str] | None = None,
        strict: bool | None = None,
        filter: Callable[[SampleType], bool] | None = None,
        workers: int = 1,
        chunk_size: int = 256,
        name_resolver: Any | None = None,
        set_filename: str | None = None,
    ) -> Self:
        """将当前样本集复制转换为另一种正式存储方案。

        Args:
            path: 显式目标路径，必须不同于当前已连接存储。
            mode: 目标存储连接模式；未显式提供时沿用 `save()` 的默认创建语义。
            storage_scheme: 目标存储方案枚举，必须使用正式 `StorageScheme`。
            data_options: 目标存储使用的正式 `data_options`。
            categories: 仅转换指定公开分类；为 `None` 时转换全部可存储分类。
            strict: 是否覆盖当前样本集的严格模式。
            filter: 仅转换命中的样本；命中样本之外的内容不会写入目标。
            workers: 批量写入 worker 数量。
            chunk_size: 批量写入分块大小。
            name_resolver: 可选目标样本命名解析器。
            set_filename: 集合级文件名，仅在集合容器方案中生效。

        Returns:
            当前样本集对象本身。

        Notes:
            本方法是复制式转换，不会删除旧存储。只有完整转换时才会在成功后把当前实例重绑到新存储；
            若使用了 `filter` 或仅转换部分 `categories`，则当前实例保持原存储绑定不变。
        """

        _require_storage_mode(mode)
        _require_storage_scheme(storage_scheme)
        _require_name_resolver(name_resolver)

        target_base_dir, target_set_filename = self._resolve_conversion_target(
            path,
            storage_scheme=storage_scheme,
            set_filename=set_filename,
        )
        if self._matches_current_storage_target(
            target_base_dir=target_base_dir,
            storage_scheme=storage_scheme,
            target_set_filename=target_set_filename,
        ):
            raise ValueError("convert_storage() 的目标路径与当前存储等价，请提供不同的目标路径或存储方案。")

        effective_strict = self.strict if strict is None else strict
        selected_items = self._filtered_items(filter=filter)
        required_fields = self._conversion_fields(categories)
        self._ensure_conversion_source_ready(items=selected_items, required_fields=required_fields)

        snapshot = self._build_conversion_snapshot(items=selected_items, strict=effective_strict)
        snapshot.save(
            path,
            mode=mode,
            storage_scheme=storage_scheme,
            data_options=data_options,
            categories=categories,
            strict=effective_strict,
            workers=workers,
            chunk_size=chunk_size,
            name_resolver=name_resolver,
            set_filename=set_filename,
        )

        if self._is_full_storage_conversion(categories=categories, filter=filter):
            self.connect_storage(
                target_base_dir,
                strict=effective_strict,
                storage_scheme=storage_scheme,
                data_options=data_options,
                name_resolver=name_resolver,
                set_filename=target_set_filename,
            )
            self.storage_dirty = False
        return self

    def save(
        self,
        path: str | Path | None = None,
        *,
        mode: Any | None = None,
        storage_scheme: Any | None = None,
        data_options: dict[str, Any] | None = None,
        categories: list[DataCategory | str] | None = None,
        strict: bool | None = None,
        filter: Callable[[SampleType], bool] | None = None,
        workers: int = 1,
        chunk_size: int = 256,
        name_resolver: Any | None = None,
        set_filename: str | None = None,
    ) -> Self:
        """保存当前样本集级元信息与样本内容。

        Args:
            path: 可选的显式目标路径；为 `None` 时要求当前样本集已连接存储。
            mode: 存储打开模式，通常为创建或覆盖。
            storage_scheme: 存储方案枚举，例如 `SET_H5`、`SAMPLE_DIR`。
            data_options: 传给底层存储实现的命名配置映射。
            categories: 公开读取/保存选择器。支持 `DataCategory` 枚举或其 value 字符串。
            strict: 是否覆盖当前样本集的严格模式。
            filter: 样本过滤函数，仅对命中的样本执行保存。
            workers: 批量保存并行 worker 数量。
            chunk_size: 批量保存的分块大小。
            name_resolver: 自定义样本文件名解析器。
            set_filename: 集合级文件名，仅在容器化方案下生效。

        Returns:
            当前样本集对象本身。

        Notes:
            `categories` 会先统一映射到内部 `SampleField`，再参与后续存储路由。
        """

        _require_storage_mode(mode)
        _require_storage_scheme(storage_scheme)
        _require_name_resolver(name_resolver)
        resolved_categories = self._categories_to_fields(categories)

        result = cast(
            Self,
            resolve_sample_set_runtime(self, action="save").save_sample_set(
                self,
                path=str(path) if path is not None else None,
                mode=mode,
                storage_scheme=storage_scheme,
                data_options=data_options,
                categories=resolved_categories,
                strict=self.strict if strict is None else strict,
                filter=filter,
                workers=workers,
                chunk_size=chunk_size,
                name_resolver=name_resolver,
                set_filename=set_filename,
            ),
        )
        result.storage_dirty = False
        return result

    def load(
        self,
        path: str | Path | None = None,
        *,
        mode: Any | None = None,
        storage_scheme: Any | None = None,
        data_options: dict[str, Any] | None = None,
        categories: list[DataCategory | str] | None = None,
        load_mode: SampleLoadMode = SampleLoadMode.LAZY,
        strict: bool | None = None,
        filter: Callable[[SampleType], bool] | None = None,
        workers: int = 1,
        chunk_size: int = 256,
        set_filename: str | None = None,
    ) -> Self:
        """加载当前样本集内容。

        Args:
            path: 可选的显式来源路径；为 `None` 时从已连接存储上下文读取。
            mode: 存储打开模式，通常为打开或只读。
            storage_scheme: 存储方案枚举，例如 `SET_H5`、`SAMPLE_DIR`。
            data_options: 传给底层存储实现的命名配置映射。
            categories: 公开读取选择器。支持 `DataCategory` 枚举或其 value 字符串。
            load_mode: 样本加载模式。`METADATA_ONLY` 只恢复索引，`LAZY` 按需读取，
                `EAGER` 立即加载声明目标槽位。
            strict: 是否覆盖当前样本集的严格模式。
            filter: 样本过滤函数，仅对命中的样本执行加载。
            workers: 批量加载并行 worker 数量。
            chunk_size: 批量加载的分块大小。
            set_filename: 集合级文件名，仅在容器化方案下生效。

        Returns:
            当前样本集对象本身。
        """

        _require_storage_mode(mode)
        _require_storage_scheme(storage_scheme)
        normalized_fields = self._categories_to_fields(categories, load_mode=load_mode)
        runtime_categories = (
            [] if load_mode in {SampleLoadMode.METADATA_ONLY, SampleLoadMode.LAZY} else normalized_fields
        )

        result = cast(
            Self,
            resolve_sample_set_runtime(self, action="load").load_sample_set(
                self,
                path=str(path) if path is not None else None,
                mode=mode,
                storage_scheme=storage_scheme,
                data_options=data_options,
                categories=runtime_categories,
                strict=strict,
                filter=filter,
                workers=workers,
                chunk_size=chunk_size,
                set_filename=set_filename,
            ),
        )
        for sample in result.values():
            sample._set_load_mode_internal(load_mode)
        result.storage_dirty = False
        return result

    def _build_storage_report(
        self,
        *,
        action: str,
        strict: bool,
        items: list[tuple[str, SampleType]],
        errors: dict[str, Exception],
    ) -> BatchOperationReport[Self]:
        """根据底层存储错误映射构造正式批量报告。"""

        report = BatchOperationReport[Self](action=action, strict=strict)
        report.stats.valid_samples = len(items)
        for item_uid, _ in items:
            error = errors.get(item_uid)
            if error is None:
                report.add(
                    item_uid,
                    make_operation_result(action=action, success=True, message="完成", value=self),
                )
                continue
            report.add(
                item_uid,
                make_operation_result(
                    action=action,
                    success=False,
                    message=str(error),
                    value=self,
                    error=error,
                ),
            )
        self._last_operation_report = report
        return report

    def save_all(
        self,
        *,
        categories: list[DataCategory | str] | None = None,
        strict: bool | None = None,
        filter: Callable[[SampleType], bool] | None = None,
        workers: int = 1,
        chunk_size: int = 256,
    ) -> BatchOperationReport[Self]:
        """批量保存当前样本集中的样本。

        Args:
            categories: 公开保存选择器。支持 `DataCategory` 枚举或其 value 字符串。
            strict: 是否覆盖当前样本集的严格模式。
            filter: 样本过滤函数，仅对命中的样本执行保存。
            workers: 并行 worker 数量。
            chunk_size: 每批处理的样本数量。

        Returns:
            `BatchOperationReport[Self]`，报告逐样本保存结果。
        """

        effective_strict = self.strict if strict is None else strict
        resolved_categories = self._categories_to_fields(categories)
        items = self._filtered_items(filter=filter)
        errors = resolve_sample_set_runtime(
            self,
            action="save_all",
        ).save_all_samples(
            self,
            categories=resolved_categories,
            strict=effective_strict,
            filter=filter,
            workers=workers,
            chunk_size=chunk_size,
        )
        report = self._build_storage_report(action="save_all", strict=effective_strict, items=items, errors=errors)
        if report.stats.failed == 0:
            self.storage_dirty = False
        return report

    def load_all(
        self,
        *,
        progress_callback: Callable[[int, int], None] | None = None,
        categories: list[DataCategory | str] | None = None,
        load_mode: SampleLoadMode = SampleLoadMode.EAGER,
        strict: bool | None = None,
        filter: Callable[[SampleType], bool] | None = None,
        workers: int = 1,
        chunk_size: int = 256,
    ) -> BatchOperationReport[Self]:
        """批量加载样本集中的样本。

        Args:
            progress_callback: 进度回调，参数为 `(completed, total)`。
            categories: 公开加载选择器。支持 `DataCategory` 枚举或其 value 字符串。
            load_mode: 样本加载模式。`METADATA_ONLY` 只恢复索引，`LAZY` 按需读取，
                `EAGER` 立即加载声明目标槽位。
            strict: 是否覆盖当前样本集的严格模式。
            filter: 样本过滤函数，仅对命中的样本执行加载。
            workers: 并行 worker 数量。
            chunk_size: 每批处理的样本数量。

        Returns:
            `BatchOperationReport[Self]`，报告逐样本加载结果。
        """

        effective_strict = self.strict if strict is None else strict
        normalized_fields = self._categories_to_fields(categories, load_mode=load_mode)
        runtime_categories = (
            [] if load_mode in {SampleLoadMode.METADATA_ONLY, SampleLoadMode.LAZY} else normalized_fields
        )
        errors = resolve_sample_set_runtime(
            self,
            action="load_all",
        ).load_all_samples(
            self,
            progress_callback=progress_callback,
            categories=runtime_categories,
            strict=effective_strict,
            filter=filter,
            workers=workers,
            chunk_size=chunk_size,
        )
        for sample in self.values():
            sample._set_load_mode_internal(load_mode)
        items = self._filtered_items(filter=filter)
        report = self._build_storage_report(action="load_all", strict=effective_strict, items=items, errors=errors)
        if report.stats.failed == 0:
            self.storage_dirty = False
        return report

    def organize_storage(self) -> Self:
        """按当前样本集清理存储中的冗余条目。"""

        result = cast(
            Self,
            resolve_sample_set_runtime(
                self,
                action="organize_storage",
            ).organize_sample_set_storage(self),
        )
        result.storage_dirty = False
        return result

    def export_metadata(self, path: str | Path, *, flatten_sep: str = "@") -> Path:
        """将元数据表导出为 CSV。"""

        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        self.get_metadatadf(flatten_sep=flatten_sep).to_csv(
            target,
            index=False,
            encoding="utf-8-sig",
        )
        return target

    def import_metadata(self, path: str | Path) -> Self:
        """从 metadata CSV 导入并补丁更新现有样本元数据。"""

        metadata_df = pd.read_csv(path, encoding="utf-8")
        metadata_class = self._sample_type.sample_schema.metadata_type
        for _, row in metadata_df.iterrows():
            payload = row.to_dict()
            exported_uid = str(payload.get("uid", "")).strip()
            metadata = metadata_class.from_flatten_dict(payload)  # type: ignore[union-attr]
            if exported_uid and exported_uid in self:
                self[exported_uid].replace_metadata(metadata)
                continue
            if metadata.uid in self:
                self[metadata.uid].replace_metadata(metadata)
                continue
            self[metadata.uid] = self.sample_type(metadata=metadata)  # type: ignore[call-arg]
        return self

    @property
    def processing(self) -> SampleSetProcessingNamespace:
        """返回样本集处理命名空间。"""

        return SampleSetProcessingNamespace(self)

    @property
    def evaluation(self) -> SampleSetEvaluationNamespace:
        """返回样本集评价命名空间。"""

        return SampleSetEvaluationNamespace(self)

    def preprocess(self, *, strict: bool | None = None, **kwargs: Any) -> BatchOperationReport[Self]:
        """执行样本集预处理工作流。

        Args:
            strict: 是否覆盖当前样本集的严格模式。
            **kwargs: 支持键包括 `truncate_range`、`baseline`、`baseline_order`、
                `highpass`、`lowpass`、`bandpass`、`filter_order`。这些键会逐样本
                传给 `Sample.preprocess()`。
        """

        from .workflows import preprocess_sample_set

        return cast(BatchOperationReport[Self], preprocess_sample_set(self, strict=strict, **kwargs))

    def evaluate(self, command: VibEvalCommand, **kwargs: Any) -> BatchOperationReport[Self]:
        """执行样本集评价命令。

        Args:
            command: 要执行的 `VibEvalCommand` 枚举值。
            **kwargs: 支持键包括 `overwrite`、`strict`、`uid`、`uids`、`filter`，
                以及评价命令支持的参数：`freq_range`、`weight_type`、`time_windows`、
                `nsup`、`calc_unit_system`、`output_unit_system`。
        """

        from .workflows import evaluate_sample_set

        return cast(BatchOperationReport[Self], evaluate_sample_set(self, command, **kwargs))

    def eval_zvl(
        self,
        *,
        overwrite: bool = False,
        uid: str | None = None,
        uids: list[str] | None = None,
        filter: Callable[[SampleType], bool] | None = None,
        **kwargs: Any,
    ) -> BatchOperationReport[Self]:
        """执行 ZVL 批量评价。

        Args:
            overwrite: 是否允许覆盖已有 `zvl` 结果。
            uid: 仅处理单个样本 UID。
            uids: 处理多个样本 UID。
            filter: 样本过滤函数。
            **kwargs: 支持键包括 `strict`、`freq_range`、`weight_type`、
                `time_windows`、`calc_unit_system`、`output_unit_system`。
        """

        return self.evaluate(
            VibEvalCommand.ZVL,
            overwrite=overwrite,
            uid=uid,
            uids=uids,
            filter=filter,
            **kwargs,
        )

    def eval_otovl(
        self,
        *,
        overwrite: bool = False,
        uid: str | None = None,
        uids: list[str] | None = None,
        filter: Callable[[SampleType], bool] | None = None,
        **kwargs: Any,
    ) -> BatchOperationReport[Self]:
        """执行 OTOVL 批量评价。

        Args:
            overwrite: 是否允许覆盖已有 `otovl` 结果。
            uid: 仅处理单个样本 UID。
            uids: 处理多个样本 UID。
            filter: 样本过滤函数。
            **kwargs: 支持键包括 `strict`、`freq_range`、`time_windows`、
                `calc_unit_system`、`output_unit_system`。
        """

        return self.evaluate(
            VibEvalCommand.OTOVL,
            overwrite=overwrite,
            uid=uid,
            uids=uids,
            filter=filter,
            **kwargs,
        )

    def eval_fdmvl(
        self,
        *,
        overwrite: bool = False,
        uid: str | None = None,
        uids: list[str] | None = None,
        filter: Callable[[SampleType], bool] | None = None,
        **kwargs: Any,
    ) -> BatchOperationReport[Self]:
        """执行 FDMVL 批量评价。

        Args:
            overwrite: 是否允许覆盖已有 `fdmvl` 结果。
            uid: 仅处理单个样本 UID。
            uids: 处理多个样本 UID。
            filter: 样本过滤函数。
            **kwargs: 支持键包括 `strict`、`freq_range`、`calc_unit_system`、
                `output_unit_system`。
        """

        return self.evaluate(
            VibEvalCommand.FDMVL,
            overwrite=overwrite,
            uid=uid,
            uids=uids,
            filter=filter,
            **kwargs,
        )

    def eval_fpvdv(
        self,
        *,
        overwrite: bool = False,
        uid: str | None = None,
        uids: list[str] | None = None,
        filter: Callable[[SampleType], bool] | None = None,
        **kwargs: Any,
    ) -> BatchOperationReport[Self]:
        """执行 FPVDV 批量评价。

        Args:
            overwrite: 是否允许覆盖已有 `fpvdv` 结果。
            uid: 仅处理单个样本 UID。
            uids: 处理多个样本 UID。
            filter: 样本过滤函数。
            **kwargs: 支持键包括 `strict`、`freq_range`、`nsup`、
                `calc_unit_system`、`output_unit_system`。
        """

        return self.evaluate(
            VibEvalCommand.FPVDV,
            overwrite=overwrite,
            uid=uid,
            uids=uids,
            filter=filter,
            **kwargs,
        )

    def flow(self) -> Any:
        """返回以当前样本集为起点的计算流。"""

        from ...compute.flow import ComputeFlow

        return ComputeFlow(_result=self)

    def _select_samples(
        self,
        *,
        uid: str | None = None,
        uids: list[str] | None = None,
        filter: Callable[[SampleType], bool] | None = None,
    ) -> list[tuple[str, SampleType]]:
        """统一筛选待处理样本。"""

        return select_sample_items(
            self.data,
            uid=uid,
            uids=uids,
            filter_func=filter,
        )

    @staticmethod
    def _recoverable_io_error() -> type[Exception]:
        return RecoverableIOError

    def _batch_vibeval(
        self,
        command: VibEvalCommand,
        overwrite: bool = False,
        strict: bool | None = None,
        uid: str | None = None,
        uids: list[str] | None = None,
        filter: Callable[[SampleType], bool] | None = None,
        **options: Any,
    ) -> BatchOperationReport[Self]:
        """批量振动评价通用实现。"""

        items = self._select_samples(uid=uid, uids=uids, filter=filter)
        strict_mode = self.strict if strict is None else strict
        report = run_vibeval_batch(
            items,
            command=command,
            overwrite=overwrite,
            strict=strict_mode,
            **options,
        )
        self._last_operation_report = cast(BatchOperationReport[Any], report)
        logger.info(
            f"{command.label} summary: strict={strict_mode}, overwrite={overwrite}, "
            f"total={report.stats.total}, valid={report.stats.valid_samples}, "
            f"success={report.stats.succeeded}, skipped={report.stats.skipped}, failed={report.stats.failed}"
        )
        return cast(BatchOperationReport[Self], report)

    def _batch_sample_method(
        self,
        method_name: str,
        *,
        overwrite: bool = False,
        strict: bool | None = None,
        uid: str | None = None,
        uids: list[str] | None = None,
        filter: Callable[[SampleType], bool] | None = None,
        **kwargs: Any,
    ) -> BatchOperationReport[Self]:
        """按统一规则批量调用样本实例方法。"""

        sample_method = getattr(self.sample_type, method_name, None)
        if not callable(sample_method):
            raise TypeError(f"{self.sample_type.__name__} 不支持 {method_name}()")

        items = self._select_samples(uid=uid, uids=uids, filter=filter)
        strict_mode = self.strict if strict is None else strict
        report = BatchOperationReport[Self](action=method_name, strict=strict_mode)
        report.stats.valid_samples = sum(1 for _, sample in items if getattr(sample, "accel", None) is not None)
        recoverable_io_error = self._recoverable_io_error()
        for item_uid, sample in items:
            bound_method = getattr(sample, method_name, None)
            if not callable(bound_method):
                raise TypeError(f"{type(sample).__name__} 不支持 {method_name}()")

            result = bound_method(overwrite=overwrite, **kwargs)
            if not isinstance(result, OperationResult):
                status = infer_batch_status(bool(result[0]), str(result[1]))  # type: ignore[index]
                result = OperationResult(
                    action=method_name,
                    status=status,
                    message=str(result[1]),  # type: ignore[index]
                    value=self,
                )
            report.add(item_uid, cast(OperationResult[Self], result))
            if result.status == "failed":
                logger.warning(f"{method_name} failed: uid={item_uid}, message={result.message}")
                if strict_mode:
                    self._last_operation_report = cast(BatchOperationReport[Any], report)
                    raise recoverable_io_error(f"批处理失败: {item_uid}") from result.error
            elif result.status == "skipped":
                logger.warning(f"{method_name} skipped: uid={item_uid}, message={result.message}")
            else:
                logger.info(f"{method_name} done: uid={item_uid}")

        self._last_operation_report = cast(BatchOperationReport[Any], report)
        logger.info(
            f"{method_name} summary: strict={strict_mode}, overwrite={overwrite}, "
            f"total={report.stats.total}, valid={report.stats.valid_samples}, "
            f"success={report.stats.succeeded}, skipped={report.stats.skipped}, failed={report.stats.failed}"
        )
        return cast(BatchOperationReport[Self], report)

    def calc_freqspec(
        self,
        *,
        overwrite: bool = False,
        strict: bool | None = None,
        uid: str | None = None,
        uids: list[str] | None = None,
        filter: Callable[[SampleType], bool] | None = None,
        **kwargs: Any,
    ) -> BatchOperationReport[Self]:
        """批量计算样本集内样本的组合频谱。"""

        return self._batch_sample_method(
            "calc_freqspec",
            overwrite=overwrite,
            strict=strict,
            uid=uid,
            uids=uids,
            filter=filter,
            **kwargs,
        )

    def calc_respspec(
        self,
        *,
        overwrite: bool = False,
        strict: bool | None = None,
        uid: str | None = None,
        uids: list[str] | None = None,
        filter: Callable[[SampleType], bool] | None = None,
        **kwargs: Any,
    ) -> BatchOperationReport[Self]:
        """批量计算样本集内样本的组合反应谱。"""

        return self._batch_sample_method(
            "calc_respspec",
            overwrite=overwrite,
            strict=strict,
            uid=uid,
            uids=uids,
            filter=filter,
            **kwargs,
        )

    def batch(
        self,
        func: Callable[..., Any],
        *,
        uid: str | None = None,
        uids: list[str] | None = None,
        filter: Callable[[SampleType], bool] | None = None,
        strict: bool | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """对样本集中的每个样本执行批处理函数。"""

        items = self._select_samples(uid=uid, uids=uids, filter=filter)
        strict_mode = self.strict if strict is None else strict
        if not strict_mode:
            return run_callable_batch(items, func=func, strict=False, **kwargs)

        recoverable_io_error = self._recoverable_io_error()
        results: dict[str, Any] = {}
        for item_uid, sample in items:
            try:
                results[item_uid] = func(sample, **kwargs)
            except Exception as exc:
                raise recoverable_io_error(f"批处理失败: {item_uid}") from exc
        return results

    def to_structured_payload(self) -> StructuredPayload:
        """导出样本集 payload。"""

        return StructuredPayload(
            entity_type="sample_set",
            domain=self._payload_domain,
            category=self.__class__.__name__,
            data_vars={uid: sample.to_structured_payload().to_dict() for uid, sample in self.items()},
            attrs={
                "schema_name": self.sample_schema.name,
                "schema_version": self.sample_schema.version,
            },
            meta={
                "sample_type": self.sample_type.__name__,
                "count": len(self),
            },
        )

    @classmethod
    def from_structured_payload(
        cls,
        payload: StructuredPayload | dict[str, Any],
    ) -> SampleSetBase[SampleType]:
        """从样本集 payload 恢复对象。"""

        normalized = normalize_payload(payload)
        sample_cls = cast(type[SampleType], cls._sample_type)
        samples: dict[str, SampleType] = {}
        for uid, sample_payload in normalized.data_vars.items():
            if not isinstance(sample_payload, dict):
                continue
            sample = sample_cls.from_structured_payload(sample_payload)
            samples[str(uid)] = cast(SampleType, sample)
        return cls(samples)

    @classmethod
    def from_samples(
        cls,
        samples: dict[str, SampleBase] | list[SampleBase] | None,
        *,
        sample_domain: SampleDomain | None = None,
    ) -> SampleSetBase[SampleType]:
        """从样本对象集合构造样本集。"""

        from .factories import create_sample_set

        return cast(
            SampleSetBase[SampleType],
            create_sample_set(
                cls,
                sample_domain=sample_domain,
                samples=cast(dict[str, SampleBase] | list[SampleBase] | None, samples),
            ),
        )

    @classmethod
    def from_storage(
        cls,
        path: str | Path,
        *,
        sample_domain: SampleDomain | None = None,
        storage_scheme: Any | None = None,
        data_options: dict[str, Any] | None = None,
        categories: list[DataCategory | str] | None = None,
        load_mode: SampleLoadMode = SampleLoadMode.LAZY,
        strict: bool | None = None,
        filter: Callable[[SampleType], bool] | None = None,
        workers: int = 1,
        chunk_size: int = 256,
        set_filename: str | None = None,
    ) -> SampleSetBase[SampleType]:
        """从标准 storage 入口创建并加载样本集。"""

        instance = cls.from_samples(None, sample_domain=sample_domain)
        return cast(
            SampleSetBase[SampleType],
            instance.load(
                path,
                storage_scheme=storage_scheme,
                data_options=data_options,
                categories=categories,
                load_mode=load_mode,
                strict=strict,
                filter=filter,
                workers=workers,
                chunk_size=chunk_size,
                set_filename=set_filename,
            ),
        )


__all__ = ["SampleSetBase", "SampleType"]
