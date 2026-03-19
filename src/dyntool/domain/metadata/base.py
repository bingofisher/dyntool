"""元数据基类与 UID 生成。"""

from __future__ import annotations

import json
import os
import uuid
from abc import abstractmethod
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable, ClassVar, Self

import pandas as pd
from pydantic import BaseModel, ConfigDict, PrivateAttr, computed_field

from ..serialization import StructuredPayload, normalize_payload
from .normalization import denormalize_flat_dict, normalize_extra
from .schema import MetadataSchema

PathLike = str | os.PathLike[str]


class MetadataIDGenerator:
    """基于标准化 JSON 的稳定元数据 UID 生成器。"""

    DEFAULT_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_DNS, "metadata")
    DEFAULT_FLOAT_PRECISION = 6

    def __init__(
        self,
        *,
        namespace: uuid.UUID | None = None,
        float_precision: int = DEFAULT_FLOAT_PRECISION,
        enable_registry: bool = False,
        custom_serializer: Callable[[Any], Any] | None = None,
    ) -> None:
        self.namespace = namespace or self.DEFAULT_NAMESPACE
        self.float_precision = float_precision
        self.custom_serializer = custom_serializer
        self._registry = {} if enable_registry else None

    @staticmethod
    def _normalize(obj: Any, prec: int) -> Any:
        if isinstance(obj, float):
            rounded = round(obj, prec)
            return 0.0 if rounded == -0.0 else rounded
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        if isinstance(obj, dict):
            return {key: MetadataIDGenerator._normalize(value, prec) for key, value in obj.items()}
        if isinstance(obj, (list, tuple)):
            return type(obj)(MetadataIDGenerator._normalize(item, prec) for item in obj)
        if isinstance(obj, (set, frozenset)):
            items = [MetadataIDGenerator._normalize(item, prec) for item in obj]
            return sorted(
                items,
                key=lambda item: json.dumps(
                    item,
                    sort_keys=True,
                    ensure_ascii=False,
                    default=str,
                ),
            )
        return obj

    def generate_id(self, metadata: dict[str, Any]) -> str:
        """根据元数据内容生成稳定 UID。"""

        if not isinstance(metadata, dict):
            raise TypeError("metadata 必须是 dict")
        normalized = self._normalize(metadata, self.float_precision)
        if self.custom_serializer is not None:
            normalized = self.custom_serializer(normalized)
        payload = json.dumps(
            normalized,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
            default=str,
        )
        uid = str(uuid.uuid5(self.namespace, payload))
        if self._registry is not None:
            self._registry[uid] = metadata.copy()
        return uid

    def get_metadata(self, uid: str) -> dict[str, Any] | None:
        """返回注册表中的元数据内容。"""

        if self._registry is None:
            raise RuntimeError("注册表未启用，请在初始化时设置 enable_registry=True")
        return self._registry.get(uid)

    def is_registered(self, uid: str) -> bool:
        """判断 UID 是否已注册。"""

        return self._registry is not None and uid in self._registry

    @classmethod
    def quick_id(
        cls,
        metadata: dict[str, Any],
        float_precision: int = DEFAULT_FLOAT_PRECISION,
    ) -> str:
        """快速生成稳定 UID。"""

        return cls(float_precision=float_precision).generate_id(metadata)


