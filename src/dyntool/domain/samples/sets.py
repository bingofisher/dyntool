"""领域样本集基础类。"""

from __future__ import annotations

from collections import UserDict
from pathlib import Path
from typing import Any, Callable, ClassVar, Generic, Mapping, Self, TypeVar, cast

import pandas as pd
from pydantic import ValidationError

from ...logging import get_logger
from ..constants import DataCategory
from ..enums import SampleDomain
from ..metadata import MetadataBase
from ..models import DataModelBase
from ..runtime import resolve_sample_set_runtime
from ..serialization import StructuredPayload, normalize_payload
from .base import SampleBase
from .batch import run_callable_batch, run_vibeval_batch, select_sample_items
from .commands import VibEvalCommand
from .namespaces import SampleSetEvaluationNamespace, SampleSetProcessingNamespace

SampleType = TypeVar("SampleType", bound=SampleBase)
logger = get_logger("samples")


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

        if samples:
            if isinstance(samples, list):
                self.update_from_list(samples)
            elif isinstance(samples, dict):
                self.update(samples)
            else:
                raise TypeError("samples 参数必须是字典或列表类型")

    def __setitem__(self, key: str, item: Any) -> None:
        normalized_key = key.strip()
        expected_type = self.sample_type
        if not isinstance(item, expected_type):
            raise TypeError(f"类型错误: {self.__class__.__name__} 仅接受 {expected_type.__name__} 类型")
        expected_key = item.uid.strip()
        if normalized_key != expected_key:
            normalized_key = expected_key
        super().__setitem__(normalized_key, item)

    def __getitem__(self, key: str) -> SampleType:
        return super().__getitem__(key.strip())

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}[{self.sample_type.__name__}] ({len(self)} samples)>"

    @property
    def sample_type(self) -> type[SampleType]:
        """返回样本集管理的样本类型。"""

        return cast(type[SampleType], self._sample_type)

    @property
    def sample_schema(self):
        """返回样本 schema。"""

        return self.sample_type.sample_schema

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

    def update_data(self, uid: str, data: DataModelBase) -> None:
        """更新指定样本的特定类别数据。"""

        if uid not in self:
            raise KeyError(f"样本 '{uid}' 不存在于样本集中")
        slot_name = self._resolve_slot_name(data.category)
        self[uid].set_data_var(slot_name, data)

    def get_metadata(self, **metadata_criteria: Any) -> list[MetadataBase]:
        """根据元数据条件筛选样本元数据。"""

        return [sample.metadata for sample in self.values() if sample.metadata.match(**metadata_criteria)]

    def get_uids(self, **metadata_criteria: Any) -> list[str]:
        """根据元数据条件获取匹配样本 UID 列表。"""

        return [meta.uid for meta in self.get_metadata(**metadata_criteria)]

    def get_uid_by_metadata(self, metadata: MetadataBase) -> str:
        """根据元数据对象获取对应样本 UID。"""

        for uid, sample in self.items():
            if sample.metadata.uid == metadata.uid:
                return uid
        raise KeyError("未找到匹配的样本 UID")

    def get_metadatadf(self, flatten_sep: str = "@") -> pd.DataFrame:
        """将样本元数据转换为扁平化 DataFrame。"""

        metadata_list = [meta.to_flatten_dict(sep=flatten_sep) for meta in self.get_metadata()]
        return pd.DataFrame(metadata_list)

    def _resolve_slot_name(self, category: str | DataCategory) -> str:
        raw_name = DataCategory.to_sample_attr_name(category) if isinstance(category, DataCategory) else str(category)
        return self.sample_schema.slot(raw_name).name

    def get_data(self, uid: str, category: str | DataCategory) -> DataModelBase | None:
        """获取指定样本的特定类别数据。"""

        if uid not in self:
            raise KeyError(f"样本 '{uid}' 不存在于样本集中")
        return self[uid].get_data_var(self._resolve_slot_name(category))

    def get_data_dict(self, category: str | DataCategory) -> dict[str, DataModelBase]:
        """获取指定类别的所有样本数据字典。"""

        slot_name = self._resolve_slot_name(category)
        data_dict: dict[str, DataModelBase] = {}
        for uid, sample in self.items():
            data = sample.get_data_var(slot_name)
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
        """返回符合谓词条件的新样本集。"""

        return self.__class__(dict(self._filtered_items(filter=filter)))

    def get_sample(
        self,
        filter: Callable[[SampleType], bool] | None = None,
    ) -> SampleType | None:
        """返回唯一匹配的样本。"""

        matched_sample: SampleType | None = None
        for _, sample in self._filtered_items(filter=filter):
            if matched_sample is not None:
                raise ValueError("expected exactly one matched sample")
            matched_sample = sample
        return matched_sample

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
        **kwargs: Any,
    ) -> Self:
        """连接样本集存储。"""

        return cast(
            Self,
            resolve_sample_set_runtime(self, action="connect_storage").connect_sample_set_storage(
                self,
                str(base_dir),
                **kwargs,
            ),
        )

    def save(
        self,
        path: str | Path | None = None,
        *,
        mode: object | None = None,
        storage_scheme: object | None = None,
        data_options: dict[str, Any] | None = None,
        categories: list[str] | None = None,
        strict: bool = True,
        filter: Callable[[SampleType], bool] | None = None,
        workers: int = 1,
        chunk_size: int = 256,
        name_resolver: object | None = None,
        set_filename: str | None = None,
    ) -> Self:
        """保存当前样本集。"""

        return cast(
            Self,
            resolve_sample_set_runtime(self, action="save").save_sample_set(
                self,
                path=str(path) if path is not None else None,
                mode=mode,
                storage_scheme=storage_scheme,
                data_options=data_options,
                categories=categories,
                strict=strict,
                filter=filter,
                workers=workers,
                chunk_size=chunk_size,
                name_resolver=name_resolver,
                set_filename=set_filename,
            ),
        )

    def load(
        self,
        path: str | Path | None = None,
        *,
        mode: object | None = None,
        storage_scheme: object | None = None,
        data_options: dict[str, Any] | None = None,
        categories: list[str] | None = None,
        strict: bool | None = None,
        filter: Callable[[SampleType], bool] | None = None,
        workers: int = 1,
        chunk_size: int = 256,
        set_filename: str | None = None,
    ) -> Self:
        """加载样本集内容。"""

        return cast(
            Self,
            resolve_sample_set_runtime(self, action="load").load_sample_set(
                self,
                path=str(path) if path is not None else None,
                mode=mode,
                storage_scheme=storage_scheme,
                data_options=data_options,
                categories=categories,
                strict=strict,
                filter=filter,
                workers=workers,
                chunk_size=chunk_size,
                set_filename=set_filename,
            ),
        )

    def save_all(
        self,
        *,
        categories: list[str] | None = None,
        strict: bool = True,
        filter: Callable[[SampleType], bool] | None = None,
        workers: int = 1,
        chunk_size: int = 256,
    ) -> dict[str, Exception]:
        """批量保存当前样本集中的样本。"""

        return resolve_sample_set_runtime(
            self,
            action="save_all",
        ).save_all_samples(
            self,
            categories=categories,
            strict=strict,
            filter=filter,
            workers=workers,
            chunk_size=chunk_size,
        )

    def load_all(
        self,
        *,
        progress_callback: Callable[[int, int], None] | None = None,
        categories: list[str] | None = None,
        strict: bool | None = None,
        filter: Callable[[SampleType], bool] | None = None,
        workers: int = 1,
        chunk_size: int = 256,
    ) -> dict[str, Exception]:
        """批量加载样本集中的样本。"""

        return resolve_sample_set_runtime(
            self,
            action="load_all",
        ).load_all_samples(
            self,
            progress_callback=progress_callback,
            categories=categories,
            strict=strict,
            filter=filter,
            workers=workers,
            chunk_size=chunk_size,
        )

    def organize_storage(self) -> Self:
        """整理样本集存储。"""

        return cast(
            Self,
            resolve_sample_set_runtime(
                self,
                action="organize_storage",
            ).organize_sample_set_storage(self),
        )

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
        """用 metadata CSV 替换当前样本集。"""

        imported = self.__class__.build_from_metadatadf(pd.read_csv(path))
        self.clear()
        self.update(imported)
        return self

    @property
    def processing(self) -> SampleSetProcessingNamespace:
        """返回样本集处理命名空间。"""

        return SampleSetProcessingNamespace(self)

    @property
    def evaluation(self) -> SampleSetEvaluationNamespace:
        """返回样本集评价命名空间。"""

        return SampleSetEvaluationNamespace(self)

    def preprocess(self, **kwargs: Any) -> Any:
        """执行样本集预处理工作流。"""

        from .workflows import preprocess_sample_set

        return preprocess_sample_set(self, **kwargs)

    def evaluate(self, command: VibEvalCommand, **kwargs: Any) -> Any:
        """执行样本集评价命令。"""

        from .workflows import evaluate_sample_set

        return evaluate_sample_set(self, command, **kwargs)

    def eval_zvl(self, **kwargs: Any) -> Any:
        """执行 ZVL 批量评价。"""

        return self.evaluate(VibEvalCommand.ZVL, **kwargs)

    def eval_otovl(self, **kwargs: Any) -> Any:
        """执行 OTOVL 批量评价。"""

        return self.evaluate(VibEvalCommand.OTOVL, **kwargs)

    def eval_fdmvl(self, **kwargs: Any) -> Any:
        """执行 FDMVL 批量评价。"""

        return self.evaluate(VibEvalCommand.FDMVL, **kwargs)

    def eval_fpvdv(self, **kwargs: Any) -> Any:
        """执行 FPVDV 批量评价。"""

        return self.evaluate(VibEvalCommand.FPVDV, **kwargs)

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
        module = __import__(
            "dyntool.infrastructure.persistence",
            fromlist=["RecoverableIOError"],
        )
        return module.RecoverableIOError

    def _batch_vibeval(
        self,
        command: VibEvalCommand,
        overwrite: bool = False,
        uid: str | None = None,
        uids: list[str] | None = None,
        filter: Callable[[SampleType], bool] | None = None,
        **kwargs: object,
    ) -> dict[str, tuple[bool, str]] | tuple[bool, str]:
        """批量振动评价通用实现。"""

        items = self._select_samples(uid=uid, uids=uids, filter=filter)
        results, stats = run_vibeval_batch(
            items,
            command=command,
            overwrite=overwrite,
            **kwargs,
        )
        logger.info(
            f"{command.label} 计算完成 (overwrite={overwrite}): "
            f"总有效样本 {stats.valid_samples}, 处理 {stats.processed}, "
            f"跳过 {stats.skipped}, 失败 {stats.failed}"
        )
        if uid is not None:
            return results[uid]
        return results

    def batch(
        self,
        func: Callable[..., Any],
        *,
        uid: str | None = None,
        uids: list[str] | None = None,
        filter: Callable[[SampleType], bool] | None = None,
        strict: bool = True,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """对样本集中的每个样本执行批处理函数。"""

        items = self._select_samples(uid=uid, uids=uids, filter=filter)
        if not strict:
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
        storage_scheme: object | None = None,
        data_options: dict[str, Any] | None = None,
        categories: list[str] | None = None,
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
                strict=strict,
                filter=filter,
                workers=workers,
                chunk_size=chunk_size,
                set_filename=set_filename,
            ),
        )


__all__ = ["SampleSetBase", "SampleType"]
