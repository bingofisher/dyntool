"""样本 schema 定义。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..constants import DataCategory, SAMPLE_ATTR_TO_DATA_CATEGORY
from ..metadata import MetadataBase
from ..models import DataModelBase
from .types import SampleField


def _coerce_sample_field(value: SampleField | str | None, *, property_name: str) -> SampleField:
    """把声明值解析为 ``SampleField``。"""

    if value is None:
        return SampleField(property_name)
    if isinstance(value, SampleField):
        return value
    return SampleField(str(value).strip())


def _coerce_data_category(
    value: DataCategory | str | None,
    *,
    property_name: str,
) -> DataCategory | None:
    """把声明值解析为 ``DataCategory``。"""

    if value is None:
        return SAMPLE_ATTR_TO_DATA_CATEGORY.get(property_name)
    if isinstance(value, DataCategory):
        return value
    return DataCategory(str(value).strip())


@dataclass(frozen=True, slots=True)
class SampleSlotSpec:
    """描述单个样本数据项规格。"""

    name: str
    model_type: type[DataModelBase]
    aliases: tuple[str, ...] = ()
    required: bool = False
    role: str | None = None
    include_in_storage: bool = True
    field: SampleField | str | None = None
    category: DataCategory | str | None = None

    def __post_init__(self) -> None:
        resolved_name = str(self.name).strip()
        if not resolved_name:
            raise ValueError("SampleSlotSpec.name 不能为空")
        object.__setattr__(self, "name", resolved_name)
        object.__setattr__(self, "field", _coerce_sample_field(self.field, property_name=resolved_name))
        object.__setattr__(self, "category", _coerce_data_category(self.category, property_name=resolved_name))

    @property
    def property_name(self) -> str:
        """返回样本属性访问名。"""

        return self.name

    def supports(self, value: Any) -> bool:
        """判断数据项是否接受当前值。"""

        return isinstance(value, self.model_type)


@dataclass(frozen=True, slots=True)
class SampleSchema:
    """描述样本元数据类型与数据项规格。"""

    name: str
    version: int = 1
    metadata_type: type[MetadataBase] = MetadataBase
    slots: tuple[SampleSlotSpec, ...] = ()
    aliases: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        resolved_aliases = {str(key).strip(): str(value).strip() for key, value in self.aliases.items()}
        object.__setattr__(self, "aliases", resolved_aliases)

    def canonical_name(self, name: str) -> str:
        """把属性别名解析为样本属性名。"""

        raw_name = str(name).strip()
        if raw_name in self.aliases:
            return self.aliases[raw_name]
        for spec in self.slots:
            if raw_name == spec.property_name or raw_name in spec.aliases:
                return spec.property_name
        return raw_name

    def resolve_field(self, selector: SampleField | DataCategory | str) -> SampleField:
        """把公开或内部选择器解析为 ``SampleField``。"""

        if isinstance(selector, SampleField):
            return selector
        if isinstance(selector, DataCategory):
            for spec in self.slots:
                if spec.category == selector:
                    return spec.field  # type: ignore[return-value]
            raise KeyError(f"当前样本 schema 不支持 DataCategory: {selector.value}")
        canonical_name = self.canonical_name(str(selector))
        for spec in self.slots:
            if canonical_name == spec.property_name:
                return spec.field  # type: ignore[return-value]
        raise KeyError(f"未知样本槽位/数据项: {selector}")

    def field_spec(self, selector: SampleField | DataCategory | str) -> SampleSlotSpec:
        """按字段、分类或属性名获取数据项规格。"""

        field = self.resolve_field(selector)
        for spec in self.slots:
            if spec.field == field:
                return spec
        raise KeyError(f"未知样本数据项: {selector}")

    def slot(self, selector: SampleField | DataCategory | str) -> SampleSlotSpec:
        """兼容旧命名，返回对应数据项规格。"""

        return self.field_spec(selector)

    def has_slot(self, selector: SampleField | DataCategory | str) -> bool:
        """判断 schema 是否包含指定数据项。"""

        try:
            self.field_spec(selector)
        except KeyError:
            return False
        return True

    def property_name(self, selector: SampleField | DataCategory | str) -> str:
        """返回指定数据项的属性访问名。"""

        return self.field_spec(selector).property_name

    def category(self, selector: SampleField | DataCategory | str) -> DataCategory:
        """返回指定数据项的公开 ``DataCategory``。"""

        spec = self.field_spec(selector)
        if spec.category is None:
            raise KeyError(f"样本数据项 '{spec.property_name}' 未声明公开 DataCategory")
        return spec.category

    def slot_names(self, *, include_storage_only: bool = False) -> tuple[str, ...]:
        """兼容旧命名，返回属性访问名列表。"""

        return self.property_names(include_storage_only=include_storage_only)

    def property_names(self, *, include_storage_only: bool = False) -> tuple[str, ...]:
        """返回属性访问名列表。"""

        if not include_storage_only:
            return tuple(spec.property_name for spec in self.slots)
        return tuple(spec.property_name for spec in self.slots if spec.include_in_storage)

    def field_names(self, *, include_storage_only: bool = False) -> tuple[SampleField, ...]:
        """返回内部 ``SampleField`` 列表。"""

        if not include_storage_only:
            return tuple(spec.field for spec in self.slots)
        return tuple(spec.field for spec in self.slots if spec.include_in_storage)

    def supported_categories(self) -> tuple[DataCategory, ...]:
        """返回 schema 支持的公开 ``DataCategory`` 子集。"""

        return tuple(spec.category for spec in self.slots if spec.category is not None)

    def storable_categories(self) -> tuple[DataCategory, ...]:
        """返回允许进入 storage 流程的公开 ``DataCategory`` 子集。"""

        return tuple(spec.category for spec in self.slots if spec.category is not None and spec.include_in_storage)


__all__ = ["SampleSchema", "SampleSlotSpec"]
