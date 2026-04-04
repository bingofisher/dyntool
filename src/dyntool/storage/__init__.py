"""AdvDynTool 正式存储模块。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, TypeAlias, TypeVar

from ..domain.constants import DataCategory
from ..domain.enums import SampleDomain
from ..domain.metadata import MetadataBase
from ..domain.models import DataModelBase
from ..domain.samples import SampleBaseModel, SampleSetBase
from ..domain.samples.types import SampleLoadMode, SampleSetViewOptions, StorageAccessMode
from ._repository import detect_storage_scheme, inspect_storage_repository
from .runtime import StorageRuntime
from .types import (
    AttrDataFormat,
    ContainerFormat,
    NameResolver,
    StorageConnectOptions,
    StorageMode,
    StorageRepositoryReport,
    StorageScheme,
)

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
    """将样本集连接到指定存储位置。

    Notes:
        `data_options` 采用正式命名契约，未知键会立即报错。H5 样本存储默认启用
        `gzip` 压缩，默认级别为 `4`。
    """

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
    progress_callback: Callable[[int, int], None] | None = None,
    show_progress: bool | None = None,
    categories: list[str] | None = None,
    strict: bool | None = None,
    filter: Callable[[Any], bool] | None = None,
    workers: int = 1,
    chunk_size: int = 256,
    name_resolver: NameResolver | None = None,
    set_filename: str | None = None,
) -> None:
    """保存样本集。

    Notes:
        当目标方案为 `SAMPLE_H5` 或 `SET_H5` 时，若未显式覆盖压缩相关参数，
        将默认使用 `gzip` 压缩和级别 `4`。
        `show_progress=None` 时，会按当前 logging 是否输出到控制台自动判定是否显示
        简洁进度条；`progress_callback` 始终接收 `(completed, total)`。
    """

    StorageRuntime().save_sample_set_runtime(
        sample_set,
        path=path,
        storage_scheme=scheme,
        data_options=data_options,
        progress_callback=progress_callback,
        show_progress=show_progress,
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
    progress_callback: Callable[[int, int], None] | None = None,
    show_progress: bool | None = None,
    categories: list[str] | None = None,
    strict: bool | None = None,
    filter: Callable[[Any], bool] | None = None,
    workers: int = 1,
    chunk_size: int = 256,
    set_filename: str | None = None,
) -> SampleSetBase[Any]:
    """加载样本集。

    Notes:
        `data_options` 会在连接阶段完成校验；不适用于当前方案的键和未知键都会直接报错。
        `show_progress=None` 时，会按当前 logging 是否输出到控制台自动判定是否显示
        简洁进度条；`progress_callback` 始终接收 `(completed, total)`。
    """

    return StorageRuntime().load(
        path,
        domain=domain,
        scheme=scheme,
        data_options=data_options,
        progress_callback=progress_callback,
        show_progress=show_progress,
        categories=categories,
        strict=strict,
        filter=filter,
        workers=workers,
        chunk_size=chunk_size,
        set_filename=set_filename,
    )


__all__ = [
    "DataCategory",
    "SampleDomain",
    "SampleLoadMode",
    "SampleSetViewOptions",
    "StorageAccessMode",
    "AttrDataFormat",
    "ContainerFormat",
    "NameResolver",
    "StorageConnectOptions",
    "StorageMode",
    "StorageRepositoryReport",
    "StorageScheme",
    "connect_sample_set",
    "detect_storage_scheme",
    "inspect_storage_repository",
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
