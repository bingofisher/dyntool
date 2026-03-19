"""领域样本基础类。"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, Iterable, Mapping, Self, Union, cast, get_args, get_origin

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PrivateAttr,
    computed_field,
    model_validator,
)

from ..constants import DataCategory
from ..enums import SampleDomain
from ..metadata import MetadataBase, metadata_from_structured_payload
from ..models import DataModelBase, model_from_structured_payload
from ..runtime import resolve_sample_runtime
from ..serialization import StructuredPayload, normalize_payload
from .batch import OperationResult
from .namespaces import SampleEvaluationNamespace, SampleProcessingNamespace
from .schema import SampleSchema
from .types import SampleField, SampleLoadMode

if TYPE_CHECKING:
    from .commands import VibEvalCommand


class SampleBase(BaseModel):
    """领域样本抽象基础类。"""

    alias: str = Field("", description="样本别名")
    metadata: MetadataBase = Field(..., description="样本元数据")
    strict: bool = Field(default=True, exclude=True, description="严格模式默认值")
    data_vars: dict[SampleField, DataModelBase] = Field(
        default_factory=dict,
        description="样本数据槽位",
    )

    _payload_domain: ClassVar[str] = "default"
    _sample_set_type: ClassVar[type | None] = None
    sample_schema: ClassVar[SampleSchema] = SampleSchema(name="sample")
    _storage_set: Any = PrivateAttr(default=None)
    _alias_overridden: bool = PrivateAttr(default=False)
    _loaded_categories: set[SampleField] = PrivateAttr(default_factory=set)
    _dirty_categories: set[SampleField] = PrivateAttr(default_factory=set)
    _load_mode: SampleLoadMode = PrivateAttr(default=SampleLoadMode.EAGER)
    _originated_from_storage: bool = PrivateAttr(default=False)

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
            for property_name in cls.sample_schema.property_names():
                if property_name in payload:
                    raw_data_vars[property_name] = payload.pop(property_name)
            payload["data_vars"] = raw_data_vars
            return payload
        return data

    @model_validator(mode="after")
    def _normalize_sample(self) -> Self:
        normalized: dict[SampleField, DataModelBase] = {}
        for name, value in self.data_vars.items():
            if value is None:
                continue
            field = self._resolve_field(str(name))
            spec = self.sample_schema.field_spec(field)
            if not spec.supports(value):
                raise TypeError(
                    f"数据项 '{spec.property_name}' 只接受 {spec.model_type.__name__}，实际得到 {type(value).__name__}"
                )
            normalized[field] = value
        object.__setattr__(self, "data_vars", normalized)

        for spec in self.sample_schema.slots:
            if spec.required and spec.field not in self.data_vars:
                raise ValueError(f"样本缺少必填数据项: {spec.property_name}")

        object.__setattr__(self, "_loaded_categories", set(self.data_vars))
        object.__setattr__(self, "_dirty_categories", set())
        object.__setattr__(self, "_load_mode", SampleLoadMode.EAGER)
        self._bind_metadata(self.metadata)
        if not self.alias or not self.alias.strip():
            self._set_alias_internal(self._default_alias_for_metadata(), mark_override=False)
        else:
            resolved_alias = self.alias.strip()
            mark_override = resolved_alias != self._default_alias_for_metadata()
            self._set_alias_internal(resolved_alias, mark_override=mark_override)
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
        if name == "metadata":
            raise AttributeError("禁止直接写入 metadata，请改用 replace_metadata() 或 update_metadata()")
        if name == "alias":
            raise AttributeError("禁止直接写入 alias，请改用 set_alias()、clear_alias_override() 或 refresh_alias()")
        if self.sample_schema.has_slot(name):
            raise AttributeError(f"禁止直接写入样本槽位 '{name}'，请改用 update_data() 或 update()")
        if name in type(self).model_fields:
            super().__setattr__(name, value)
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

    @classmethod
    def supported_categories(cls) -> tuple[DataCategory, ...]:
        """返回当前样本类型支持的公开 DataCategory 子集。"""

        return cls.sample_schema.supported_categories()

    @classmethod
    def storable_categories(cls) -> tuple[DataCategory, ...]:
        """返回当前样本类型允许进入存储流程的 DataCategory 子集。"""

        return cls.sample_schema.storable_categories()

    @classmethod
    def supported_fields(cls) -> tuple[SampleField, ...]:
        """返回当前样本类型声明的内部 SampleField 列表。"""

        return cls.sample_schema.field_names()

    @classmethod
    def storable_fields(cls) -> tuple[SampleField, ...]:
        """返回当前样本类型可持久化读写的 SampleField 列表。"""

        return cls.sample_schema.field_names(include_storage_only=True)

    def available_categories(self) -> tuple[DataCategory, ...]:
        """返回当前样本已加载或可从已绑定 storage 读取的公开 DataCategory。"""

        categories = {self.sample_schema.category(field) for field in self._loaded_categories}
        if self._storage_set is not None and self._storage_set.storage is not None:
            categories.update(self.storable_categories())
        return tuple(sorted(categories, key=str))

    def _resolve_field(self, selector: SampleField | DataCategory | str) -> SampleField:
        """把公开选择器解析为内部 SampleField。"""

        return self.sample_schema.resolve_field(selector)

    def _resolve_property_name(self, selector: SampleField | DataCategory | str) -> str:
        """返回选择器对应的样本属性访问名。"""

        return self.sample_schema.property_name(selector)

    def _normalize_public_categories(
        self,
        categories: Iterable[SampleField | DataCategory | str] | None = None,
    ) -> list[SampleField] | None:
        """将公开 categories 统一解析为去重后的 SampleField 列表。"""

        if categories is None:
            return None
        resolved: list[SampleField] = []
        for raw_category in categories:
            field = self._resolve_field(raw_category)
            if field not in resolved:
                resolved.append(field)
        return resolved or None

    def _default_alias_for_metadata(self, metadata: MetadataBase | None = None) -> str:
        """根据元数据计算默认 alias。"""

        target = metadata or self.metadata
        metadata_alias = getattr(target, "alias", None)
        if isinstance(metadata_alias, str) and metadata_alias.strip():
            return metadata_alias.strip()
        return target.uid

    def _set_alias_internal(self, alias: str, *, mark_override: bool) -> None:
        """内部设置 alias，并按需维护覆盖标记。"""

        object.__setattr__(self, "alias", alias.strip())
        object.__setattr__(self, "_alias_overridden", mark_override)

    def _restore_alias_internal(self, alias: str | None) -> None:
        """按持久化结果恢复 alias，并推导是否属于手工覆盖。"""

        resolved = str(alias or "").strip()
        if not resolved:
            self._set_alias_internal(self._default_alias_for_metadata(), mark_override=False)
            return
        self._set_alias_internal(
            resolved,
            mark_override=resolved != self._default_alias_for_metadata(),
        )

    def _replace_data_vars_internal(self, data_vars: dict[SampleField, DataModelBase]) -> None:
        """内部替换整个数据槽映射，并同步加载/脏状态。"""

        normalized: dict[SampleField, DataModelBase] = {}
        for name, value in data_vars.items():
            field = self._resolve_field(str(name))
            spec = self.sample_schema.field_spec(field)
            if not spec.supports(value):
                raise TypeError(
                    f"数据项 '{spec.property_name}' 只接受 {spec.model_type.__name__}，实际得到 {type(value).__name__}"
                )
            normalized[field] = value
        object.__setattr__(self, "data_vars", normalized)
        object.__setattr__(self, "_loaded_categories", set(normalized))
        object.__setattr__(self, "_dirty_categories", set())

    def _bind_metadata(self, metadata: MetadataBase) -> None:
        """绑定元数据变更回调。"""

        metadata.bind_change_callback(self._on_metadata_changed)

    def _sync_alias_after_metadata_change(
        self,
        *,
        old_uid: str | None,
        old_metadata_alias: str | None,
        force: bool = False,
    ) -> None:
        current_alias = self.alias.strip()
        if force or not self._alias_overridden:
            self._set_alias_internal(self._default_alias_for_metadata(), mark_override=False)
            return
        if (
            not current_alias
            or current_alias == old_uid
            or (old_metadata_alias is not None and current_alias == old_metadata_alias)
        ):
            self._set_alias_internal(self._default_alias_for_metadata(), mark_override=False)

    def _sync_identity_state(
        self,
        old_uid: str | None,
        old_metadata_alias: str | None,
        *,
        force_alias: bool = False,
    ) -> None:
        """统一同步 metadata 变更后的 uid 与 alias 状态。"""

        self._sync_alias_after_metadata_change(
            old_uid=old_uid,
            old_metadata_alias=old_metadata_alias,
            force=force_alias,
        )

    def _replace_metadata(self, metadata: MetadataBase) -> None:
        """替换元数据对象，并触发必要的样本集重索引。"""

        if not isinstance(metadata, MetadataBase):
            raise TypeError("metadata 必须是 MetadataBase 实例")
        old_metadata = getattr(self, "metadata", None)
        old_uid = old_metadata.uid if isinstance(old_metadata, MetadataBase) else None
        old_metadata_alias = getattr(old_metadata, "alias", None) if isinstance(old_metadata, MetadataBase) else None
        if isinstance(old_metadata, MetadataBase):
            old_metadata.bind_change_callback(None)
        super().__setattr__("metadata", metadata)
        self._bind_metadata(metadata)
        self._sync_identity_state(old_uid=old_uid, old_metadata_alias=old_metadata_alias)
        if self._storage_set is not None and old_uid is not None:
            self._storage_set._on_sample_metadata_changed(self, old_uid)

    def _on_metadata_changed(
        self,
        metadata: MetadataBase,
        old_uid: str,
        old_metadata_alias: str | None,
    ) -> None:
        """响应元数据对象内部字段变化。"""

        self._sync_identity_state(old_uid=old_uid, old_metadata_alias=old_metadata_alias)
        if self._storage_set is not None:
            self._storage_set._on_sample_metadata_changed(self, old_uid)

    def get_data_var(self, name: SampleField | DataCategory | str) -> DataModelBase | None:
        """按内部字段、公开分类或属性别名读取样本数据项。"""

        field = self._resolve_field(name)
        if field not in self.data_vars:
            spec = self.sample_schema.field_spec(field)
            if self._storage_set is not None and self._storage_set.storage is not None and spec.include_in_storage:
                if self._load_mode is SampleLoadMode.LAZY:
                    self.ensure_loaded(categories=[self.sample_schema.category(field)])
                elif self._load_mode is SampleLoadMode.METADATA_ONLY:
                    raise RuntimeError(
                        f"当前样本处于 metadata-only 模式，数据项 '{spec.property_name}' 尚未加载，请先调用 ensure_loaded()。"
                    )
        return self.data_vars.get(field)

    def is_loaded(self, name: SampleField | DataCategory | str) -> bool:
        """判断指定数据项当前是否已经加载到内存。"""

        field = self._resolve_field(name)
        return field in self._loaded_categories and field in self.data_vars

    @property
    def loaded_categories(self) -> tuple[DataCategory, ...]:
        """返回当前已加载数据项对应的公开 DataCategory 元组。"""

        return tuple(self.sample_schema.category(field) for field in sorted(self._loaded_categories, key=str))

    @property
    def load_mode(self) -> SampleLoadMode:
        """返回当前样本的数据加载模式。"""

        return self._load_mode

    def _set_load_mode_internal(self, load_mode: SampleLoadMode) -> None:
        """内部设置当前样本的加载模式。"""

        object.__setattr__(self, "_load_mode", load_mode)

    def ensure_loaded(
        self,
        *,
        categories: Iterable[SampleField | DataCategory | str] | None = None,
    ) -> Self:
        """显式加载当前样本尚未加载的数据项。"""

        if self._storage_set is None or self._storage_set.storage is None:
            return self
        selected_fields = self._normalize_public_categories(categories)
        loaded = self._storage_set.storage.load_sample(self.uid, selected_fields)
        loaded._originated_from_storage = True
        for category in loaded.loaded_categories:
            self._replace_data_var_internal(category, loaded.get_data_var(category))
        if self._load_mode is SampleLoadMode.METADATA_ONLY:
            self._set_load_mode_internal(SampleLoadMode.LAZY)
        return self

    def unload(
        self,
        *,
        categories: Iterable[SampleField | DataCategory | str] | None = None,
    ) -> Self:
        """从内存中卸载指定数据项，但不删除持久化内容。"""

        selected_fields = self._normalize_public_categories(categories)
        targets = selected_fields or list(self.data_vars.keys())
        for field in targets:
            self.data_vars.pop(field, None)
            self._loaded_categories.discard(field)
        return self

    def set_data_var(self, name: SampleField | DataCategory | str, value: DataModelBase | None) -> None:
        """设置单个样本数据项并同步加载/脏状态。"""

        field = self._resolve_field(name)
        spec = self.sample_schema.field_spec(field)
        if value is None:
            self.data_vars.pop(field, None)
            self._loaded_categories.discard(field)
            self._dirty_categories.add(field)
            return
        if not spec.supports(value):
            raise TypeError(
                f"数据项 '{spec.property_name}' 只接受 {spec.model_type.__name__}，实际得到 {type(value).__name__}"
            )
        self.data_vars[field] = value
        self._loaded_categories.add(field)
        self._dirty_categories.add(field)
        if self._storage_set is not None:
            self._storage_set.storage_dirty = True

    def _replace_data_var_internal(self, name: SampleField | DataCategory | str, value: DataModelBase | None) -> None:
        """内部替换单个数据项，不触发外部写路径副作用。"""

        field = self._resolve_field(name)
        if value is None:
            self.data_vars.pop(field, None)
            self._loaded_categories.discard(field)
            return
        spec = self.sample_schema.field_spec(field)
        if not spec.supports(value):
            raise TypeError(
                f"数据项 '{spec.property_name}' 只接受 {spec.model_type.__name__}，实际得到 {type(value).__name__}"
            )
        self.data_vars[field] = value
        self._loaded_categories.add(field)

    def update_data(self, strict: bool | None = None, **data_patch: DataModelBase | None) -> Self:
        """按槽位名更新样本数据。

        Args:
            strict: 是否按严格模式校验槽位名。`None` 表示继承当前样本的 `strict`
                设置；`True` 时遇到未知槽位立即报错；`False` 时忽略未知槽位。
            **data_patch: 以样本 schema 顶层槽位名为键的数据补丁。支持键为当前样本
                schema 声明的槽位名，例如 `accel`、`vel`、`disp`、`freqspec`、
                `respspec` 以及各类评价结果槽位。值为 `DataModelBase` 实例或 `None`。

        Returns:
            当前样本对象本身。

        Raises:
            KeyError: 严格模式下传入未知槽位名。
            TypeError: 槽位值与 schema 期望的数据模型类型不匹配。

        Notes:
            该方法会更新已加载槽位状态与脏槽位状态；如果样本已挂接到 `SampleSet`，
            还会同步标记 `storage_dirty=True`。
        """

        strict_mode = self.strict if strict is None else strict
        valid_slots = set(self.sample_schema.property_names())
        for name, value in data_patch.items():
            if name not in valid_slots:
                if strict_mode:
                    raise KeyError(f"未知样本槽位: {name}")
                continue
            self.set_data_var(name, value)
        return self

    def update(self, *, strict: bool | None = None, **kwargs: Any) -> None:
        """统一更新样本 alias、metadata 与数据槽位。

        Args:
            strict: 是否按严格模式校验字段名。`None` 表示继承当前样本的 `strict`
                设置；`True` 时遇到未知字段立即报错；`False` 时忽略未知字段。
            **kwargs: 支持键为 `alias`、`metadata`、`data_vars` 以及当前样本 schema
                声明的顶层槽位名。`alias` 用于显式覆盖样本别名；`metadata` 用于替换整
                个元数据对象；`data_vars` 用于批量传入槽位字典；其余槽位键会交给
                `set_data_var()` 逐项更新。

        Raises:
            KeyError: 严格模式下传入未知字段。
            TypeError: `metadata` 不是 `MetadataBase` 实例，或 `data_vars` 不是字典。

        Notes:
            `metadata` 变化会触发 `uid` 重算，并可能联动 `alias`、样本集索引与
            `storage_dirty`。手工传入 `alias` 会把当前样本标记为“手工 alias 覆盖”。
        """

        strict_mode = self.strict if strict is None else strict
        if "data_vars" in kwargs:
            raw_data_vars = kwargs.pop("data_vars")
            if not isinstance(raw_data_vars, dict):
                raise TypeError("data_vars 必须是 dict[str, DataModelBase]")
            for key, value in raw_data_vars.items():
                self.set_data_var(str(key), value)

        valid_keys = {"alias", "metadata", *self.sample_schema.slot_names()}
        for key, value in kwargs.items():
            if key not in valid_keys:
                if not strict_mode:
                    continue
                raise KeyError(f"字段 '{key}' 不存在于样本中，无法更新。有效字段: {sorted(valid_keys)}")
            if key == "alias":
                if value is None:
                    self.clear_alias_override()
                else:
                    self.set_alias(str(value))
            elif key == "metadata":
                if not isinstance(value, MetadataBase):
                    raise TypeError("metadata 必须是 MetadataBase 实例")
                self._replace_metadata(value)
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

        self._replace_metadata(metadata)
        return self

    def update_metadata(self, **kwargs: Any) -> Self:
        """原位更新当前元数据对象。

        Args:
            **kwargs: 支持键为当前 metadata 类型声明的字段名。例如
                `VibrationTestMetadata` 支持 `case`、`point`、`instr`、`dir`、
                `record`、`timestamp`、`extra`；通用 `Metadata` 支持 `identity`、
                `attributes`、`extra`。

        Returns:
            当前样本对象本身。

        Raises:
            ValidationError: metadata 字段校验失败。
            TypeError: 字段类型不符合 metadata 模型约束。

        Notes:
            metadata 变更会触发 `uid` 重算；若当前样本 alias 未手工覆盖，则也会同步
            到最新 `metadata.alias`。样本已挂接到 `SampleSet` 时会进一步触发重索引
            与 `storage_dirty` 标记。
        """

        self.metadata.update(**kwargs)
        return self

    def replace_metadata(self, metadata: MetadataBase) -> Self:
        """替换当前元数据对象。"""

        self._replace_metadata(metadata)
        return self

    def set_alias(self, alias: str) -> Self:
        """显式设置样本 alias，并标记为手工覆盖。"""

        resolved = str(alias).strip()
        if not resolved:
            raise ValueError("alias 不能为空")
        self._set_alias_internal(resolved, mark_override=True)
        if self._storage_set is not None:
            self._storage_set.storage_dirty = True
        return self

    def clear_alias_override(self) -> Self:
        """清除手工 alias 覆盖并恢复自动 alias。"""

        self._set_alias_internal(self._default_alias_for_metadata(), mark_override=False)
        if self._storage_set is not None:
            self._storage_set.storage_dirty = True
        return self

    def refresh_alias(self, *, force: bool = False) -> Self:
        """刷新当前样本 alias。

        Args:
            force: 是否强制覆盖手工 alias。`False` 时仅刷新自动 alias；
                `True` 时即使当前 alias 由 `set_alias()` 手工设置，也会强制回到
                `metadata.alias` 自动链。

        Returns:
            当前样本对象本身。

        Notes:
            该方法会在样本已挂接到 `SampleSet` 时标记 `storage_dirty=True`，但不会
            自动写回存储；落盘仍需显式调用 `save()` 或 `save_all()`。
        """

        self._sync_alias_after_metadata_change(
            old_uid=self.uid,
            old_metadata_alias=self._default_alias_for_metadata(),
            force=force,
        )
        if self._storage_set is not None:
            self._storage_set.storage_dirty = True
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
        self._replace_metadata(self.metadata.__class__.from_json(target))
        return self

    def connect_storage(
        self,
        base_dir: str | Path,
        *,
        strict: bool | None = None,
        **kwargs: Any,
    ) -> Self:
        """为当前样本绑定存储上下文。

        Args:
            base_dir: 样本存储根目录、单样本文件路径或容器目录。
            strict: 是否覆盖当前样本与所属 `SampleSet` 的严格模式。`None` 表示保留
                现有设置。
            **kwargs: 支持键包括 `mode`、`storage_scheme`、`data_options`、
                `name_resolver`、`set_filename`。`mode` 控制创建或打开行为；
                `storage_scheme` 指定 `SAMPLE_JSON`、`SAMPLE_H5`、`SAMPLE_DIR`
                等方案；`data_options` 用于传递底层存储配置；`name_resolver` 用于
                自定义文件名解析；`set_filename` 用于 `SET_H5` 容器场景的集合文件名。

        Returns:
            已绑定存储上下文的当前样本对象。

        Raises:
            RuntimeBindingError: 当前 sample runtime 未绑定。
            TypeError: `mode` 或 `storage_scheme` 不是合法枚举值。

        Notes:
            本方法只建立后续 `save()` / `load()` / 懒加载所需的上下文，不会立即落盘。
        """

        result = cast(
            Self,
            resolve_sample_runtime(self, action="connect_storage").connect_sample_storage(
                self,
                str(base_dir),
                **kwargs,
            ),
        )
        if strict is not None:
            result.strict = strict
            if result._storage_set is not None:
                result._storage_set.strict = strict
        return result

    def save(self, path: str | Path | None = None, *, strict: bool | None = None, **kwargs: Any) -> Self:
        """显式保存当前样本。

        Args:
            path: 可选的显式目标路径；为 `None` 时要求当前样本已连接有效存储上下文。
            strict: 是否覆盖当前样本与所属 `SampleSet` 的严格模式。`None` 表示保留
                现有设置。
            **kwargs: 支持键包括 `mode`、`storage_scheme`、`data_options`、
                `name_resolver`、`set_filename`、`categories`。其中 `categories`
                用于选择要写回的顶层槽位名；其余键与 `connect_storage()` 语义一致。

        Returns:
            当前样本对象本身。

        Raises:
            RuntimeError: 未提供 `path` 且当前样本尚未连接存储。

        Notes:
            该方法会把当前 alias、metadata 与已加载槽位写回存储，但不会清理旧 UID
            残留；旧条目清理由 `SampleSet.organize_storage()` 负责。
        """

        result = cast(
            Self,
            resolve_sample_runtime(self, action="save").save_sample(
                self,
                path=str(path) if path is not None else None,
                **kwargs,
            ),
        )
        if strict is not None:
            result.strict = strict
            if result._storage_set is not None:
                result._storage_set.strict = strict
        return result

    def load(self, path: str | Path | None = None, *, strict: bool | None = None, **kwargs: Any) -> Self:
        """显式加载当前样本。

        Args:
            path: 可选的显式来源路径；为 `None` 时从已连接存储上下文读取。
            strict: 是否覆盖当前样本与所属 `SampleSet` 的严格模式。`None` 表示保留
                现有设置。
            **kwargs: 支持键包括 `mode`、`storage_scheme`、`data_options`、
                `name_resolver`、`set_filename`、`categories`。`categories` 用于
                指定要恢复的顶层槽位名；其余键与 `connect_storage()` 语义一致。

        Returns:
            当前样本对象本身。

        Raises:
            RuntimeError: 未提供 `path` 且当前样本尚未连接存储。

        Notes:
            该方法会同步恢复 metadata、alias 和槽位数据；metadata 变更产生的 `uid`
            结果会继续通过样本聚合边界维护。
        """

        result = cast(
            Self,
            resolve_sample_runtime(self, action="load").load_sample(
                self,
                path=str(path) if path is not None else None,
                **kwargs,
            ),
        )
        if strict is not None:
            result.strict = strict
            if result._storage_set is not None:
                result._storage_set.strict = strict
        return result

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

    def preprocess(self, *, strict: bool | None = None, **kwargs: Any) -> OperationResult[Self]:
        """执行加速度预处理工作流。

        Args:
            strict: 是否覆盖当前样本的严格模式。`None` 表示保留现有设置。
            **kwargs: 支持键包括 `truncate_range`、`baseline`、`baseline_order`、
                `highpass`、`lowpass`、`bandpass`、`filter_order`。这些键分别对应
                截断时间窗、基线校正方法、基线校正阶数、高通截止频率、低通截止频率、
                带通频率范围以及滤波器阶数。

        Returns:
            `OperationResult[Self]`，其 `value` 为当前样本对象。

        Notes:
            预处理只修改 `accel` 槽位，不会自动写回存储。若当前样本无 `accel`，
            会返回失败结果而不是静默跳过。
        """

        from .workflows import preprocess_sample

        if strict is not None:
            self.strict = strict
        return cast(OperationResult[Self], preprocess_sample(self, **kwargs))

    def evaluate(self, command: "VibEvalCommand", **options: Any) -> OperationResult[Self]:
        """执行单样本振动评价命令。

        Args:
            command: 要执行的 `VibEvalCommand` 枚举值。
            **options: 支持键取决于评价命令。当前正式支持键包括 `overwrite`，
                以及由 `AccelSeries.eval_*()` 支持的评价参数：
                `freq_range`、`weight_type`、`time_windows`、`nsup`、
                `calc_unit_system`、`output_unit_system`。

        Returns:
            `OperationResult[Self]`，其 `value` 为当前样本对象。

        Raises:
            TypeError: `command` 不是 `VibEvalCommand` 枚举值。
        """

        from .commands import VibEvalCommand
        from .workflows import evaluate_sample

        if not isinstance(command, VibEvalCommand):
            raise TypeError("command 必须是 VibEvalCommand 枚举")
        return cast(OperationResult[Self], evaluate_sample(self, command, **options))

    def eval_zvl(self, *, overwrite: bool = False, **kwargs: Any) -> OperationResult[Self]:
        """执行 ZVL 评价。

        Args:
            overwrite: 是否允许覆盖已有 `zvl` 结果。
            **kwargs: 支持键包括 `freq_range`、`weight_type`、`time_windows`、
                `calc_unit_system`、`output_unit_system`。
        """

        from .commands import VibEvalCommand

        return self.evaluate(VibEvalCommand.ZVL, overwrite=overwrite, **kwargs)

    def eval_otovl(self, *, overwrite: bool = False, **kwargs: Any) -> OperationResult[Self]:
        """执行 OTOVL 评价。

        Args:
            overwrite: 是否允许覆盖已有 `otovl` 结果。
            **kwargs: 支持键包括 `freq_range`、`time_windows`、
                `calc_unit_system`、`output_unit_system`。
        """

        from .commands import VibEvalCommand

        return self.evaluate(VibEvalCommand.OTOVL, overwrite=overwrite, **kwargs)

    def eval_fdmvl(self, *, overwrite: bool = False, **kwargs: Any) -> OperationResult[Self]:
        """执行 FDMVL 评价。

        Args:
            overwrite: 是否允许覆盖已有 `fdmvl` 结果。
            **kwargs: 支持键包括 `freq_range`、`calc_unit_system`、
                `output_unit_system`。
        """

        from .commands import VibEvalCommand

        return self.evaluate(VibEvalCommand.FDMVL, overwrite=overwrite, **kwargs)

    def eval_fpvdv(self, *, overwrite: bool = False, **kwargs: Any) -> OperationResult[Self]:
        """执行 FPVDV 评价。

        Args:
            overwrite: 是否允许覆盖已有 `fpvdv` 结果。
            **kwargs: 支持键包括 `freq_range`、`nsup`、`calc_unit_system`、
                `output_unit_system`。
        """

        from .commands import VibEvalCommand

        return self.evaluate(VibEvalCommand.FPVDV, overwrite=overwrite, **kwargs)

    def _iter_container_fields(
        self,
        *,
        include_storage_only: bool = False,
    ) -> dict[str, DataModelBase]:
        allowed_fields = (
            set(self.sample_schema.field_names(include_storage_only=True)) if include_storage_only else None
        )
        return {
            self.sample_schema.property_name(name): value
            for name, value in self.data_vars.items()
            if isinstance(value, DataModelBase) and (allowed_fields is None or name in allowed_fields)
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
