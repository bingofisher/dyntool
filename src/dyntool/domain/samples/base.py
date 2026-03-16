"""领域样本基础类。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, ClassVar, Mapping, Self, Union, cast, get_args, get_origin

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PrivateAttr,
    computed_field,
    model_validator,
)

from ..enums import SampleDomain
from ..metadata import MetadataBase, metadata_from_structured_payload
from ..models import DataModelBase, model_from_structured_payload
from ..runtime import resolve_sample_runtime
from ..serialization import StructuredPayload, normalize_payload
from .namespaces import SampleEvaluationNamespace, SampleProcessingNamespace
from .schema import SampleSchema


class SampleBase(BaseModel):
    """领域样本抽象基础类。"""

    alias: str = Field("", description="样本别名")
    metadata: MetadataBase = Field(..., description="样本元数据")
    data_vars: dict[str, DataModelBase] = Field(
        default_factory=dict,
        description="样本数据槽位",
    )

    _payload_domain: ClassVar[str] = "default"
    _sample_set_type: ClassVar[type | None] = None
    sample_schema: ClassVar[SampleSchema] = SampleSchema(name="sample")
    _storage_set: Any = PrivateAttr(default=None)

    model_config = ConfigDict(
        extra="forbid",
        arbitrary_types_allowed=True,
        validate_assignment=True,
        populate_by_name=True,
    )

    @computed_field
    @property
    def uid(self) -> str:
        """返回样本唯一标识。"""

        return self.metadata.uid

    @computed_field
    @property
    def schema_name(self) -> str:
        """返回样本 schema 名称。"""

        return self.sample_schema.name

    @computed_field
    @property
    def schema_version(self) -> int:
        """返回样本 schema 版本。"""

        return self.sample_schema.version

    @model_validator(mode="before")
    @classmethod
    def _prevent_direct_instantiation(cls, data: Any) -> Any:
        if cls is SampleBase:
            raise TypeError(f"{cls.__name__} 是抽象基础类，不能直接实例化")
        if isinstance(data, dict):
            payload = dict(data)
            raw_data_vars = payload.pop("data_vars", {}) or {}
            if not isinstance(raw_data_vars, dict):
                raise TypeError("data_vars 必须是 dict[str, DataModelBase]")
            for slot_name in cls.sample_schema.slot_names():
                if slot_name in payload:
                    raw_data_vars[slot_name] = payload.pop(slot_name)
            payload["data_vars"] = raw_data_vars
            return payload
        return data

    @model_validator(mode="after")
    def _normalize_sample(self) -> Self:
        if not self.alias or not self.alias.strip():
            object.__setattr__(self, "alias", self.uid)

        normalized: dict[str, DataModelBase] = {}
        for name, value in self.data_vars.items():
            if value is None:
                continue
            canonical = self.sample_schema.canonical_name(name)
            slot = self.sample_schema.slot(canonical)
            if not slot.supports(value):
                raise TypeError(
                    f"槽位 '{canonical}' 只接受 {slot.model_type.__name__}，实际得到 {type(value).__name__}"
                )
            normalized[canonical] = value
        object.__setattr__(self, "data_vars", normalized)

        for slot in self.sample_schema.slots:
            if slot.required and slot.name not in self.data_vars:
                raise ValueError(f"样本缺少必填槽位: {slot.name}")
        return self

    def __getattr__(self, name: str) -> Any:
        private_attributes = object.__getattribute__(self, "__private_attributes__")
        if name in private_attributes:
            attribute = private_attributes[name]
            if hasattr(attribute, "__get__"):
                return attribute.__get__(self, type(self))
            try:
                return self.__pydantic_private__[name]
            except KeyError as exc:
                raise AttributeError(f"{type(self).__name__!s} has no attribute {name!r}") from exc

        try:
            pydantic_extra = object.__getattribute__(self, "__pydantic_extra__")
        except AttributeError:
            pydantic_extra = None
        if pydantic_extra and name in pydantic_extra:
            return pydantic_extra[name]

        if self.sample_schema.has_slot(name):
            return self.get_data_var(name)
        raise AttributeError(f"{type(self).__name__!s} has no attribute {name!r}")

    def __setattr__(self, name: str, value: Any) -> None:
        if name.startswith("_"):
            super().__setattr__(name, value)
            return
        if name in type(self).model_fields:
            super().__setattr__(name, value)
            return
        if self.sample_schema.has_slot(name):
            self.set_data_var(name, value)
            return
        super().__setattr__(name, value)

    @classmethod
    def get_attr_types(cls, *attrs: str) -> dict[str, type]:
        """获取指定字段或槽位的类型注解。"""

        attr_types: dict[str, type] = {}
        if not attrs:
            attrs = ("alias", "metadata", *cls.sample_schema.slot_names())

        for attr in attrs:
            if attr in cls.model_fields:
                typ = cls.model_fields[attr].annotation
                origin = get_origin(typ)
                if origin is Union:
                    args = get_args(typ)
                    if len(args) == 2 and type(None) in args:
                        typ = next(item for item in args if item is not type(None))
                    else:
                        raise TypeError("仅支持 Optional[...] 类型字段")
                if not isinstance(typ, type):
                    raise TypeError(f"字段 '{attr}' 的类型注解无法解析为类: {typ}")
                attr_types[attr] = typ
                continue
            attr_types[attr] = cls.sample_schema.slot(attr).model_type
        return attr_types

    def get_data_var(self, name: str) -> DataModelBase | None:
        """按规范名或别名获取槽位值。"""

        canonical = self.sample_schema.canonical_name(name)
        return self.data_vars.get(canonical)

    def set_data_var(self, name: str, value: DataModelBase | None) -> None:
        """设置槽位值并执行 schema 校验。"""

        canonical = self.sample_schema.canonical_name(name)
        slot = self.sample_schema.slot(canonical)
        if value is None:
            self.data_vars.pop(canonical, None)
            return
        if not slot.supports(value):
            raise TypeError(f"槽位 '{canonical}' 只接受 {slot.model_type.__name__}，实际得到 {type(value).__name__}")
        self.data_vars[canonical] = value

    def update(self, **kwargs: Any) -> None:
        """安全更新样本字段与数据槽位。"""

        if "data_vars" in kwargs:
            raw_data_vars = kwargs.pop("data_vars")
            if not isinstance(raw_data_vars, dict):
                raise TypeError("data_vars 必须是 dict[str, DataModelBase]")
            for key, value in raw_data_vars.items():
                self.set_data_var(str(key), value)

        valid_keys = {"alias", "metadata", *self.sample_schema.slot_names()}
        for key, value in kwargs.items():
            if key not in valid_keys:
                raise KeyError(f"字段 '{key}' 不存在于样本中，无法更新。有效字段: {sorted(valid_keys)}")
            if key in {"alias", "metadata"}:
                setattr(self, key, value)
            else:
                self.set_data_var(key, value)

    @classmethod
    def sample_set_type(cls) -> type:
        """返回样本对应的样本集类型。"""

        if cls._sample_set_type is None:
            raise TypeError(f"{cls.__name__} 未配置 _sample_set_type")
        return cls._sample_set_type

    def set_metadata(self, metadata: MetadataBase) -> Self:
        """直接设置元数据对象。"""

        self.metadata = metadata
        if not self.alias or self.alias == self.uid:
            self.alias = metadata.uid
        return self

    def update_metadata(self, **kwargs: Any) -> Self:
        """原位更新当前元数据对象。"""

        self.metadata.update(**kwargs)
        return self

    def replace_metadata(self, metadata: MetadataBase) -> Self:
        """替换当前元数据对象。"""

        self.metadata = metadata
        return self

    def _resolve_metadata_path(self, path: str | None = None) -> Path:
        if path is not None:
            return Path(path)
        return Path(f"{self.uid}.json")

    def save_metadata(self, path: str | None = None) -> Self:
        """将元数据保存为 JSON。"""

        target = self._resolve_metadata_path(path)
        self.metadata.to_json(target)
        return self

    def load_metadata(self, path: str | None = None) -> Self:
        """从 JSON 重新加载元数据。"""

        target = self._resolve_metadata_path(path)
        self.metadata = self.metadata.__class__.from_json(target)
        return self

    def connect_storage(
        self,
        base_dir: str | Path,
        **kwargs: Any,
    ) -> Self:
        """连接样本存储。"""

        return cast(
            Self,
            resolve_sample_runtime(self, action="connect_storage").connect_sample_storage(
                self,
                str(base_dir),
                **kwargs,
            ),
        )

    def save(self, path: str | Path | None = None, **kwargs: Any) -> Self:
        """保存样本。"""

        return cast(
            Self,
            resolve_sample_runtime(self, action="save").save_sample(
                self,
                path=str(path) if path is not None else None,
                **kwargs,
            ),
        )

    def load(self, path: str | Path | None = None, **kwargs: Any) -> Self:
        """加载样本。"""

        return cast(
            Self,
            resolve_sample_runtime(self, action="load").load_sample(
                self,
                path=str(path) if path is not None else None,
                **kwargs,
            ),
        )

    def reload(self) -> Self:
        """从已连接存储重新加载样本。"""

        return cast(
            Self,
            resolve_sample_runtime(self, action="reload").reload_sample(self),
        )

    @property
    def processing(self) -> SampleProcessingNamespace:
        """返回样本处理命名空间。"""

        return SampleProcessingNamespace(self)

    @property
    def evaluation(self) -> SampleEvaluationNamespace:
        """返回样本评价命名空间。"""

        return SampleEvaluationNamespace(self)

    def flow(self) -> Any:
        """返回以当前样本为起点的计算流。"""

        from ...compute.flow import ComputeFlow

        return ComputeFlow(_result=self)

    def preprocess(self, **kwargs: Any) -> tuple[bool, str]:
        """执行预处理工作流。"""

        from .workflows import preprocess_sample

        return preprocess_sample(self, **kwargs)

    def evaluate(self, command: object, **kwargs: Any) -> tuple[bool, str]:
        """执行单样本评价命令。"""

        from .commands import VibEvalCommand
        from .workflows import evaluate_sample

        if not isinstance(command, VibEvalCommand):
            raise TypeError("command 必须是 VibEvalCommand 枚举")
        return evaluate_sample(self, command, **kwargs)

    def eval_zvl(self, **kwargs: Any) -> tuple[bool, str]:
        """执行 ZVL 评价。"""

        from .commands import VibEvalCommand

        return self.evaluate(VibEvalCommand.ZVL, **kwargs)

    def eval_otovl(self, **kwargs: Any) -> tuple[bool, str]:
        """执行 OTOVL 评价。"""

        from .commands import VibEvalCommand

        return self.evaluate(VibEvalCommand.OTOVL, **kwargs)

    def eval_fdmvl(self, **kwargs: Any) -> tuple[bool, str]:
        """执行 FDMVL 评价。"""

        from .commands import VibEvalCommand

        return self.evaluate(VibEvalCommand.FDMVL, **kwargs)

    def eval_fpvdv(self, **kwargs: Any) -> tuple[bool, str]:
        """执行 FPVDV 评价。"""

        from .commands import VibEvalCommand

        return self.evaluate(VibEvalCommand.FPVDV, **kwargs)

    def _iter_container_fields(
        self,
        *,
        include_storage_only: bool = False,
    ) -> dict[str, DataModelBase]:
        allowed_names = set(self.sample_schema.slot_names(include_storage_only=True)) if include_storage_only else None
        return {
            name: value
            for name, value in self.data_vars.items()
            if isinstance(value, DataModelBase) and (allowed_names is None or name in allowed_names)
        }

    def current_units(self) -> dict[str, dict[str, str]]:
        """返回样本内各数据槽位的当前单位。"""

        return {
            field_name: container.current_units() for field_name, container in self._iter_container_fields().items()
        }

    def convert_units(
        self,
        units: Mapping[str, Mapping[str, str | None]],
        *,
        replace: bool = True,
    ) -> Self:
        """按槽位批量转换样本内部数据单位。"""

        target = self if replace else self.model_copy(deep=True)
        for field_name, field_units in units.items():
            container = target.get_data_var(field_name)
            if container is None:
                continue
            if not isinstance(container, DataModelBase):
                raise TypeError(f"字段 '{field_name}' 不是数据模型，无法转换单位")
            target.set_data_var(
                field_name,
                container.convert_units(field_units, replace=replace),
            )
        if hasattr(target, "_refresh_freqspec") and any(name in units for name in ("freq_amp", "freq_pha")):
            target._refresh_freqspec()  # type: ignore[attr-defined]
        if hasattr(target, "_refresh_respspec") and any(
            name in units for name in ("respspec_sa", "respspec_sv", "respspec_sd", "respspec_psa", "respspec_psv")
        ):
            target._refresh_respspec()  # type: ignore[attr-defined]
        return target

    def to_structured_payload(self) -> StructuredPayload:
        """导出样本 payload。"""

        metadata_payload = self.metadata.to_structured_payload().to_dict()
        data_vars = {
            key: value.to_structured_payload().to_dict()
            for key, value in self._iter_container_fields(include_storage_only=True).items()
        }
        return StructuredPayload(
            entity_type="sample",
            domain=self._payload_domain,
            category=self.__class__.__name__,
            data_vars=data_vars,
            attrs={
                "alias": self.alias,
                "schema_name": self.schema_name,
                "schema_version": self.schema_version,
            },
            meta={"metadata": metadata_payload},
        )

    @classmethod
    def from_structured_payload(
        cls,
        payload: StructuredPayload | dict[str, Any],
    ) -> SampleBase:
        """从样本 payload 恢复对象。"""

        normalized = normalize_payload(payload)
        metadata_payload = normalized.meta.get("metadata")
        if not isinstance(metadata_payload, dict):
            raise ValueError("样本 payload 缺少 metadata 信息")

        metadata_obj = metadata_from_structured_payload(metadata_payload)
        alias = str(normalized.attrs.get("alias", ""))
        sample_data: dict[str, Any] = {"metadata": metadata_obj, "data_vars": {}}
        if alias:
            sample_data["alias"] = alias

        for field_name, field_payload in normalized.data_vars.items():
            if not isinstance(field_payload, dict):
                continue
            sample_data["data_vars"][field_name] = model_from_structured_payload(field_payload)
        return cls(**sample_data)

    @classmethod
    def from_models(
        cls,
        *,
        sample_domain: SampleDomain | None = None,
        metadata: MetadataBase | None = None,
        metadata_cls: type[MetadataBase] | None = None,
        alias: str = "",
        data_vars: dict[str, Any] | None = None,
        **models: Any,
    ) -> SampleBase:
        """根据模型对象构造样本。"""

        from .factories import create_sample

        merged_data_vars = dict(data_vars or {})
        merged_data_vars.update(models)
        return create_sample(
            cls,
            sample_domain=sample_domain,
            metadata=metadata,
            metadata_cls=metadata_cls,
            alias=alias,
            data_vars=merged_data_vars,
            metadata_kwargs={},
        )

    @classmethod
    def from_accel_data(
        cls,
        values: Any,
        *,
        dt: float | None = None,
        time: Any = None,
        axis_unit: str | None = None,
        data_unit: str | None = None,
        sample_domain: SampleDomain | None = None,
        metadata: MetadataBase | None = None,
        metadata_cls: type[MetadataBase] | None = None,
        alias: str = "",
        **metadata_kwargs: Any,
    ) -> SampleBase:
        """从加速度数据直接构造样本。"""

        from .factories import create_sample_from_accel

        return create_sample_from_accel(
            cls,
            values,
            dt=dt,
            time=time,
            axis_unit=axis_unit,
            data_unit=data_unit,
            sample_domain=sample_domain,
            metadata=metadata,
            metadata_cls=metadata_cls,
            alias=alias,
            metadata_kwargs=dict(metadata_kwargs),
        )


SampleBaseModel = SampleBase


__all__ = ["SampleBase", "SampleBaseModel"]
