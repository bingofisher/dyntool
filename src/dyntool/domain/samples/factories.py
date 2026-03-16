"""样本与样本集工厂辅助函数。"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..enums import SampleDomain
from ..metadata import Metadata, MetadataBase, VibrationTestMetadata, normalize_extra
from ..models import AccelSeries

if TYPE_CHECKING:
    from .base import SampleBase
    from .sets import SampleSetBase


def infer_sample_domain(
    metadata: MetadataBase | type[MetadataBase] | None,
) -> SampleDomain | None:
    """根据元数据对象或类型推断样本领域。"""

    if metadata is None:
        return None
    metadata_type = metadata if isinstance(metadata, type) else type(metadata)
    if issubclass(metadata_type, VibrationTestMetadata):
        return SampleDomain.VIBRATION_TEST
    if issubclass(metadata_type, Metadata):
        return SampleDomain.DEFAULT
    return None


def require_sample_domain(domain: SampleDomain) -> SampleDomain:
    """校验样本领域枚举值。"""

    if not isinstance(domain, SampleDomain):
        raise TypeError("sample_domain 必须是 SampleDomain 枚举")
    return domain


def get_sample_class(domain: SampleDomain) -> type["SampleBase"]:
    """返回样本领域对应的样本类型。"""

    from .default import Sample
    from .vibration_test import VibrationTestSample

    mapping: dict[SampleDomain, type[SampleBase]] = {
        SampleDomain.DEFAULT: Sample,
        SampleDomain.VIBRATION_TEST: VibrationTestSample,
    }
    return mapping[require_sample_domain(domain)]


def get_sample_set_class(domain: SampleDomain) -> type["SampleSetBase[Any]"]:
    """返回样本领域对应的样本集类型。"""

    from .default import SampleSet
    from .vibration_test import VibrationTestSampleSet

    mapping: dict[SampleDomain, type[SampleSetBase[Any]]] = {
        SampleDomain.DEFAULT: SampleSet,
        SampleDomain.VIBRATION_TEST: VibrationTestSampleSet,
    }
    return mapping[require_sample_domain(domain)]


def get_metadata_class(domain: SampleDomain) -> type[MetadataBase]:
    """返回样本领域对应的元数据类型。"""

    mapping: dict[SampleDomain, type[MetadataBase]] = {
        SampleDomain.DEFAULT: Metadata,
        SampleDomain.VIBRATION_TEST: VibrationTestMetadata,
    }
    return mapping[require_sample_domain(domain)]


def infer_domain_from_sample_cls(sample_cls: type["SampleBase"]) -> SampleDomain | None:
    """根据样本类型推断样本领域。"""

    return infer_sample_domain(sample_cls.sample_schema.metadata_type)


def infer_domain_from_sample_set_cls(
    sample_set_cls: type["SampleSetBase[Any]"],
) -> SampleDomain | None:
    """根据样本集类型推断样本领域。"""

    sample_type = getattr(sample_set_cls, "_sample_type", None)
    if sample_type is None:
        return None
    return infer_sample_domain(sample_type.sample_schema.metadata_type)


def resolve_sample_class(
    requested_cls: type["SampleBase"],
    *,
    sample_domain: SampleDomain | None,
    metadata: MetadataBase | None,
    metadata_cls: type[MetadataBase] | None,
) -> tuple[type["SampleBase"], SampleDomain]:
    """解析最终应使用的样本类型。"""

    inferred_domain = sample_domain or infer_sample_domain(metadata) or infer_sample_domain(metadata_cls)
    cls_domain = infer_domain_from_sample_cls(requested_cls)
    is_dispatch_root = requested_cls.__name__ == "Sample"

    if not is_dispatch_root and cls_domain is not None and sample_domain is not None and cls_domain != sample_domain:
        raise ValueError("样本类型与 sample_domain 不一致")

    if not is_dispatch_root:
        return requested_cls, cls_domain or inferred_domain or SampleDomain.DEFAULT

    resolved_domain = inferred_domain or SampleDomain.DEFAULT
    return get_sample_class(resolved_domain), resolved_domain


def resolve_sample_set_class(
    requested_cls: type["SampleSetBase[Any]"],
    *,
    sample_domain: SampleDomain | None,
    samples: dict[str, SampleBase] | list[SampleBase] | None = None,
) -> tuple[type["SampleSetBase[Any]"], SampleDomain]:
    """解析最终应使用的样本集类型。"""

    cls_domain = infer_domain_from_sample_set_cls(requested_cls)
    inferred_domain = sample_domain
    if inferred_domain is None and samples:
        first_sample = next(iter(samples.values())) if isinstance(samples, dict) else samples[0]
        inferred_domain = infer_domain_from_sample_cls(type(first_sample))

    is_dispatch_root = requested_cls.__name__ == "SampleSet"
    if not is_dispatch_root and cls_domain is not None and sample_domain is not None and cls_domain != sample_domain:
        raise ValueError("样本集类型与 sample_domain 不一致")

    if not is_dispatch_root:
        return requested_cls, cls_domain or inferred_domain or SampleDomain.DEFAULT

    resolved_domain = inferred_domain or SampleDomain.DEFAULT
    return get_sample_set_class(resolved_domain), resolved_domain


def build_metadata(
    metadata_type: type[MetadataBase],
    **metadata_kwargs: Any,
) -> MetadataBase:
    """根据元数据类型构建元数据实例。"""

    extra = metadata_kwargs.pop("extra", None)

    if metadata_type is Metadata:
        identity = metadata_kwargs.pop("identity", {})
        attributes = metadata_kwargs.pop("attributes", {})
        if metadata_kwargs:
            attributes = {**dict(attributes), **metadata_kwargs}
        return Metadata(
            identity=dict(identity or {}),
            attributes=dict(attributes or {}),
            extra=normalize_extra(extra) if extra is not None else None,
        )

    if extra is not None:
        metadata_kwargs.setdefault("extra", extra)
    return metadata_type(**metadata_kwargs)


def create_sample(
    requested_cls: type["SampleBase"],
    *,
    sample_domain: SampleDomain | None,
    metadata: MetadataBase | None,
    metadata_cls: type[MetadataBase] | None,
    alias: str,
    data_vars: dict[str, Any],
    metadata_kwargs: dict[str, Any],
) -> SampleBase:
    """创建样本实例。"""

    sample_cls, resolved_domain = resolve_sample_class(
        requested_cls,
        sample_domain=sample_domain,
        metadata=metadata,
        metadata_cls=metadata_cls,
    )
    resolved_metadata_type = metadata_cls or sample_cls.sample_schema.metadata_type
    resolved_data_vars: dict[str, Any] = {}
    resolved_metadata_kwargs = dict(metadata_kwargs)

    for key, value in data_vars.items():
        if key == "data_vars" and isinstance(value, dict):
            for nested_key, nested_value in value.items():
                if sample_cls.sample_schema.has_slot(str(nested_key)):
                    resolved_data_vars[str(nested_key)] = nested_value
                else:
                    resolved_metadata_kwargs.setdefault(str(nested_key), nested_value)
            continue
        if sample_cls.sample_schema.has_slot(key):
            resolved_data_vars[key] = value
        else:
            resolved_metadata_kwargs.setdefault(key, value)

    if metadata is None:
        if resolved_metadata_type is MetadataBase:
            resolved_metadata_type = get_metadata_class(resolved_domain)
        metadata = build_metadata(resolved_metadata_type, **resolved_metadata_kwargs)

    sample = sample_cls(metadata=metadata, data_vars=resolved_data_vars)  # type: ignore[call-arg]
    if alias:
        sample.alias = alias
    return sample


def create_sample_from_accel(
    requested_cls: type["SampleBase"],
    values: Any,
    *,
    dt: float | None,
    time: Any = None,
    axis_unit: str | None,
    data_unit: str | None,
    sample_domain: SampleDomain | None,
    metadata: MetadataBase | None,
    metadata_cls: type[MetadataBase] | None,
    alias: str,
    metadata_kwargs: dict[str, Any],
) -> SampleBase:
    """从加速度数组创建样本实例。"""

    accel = AccelSeries.from_data(
        values,
        dt=dt,
        time=time,
        axis_unit=axis_unit,
        data_unit=data_unit,
    )
    return create_sample(
        requested_cls,
        sample_domain=sample_domain,
        metadata=metadata,
        metadata_cls=metadata_cls,
        alias=alias,
        data_vars={"accel": accel},
        metadata_kwargs=metadata_kwargs,
    )


def create_sample_set(
    requested_cls: type["SampleSetBase[Any]"],
    *,
    sample_domain: SampleDomain | None,
    samples: dict[str, SampleBase] | list[SampleBase] | None,
) -> SampleSetBase[Any]:
    """创建样本集实例。"""

    sample_set_cls, _ = resolve_sample_set_class(
        requested_cls,
        sample_domain=sample_domain,
        samples=samples,
    )
    return sample_set_cls(samples)


def connect_sample_set_storage(
    sample_set: SampleSetBase[Any],
    path: str | Path,
    **kwargs: Any,
) -> SampleSetBase[Any]:
    """连接样本集存储。"""

    return sample_set.connect_storage(str(path), **kwargs)


__all__ = [
    "build_metadata",
    "connect_sample_set_storage",
    "create_sample",
    "create_sample_from_accel",
    "create_sample_set",
    "get_metadata_class",
    "get_sample_class",
    "get_sample_set_class",
    "infer_domain_from_sample_cls",
    "infer_domain_from_sample_set_cls",
    "infer_sample_domain",
    "require_sample_domain",
    "resolve_sample_class",
    "resolve_sample_set_class",
]