class MetadataBase(BaseModel):
    """所有公开元数据对象的基础类。"""

    model_config = ConfigDict(extra="allow", arbitrary_types_allowed=True, validate_assignment=True)
    payload_domain: ClassVar[str] = "default"
    metadata_schema: ClassVar[MetadataSchema] = MetadataSchema(name="metadata")

    _change_callback: Callable[[MetadataBase, str, str | None], None] | None = PrivateAttr(default=None)
    _suspend_change_callback: bool = PrivateAttr(default=False)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, MetadataBase):
            return self.uid == other.uid
        if isinstance(other, dict):
            try:
                return self.uid == self.from_flatten_dict(other).uid
            except Exception:
                return False
        return False

    @computed_field
    @property
    def uid(self) -> str:
        """返回稳定 UID。"""

        return self.generate_uid()

    @computed_field
    @property
    def alias(self) -> str:
        """返回当前元数据对象的业务 alias。"""

        return self.build_alias()

    @computed_field
    @property
    def schema_name(self) -> str:
        """返回元数据 schema 名称。"""

        return self.metadata_schema.name

    @computed_field
    @property
    def schema_version(self) -> int:
        """返回元数据 schema 版本。"""

        return self.metadata_schema.version

    @abstractmethod
    def generate_uid(self) -> str:
        """生成稳定 UID。"""

    def build_alias(self) -> str:
        """构建当前元数据对象的 alias。

        Returns:
            str: 当前元数据对象的 alias。基类默认直接返回稳定 `uid`。
        """

        return self.uid

    @classmethod
    def from_alias(cls, alias: str) -> Self:
        """根据 alias 反构建元数据对象。

        Args:
            alias: 业务 alias 字符串。
        Raises:
            NotImplementedError: 当前元数据类型未声明 alias 解析规则时抛出。
        """

        raise NotImplementedError(f"{cls.__name__} 未声明 alias 反构建规则: {alias}")

    def refresh_alias(self, *, force: bool = False) -> str:
        """显式重建 alias 并返回最新值。

        Args:
            force: 是否强制刷新。对 metadata 本身仅起显式意图标识作用，不影响返回逻辑。
        Returns:
            str: 最新 alias。
        """

        del force
        return self.build_alias()

    def __setattr__(self, name: str, value: Any) -> None:
        """追踪元数据字段赋值，并在需要时通知拥有者。"""

        if name.startswith("_") or name not in self.__class__.model_fields:
            super().__setattr__(name, value)
            return

        old_value = getattr(self, name, None)
        old_uid = self.uid
        old_alias = getattr(self, "alias", None)
        super().__setattr__(name, value)

        if self._change_callback is None or self._suspend_change_callback:
            return
        try:
            self._change_callback(self, old_uid, old_alias)
        except Exception:
            self._suspend_change_callback = True
            try:
                super().__setattr__(name, old_value)
            finally:
                self._suspend_change_callback = False
            raise

    def bind_change_callback(
        self,
        callback: Callable[[MetadataBase, str, str | None], None] | None,
    ) -> None:
        """绑定或清空元数据变更回调。"""

        self._change_callback = callback

    def identity_payload(self) -> dict[str, Any]:
        """返回 schema 定义的身份字段。"""

        payload = self.model_dump(exclude={"uid", "alias", "schema_name", "schema_version"})
        return self.metadata_schema.normalize_identity(payload)

    def attribute_payload(self) -> dict[str, Any]:
        """返回 schema 定义的属性字段。"""

        payload = self.model_dump(exclude={"uid", "alias", "schema_name", "schema_version"})
        return self.metadata_schema.normalize_attributes(payload)

    def extra_payload(self) -> dict[str, Any] | None:
        """返回附加元数据。"""

        extra_field = self.metadata_schema.extra_field
        if extra_field is None:
            return None
        return normalize_extra(getattr(self, extra_field, None))

    def canonical_payload(self) -> dict[str, Any]:
        """返回 schema 驱动的规范化结构。"""

        return {
            "schema_name": self.schema_name,
            "schema_version": self.schema_version,
            "identity": self.identity_payload(),
            "attributes": self.attribute_payload(),
            "extra": self.extra_payload(),
        }

    def update(self, **kwargs: Any) -> None:
        """原地更新字段。"""

        old_payload = self.model_dump()
        old_uid = self.uid
        old_alias = getattr(self, "alias", None)
        self._suspend_change_callback = True
        try:
            for key, value in kwargs.items():
                if key not in self.__class__.model_fields:
                    raise KeyError(f"未知元数据字段: {key}")
                super().__setattr__(key, value)
        except Exception:
            self._suspend_change_callback = False
            raise
        self._suspend_change_callback = False

        if self._change_callback is None:
            return
        try:
            self._change_callback(self, old_uid, old_alias)
        except Exception:
            self._suspend_change_callback = True
            try:
                for key, value in old_payload.items():
                    if key in self.__class__.model_fields:
                        super().__setattr__(key, value)
            finally:
                self._suspend_change_callback = False
            raise

    def copy_with(self, **kwargs: Any) -> Self:
        """返回更新字段后的副本。"""

        payload = self.model_dump()
        payload.update(kwargs)
        payload.pop("uid", None)
        payload.pop("alias", None)
        return self.__class__(**payload)

    def to_flatten_dict(self, sep: str = "@") -> dict[str, Any]:
        """导出扁平字典。"""

        normalized = pd.json_normalize(self.model_dump(), sep=sep)
        return normalized.iloc[0].to_dict()

    @classmethod
    def from_flatten_dict(cls, data: dict[str, Any], sep: str = "@") -> Self:
        """从扁平字典恢复。"""

        payload = denormalize_flat_dict(data, sep=sep)
        payload.pop("uid", None)
        payload.pop("alias", None)
        return cls(**payload)

    def match(self, **criteria: Any) -> bool:
        """按谓词匹配元数据。"""

        for name, predicate in criteria.items():
            if not hasattr(self, name):
                raise KeyError(f"元数据不存在字段 {name!r}")
            if not callable(predicate):
                raise TypeError(f"字段 {name!r} 的筛选条件必须是可调用对象")
            if not predicate(getattr(self, name)):
                return False
        return True

    def to_dict(self) -> dict[str, Any]:
        """导出字典。"""

        return self.model_dump()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """从字典恢复对象。"""

        payload = dict(data)
        payload.pop("uid", None)
        payload.pop("alias", None)
        payload.pop("schema_name", None)
        payload.pop("schema_version", None)
        return cls(**payload)

    def to_json(self, path: str | PathLike) -> None:
        """保存为 JSON 文件。"""

        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )

    @classmethod
    def from_json(cls, path: str | PathLike) -> Self:
        """从 JSON 文件读取。"""

        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise TypeError("metadata JSON 内容必须是对象")
        return cls.from_dict(payload)

    def to_structured_payload(self) -> StructuredPayload:
        """导出为 `StructuredPayload`。"""

        return StructuredPayload(
            entity_type="metadata",
            domain=self.payload_domain,
            category=self.__class__.__name__,
            meta=self.to_dict(),
            attrs={
                "metadata_type": self.__class__.__name__,
                "schema_name": self.schema_name,
                "schema_version": self.schema_version,
            },
        )

    @classmethod
    def from_structured_payload(
        cls,
        payload: StructuredPayload | dict[str, Any],
    ) -> MetadataBase:
        """从 `StructuredPayload` 恢复元数据对象。"""

        normalized = normalize_payload(payload)
        if cls is MetadataBase:
            from .registry import metadata_from_structured_payload

            return metadata_from_structured_payload(normalized)
        return cls.from_dict(normalized.meta)


__all__ = ["MetadataBase", "MetadataIDGenerator"]
