"""存储适配层入口。"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from .sample_set_storage import SampleSetStorage
from .sample_storage import SampleStorage
from ..storage.types import (
    NameResolver,
    StorageConnectOptions,
    StorageMode,
    StorageScheme,
)
from .persistence import (
    DataBackend,
    get_backend,
    load,
    register_after_load,
    register_backend,
    register_before_save,
    save,
)

if TYPE_CHECKING:
    from ..domain.samples.sets import SampleSetBase


def connect_storage(
    sample_set: SampleSetBase[Any],
    base_dir: str | Path,
    *,
    options: StorageConnectOptions | None = None,
    mode: StorageMode | None = None,
    storage_scheme: StorageScheme | None = None,
    data_options: dict[str, Any] | None = None,
    name_resolver: NameResolver | None = None,
    set_filename: str | None = None,
) -> SampleSetBase[Any]:
    """连接样本集存储，仅接受枚举或显式类型对象。"""
    return sample_set.connect_storage(
        base_dir=base_dir,
        options=options,
        mode=mode,
        storage_scheme=storage_scheme,
        data_options=data_options,
        name_resolver=name_resolver,  # type: ignore[arg-type]
        set_filename=set_filename,
    )


__all__ = [
    "DataBackend",
    "SampleStorage",
    "SampleSetStorage",
    "StorageConnectOptions",
    "StorageMode",
    "StorageScheme",
    "NameResolver",
    "connect_storage",
    "register_backend",
    "get_backend",
    "register_before_save",
    "register_after_load",
    "save",
    "load",
]
