"""AdvDynTool 正式存储模块。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, TypeAlias, TypeVar

from ..domain.enums import SampleDomain
from ..domain.metadata import MetadataBase
from ..domain.models import DataModelBase
from ..domain.samples import SampleBaseModel, SampleSetBase
from .runtime import StorageRuntime
from .types import AttrDataFormat, ContainerFormat, NameResolver, StorageMode, StorageScheme

ModelT = TypeVar("ModelT", bound=DataModelBase)
MetadataT = TypeVar("MetadataT", bound=MetadataBase)
SampleT = TypeVar("SampleT", bound=SampleBaseModel)
SampleSetT = TypeVar("SampleSetT", bound=SampleSetBase[Any])
IOOptions: TypeAlias = dict[str, Any]


def save_model(
    model: DataModelBase,
    path: str | Path,
    *,
    io_options: IOOptions | None = None,
) -> Path:
    """保存单个数据模型。"""

    return StorageRuntime().save_model_runtime(
        model,
        path,
        fmt=StorageRuntime.infer_model_format(path),
        **dict(io_options or {}),
    )


def load_model(
    path: str | Path,
    model_type: type[ModelT],
    *,
    io_options: IOOptions | None = None,
) -> ModelT:
    """加载单个数据模型。"""

    return StorageRuntime().load_model_runtime(
        model_type,
        path,
        fmt=StorageRuntime.infer_model_format(path),
        **dict(io_options or {}),
    )


def inspect_model_units(
    path: str | Path,
    model_type: type[DataModelBase],
    *,
    io_options: IOOptions | None = None,
) -> dict[str, str]:
    """检查模型文件中的单位信息。"""

    return StorageRuntime().inspect_model_units_runtime(
        model_type,
        path,
        fmt=StorageRuntime.infer_model_format(path),
        **dict(io_options or {}),
    )


def save_metadata(metadata: MetadataBase, path: str | Path) -> Path:
    """保存元数据文件。"""

    return StorageRuntime.save_metadata(metadata, path)


def load_metadata(path: str | Path, metadata_type: type[MetadataT]) -> MetadataT:
    """加载元数据文件。"""

    return StorageRuntime.load_metadata(path, metadata_type)


def save_sample(
    sample: SampleT,
    path: str | Path,
    *,
    io_options: IOOptions | None = None,
) -> SampleT:
    """保存单个样本。"""

    return StorageRuntime().save_sample_runtime(
        sample,
        path=path,
        **dict(io_options or {}),
    )


def load_sample(
    sample: SampleT,
    path: str | Path,
    *,
    io_options: IOOptions | None = None,
) -> SampleT:
    """加载单个样本。"""

    return StorageRuntime().load_sample_runtime(
        sample,
        path=path,
        **dict(io_options or {}),
    )


def connect_sample_set(
    sample_set: SampleSetT,
    base_dir: str | Path,
    *,
    scheme: StorageScheme,
    mode: StorageMode | None = None,
    data_options: dict[str, Any] | None = None,
    name_resolver: NameResolver | None = None,
    set_filename: str | None = None,
) -> SampleSetT:
    """将样本集连接到指定存储位置。"""

    return StorageRuntime().connect_sample_set_runtime(
        sample_set,
        base_dir,
        storage_scheme=scheme,
        mode=mode,
        data_options=data_options,
        name_resolver=name_resolver,
        set_filename=set_filename,
    )


def save_sample_set(
    sample_set: SampleSetBase[Any],
    path: str | Path,
    *,
    scheme: StorageScheme | None = None,
    data_options: dict[str, Any] | None = None,
    categories: list[str] | None = None,
    strict: bool | None = None,
    filter: Callable[[Any], bool] | None = None,
    workers: int = 1,
    chunk_size: int = 256,
    name_resolver: NameResolver | None = None,
    set_filename: str | None = None,
) -> None:
    """保存样本集。"""

    StorageRuntime().save_sample_set_runtime(
        sample_set,
        path=path,
        storage_scheme=scheme,
        data_options=data_options,
        categories=categories,
        strict=strict,
        filter=filter,
        workers=workers,
        chunk_size=chunk_size,
        name_resolver=name_resolver,
        set_filename=set_filename,
    )


def load_sample_set(
    path: str | Path,
    *,
    domain: SampleDomain,
    scheme: StorageScheme | None = None,
    data_options: dict[str, Any] | None = None,
    categories: list[str] | None = None,
    strict: bool | None = None,
    filter: Callable[[Any], bool] | None = None,
    workers: int = 1,
    chunk_size: int = 256,
    set_filename: str | None = None,
) -> SampleSetBase[Any]:
    """加载样本集。"""

    return StorageRuntime().load(
        path,
        domain=domain,
        scheme=scheme,
        data_options=data_options,
        categories=categories,
        strict=strict,
        filter=filter,
        workers=workers,
        chunk_size=chunk_size,
        set_filename=set_filename,
    )


__all__ = [
    "AttrDataFormat",
    "ContainerFormat",
    "StorageMode",
    "StorageScheme",
    "connect_sample_set",
    "inspect_model_units",
    "load_metadata",
    "load_model",
    "load_sample",
    "load_sample_set",
    "save_metadata",
    "save_model",
    "save_sample",
    "save_sample_set",
]
