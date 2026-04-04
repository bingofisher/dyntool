"""存储运行时内部共享定义。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, TypeVar

from ..domain.metadata import MetadataBase
from ..domain.models import DataModelBase
from ..domain.samples import SampleBaseModel, SampleSetBase
from ..infrastructure.storage_constants import (
    DEFAULT_SQLITE_INDEX_FILENAME,
    DEFAULT_SQLITE_PAYLOAD_H5_FILENAME,
    METADATA_TABLE_FILENAME,
)
from ..logging import get_logger
from ._repository import detect_storage_scheme, validate_detected_scheme
from .types import StorageMode, StorageScheme

logger = get_logger("storage")

ModelT = TypeVar("ModelT", bound=DataModelBase)
MetadataT = TypeVar("MetadataT", bound=MetadataBase)
SampleT = TypeVar("SampleT", bound=SampleBaseModel)

_H5_SUFFIXES = {".h5", ".hdf5", ".hdf"}


def infer_model_format(path: str | Path) -> str:
    """根据路径后缀推断模型存储格式。"""

    return "h5" if Path(path).suffix.lower() in _H5_SUFFIXES else "csv"


def infer_sample_set_scheme(path: Path) -> StorageScheme:
    """根据样本集路径推断存储方案。"""

    try:
        return detect_storage_scheme(path, kind="sample_set")
    except Exception:  # noqa: BLE001
        if path.is_dir():
            index_path = path / DEFAULT_SQLITE_INDEX_FILENAME
            payload_path = path / DEFAULT_SQLITE_PAYLOAD_H5_FILENAME
            if index_path.exists() and payload_path.exists():
                return StorageScheme.SET_SQLITE_H5
            if (path / METADATA_TABLE_FILENAME).exists():
                return StorageScheme.SET_ATTR_TABLE
        return StorageScheme.SET_H5 if path.suffix.lower() in _H5_SUFFIXES else StorageScheme.SET_DIR


def infer_sample_scheme(path: Path) -> StorageScheme:
    """根据单样本路径推断存储方案。"""

    try:
        return detect_storage_scheme(path, kind="sample")
    except Exception:  # noqa: BLE001
        suffix = path.suffix.lower()
        if suffix in _H5_SUFFIXES:
            return StorageScheme.SAMPLE_H5
        if suffix == ".json":
            return StorageScheme.SAMPLE_JSON
        return StorageScheme.SET_DIR


def resolve_sample_set_scheme_for_read(
    path: Path,
    *,
    requested_scheme: StorageScheme | None,
) -> StorageScheme:
    """在读路径上解析并校验样本集存储方案。"""

    return validate_detected_scheme(path, requested_scheme=requested_scheme, kind="sample_set")


def resolve_sample_scheme_for_read(
    path: Path,
    *,
    requested_scheme: StorageScheme | None,
) -> StorageScheme:
    """在读路径上解析并校验单样本存储方案。"""

    return validate_detected_scheme(path, requested_scheme=requested_scheme, kind="sample")


def resolve_sample_set_connect_target(
    path: Path,
    scheme: StorageScheme,
    *,
    set_filename: str | None,
) -> tuple[Path, str | None]:
    """解析样本集连接时的根目录和集合级文件名。"""

    if scheme is not StorageScheme.SET_H5:
        return path, set_filename
    if path.suffix.lower() in _H5_SUFFIXES:
        return path.parent, set_filename or path.name
    return path, set_filename


def require_scheme(scheme: StorageScheme | str) -> StorageScheme:
    """校验并返回存储方案枚举。"""

    if isinstance(scheme, StorageScheme):
        return scheme
    if isinstance(scheme, str):
        try:
            return StorageScheme(scheme)
        except ValueError as exc:
            raise TypeError("storage_scheme 必须是 StorageScheme 枚举或其合法字符串值") from exc
    raise TypeError("storage_scheme 必须是 StorageScheme 枚举或其合法字符串值")


def require_mode(mode: StorageMode | str) -> StorageMode:
    """校验并返回存储模式枚举。"""

    if isinstance(mode, StorageMode):
        return mode
    if isinstance(mode, str):
        try:
            return StorageMode(mode)
        except ValueError as exc:
            raise TypeError("mode 必须是 StorageMode 枚举或其合法字符串值") from exc
    raise TypeError("mode 必须是 StorageMode 枚举或其合法字符串值")


def bind_samples(sample_set: SampleSetBase[Any]) -> None:
    """为样本集中的样本回填 `_storage_set` 绑定。"""

    for sample in sample_set.values():
        sample._storage_set = sample_set


__all__ = [
    "MetadataT",
    "ModelT",
    "SampleT",
    "bind_samples",
    "infer_model_format",
    "infer_sample_scheme",
    "infer_sample_set_scheme",
    "logger",
    "require_mode",
    "require_scheme",
    "resolve_sample_scheme_for_read",
    "resolve_sample_set_connect_target",
    "resolve_sample_set_scheme_for_read",
]
