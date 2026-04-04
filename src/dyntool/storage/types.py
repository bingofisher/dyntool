"""存储层公开枚举、连接选项与仓库检查报告类型。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from ..domain.constants import DataCategory

if TYPE_CHECKING:
    from ..domain.samples.base import SampleBaseModel


class StorageMode(StrEnum):
    """存储连接模式枚举。

    枚举值:
        - ``OPEN``: 连接已有存储，不主动创建缺失结构。
        - ``CREATE``: 仅在目标不存在时创建存储。
        - ``RECREATE``: 重建目标存储，适用于明确允许覆盖的场景。

    影响:
        该枚举会影响存储连接阶段的目录创建、文件覆盖和初始化行为。
    """

    OPEN = "open"
    CREATE = "create"
    RECREATE = "recreate"


class StorageScheme(StrEnum):
    """正式存储方案枚举。

    枚举值:
        - ``SAMPLE_JSON``: 单样本 JSON 存储。
        - ``SAMPLE_H5``: 单样本 H5 存储。
        - ``SET_H5``: 样本集单文件 H5 存储。
        - ``SET_SQLITE_H5``: SQLite 索引加 H5 payload 混合存储。
        - ``SET_ATTR_TABLE``: 属性表驱动的样本集目录存储。
        - ``SET_DIR``: 按样本目录组织的样本集存储。

    影响:
        该枚举会影响样本集连接策略、默认文件布局、读写路径和仓库检查逻辑。
    """

    SAMPLE_JSON = "sample_json"
    SAMPLE_H5 = "sample_h5"
    SET_H5 = "set_h5"
    SET_SQLITE_H5 = "set_sqlite_h5"
    SET_ATTR_TABLE = "attr_table"
    SET_DIR = "sample_dir"


class ContainerFormat(StrEnum):
    """单个数据模型容器格式枚举。"""

    CSV = "csv"
    H5 = "h5"
    NPY = "npy"
    JSON = "json"


class AttrDataFormat(StrEnum):
    """`SET_ATTR_TABLE` 属性文件落盘格式枚举。

    枚举值:
        - ``CSV``: 以 CSV 保存属性表。
        - ``NPY``: 以 NPY 保存属性数组。

    影响:
        该枚举会影响属性表落盘格式和后续读取逻辑。
    """

    CSV = "csv"
    NPY = "npy"


NameResolver = Callable[["SampleBaseModel", dict[str, Any]], str]
"""样本命名解析器类型。"""


@dataclass(slots=True)
class StorageConnectOptions:
    """面向调用方的存储连接参数。

    Attributes:
        base_dir: 目标存储根目录或基础路径。
        scheme: 目标存储方案。
        mode: 连接模式。
        data_options: 底层存储实现使用的附加参数。
        name_resolver: 样本名解析函数。
        set_filename: 样本集单文件方案的文件名。
    """

    base_dir: str | Path | None = None
    scheme: StorageScheme = StorageScheme.SET_DIR
    mode: StorageMode = StorageMode.OPEN
    data_options: dict[str, Any] | None = None
    name_resolver: NameResolver | None = None
    set_filename: str = "all_samples.h5"


@dataclass(slots=True)
class ResolvedStorageConnectOptions:
    """标准化后的连接参数。

    Attributes:
        mode: 解析后的连接模式。
        storage_scheme: 解析后的正式存储方案。
        data_options: 解析后的底层存储参数。
        name_resolver: 解析后的样本命名函数。
        set_filename: 解析后的样本集文件名。
    """

    mode: StorageMode
    storage_scheme: StorageScheme
    data_options: dict[str, Any] | None
    name_resolver: NameResolver | None
    set_filename: str


@dataclass(slots=True)
class StorageRepositoryReport:
    """存储仓库结构与完整性检查报告。"""

    path: Path
    detected_scheme: StorageScheme | None
    requested_scheme: StorageScheme | None
    level: str
    exists: bool
    is_valid: bool
    issues: tuple[str, ...]
    warnings: tuple[str, ...]
    sample_count: int | None = None


def resolve_connect_options(
    *,
    options: StorageConnectOptions | None,
    mode: StorageMode | None,
    storage_scheme: StorageScheme | None,
    data_options: dict[str, Any] | None,
    name_resolver: NameResolver | None,
    set_filename: str | None,
    default_set_filename: str,
) -> ResolvedStorageConnectOptions:
    """解析连接参数优先级并返回标准化结果。

    Args:
        options: 调用方传入的结构化连接参数。
        mode: 显式传入的连接模式，会覆盖 `options.mode`。
        storage_scheme: 显式传入的存储方案，会覆盖 `options.scheme`。
        data_options: 显式传入的底层存储参数，会覆盖 `options.data_options`。
        name_resolver: 显式传入的样本命名函数，会覆盖 `options.name_resolver`。
        set_filename: 显式传入的样本集文件名，会覆盖 `options.set_filename`。
        default_set_filename: 当调用方未提供文件名时使用的默认值。

    Returns:
        标准化后的连接参数对象。

    Notes:
        显式关键字参数优先级高于 `options` 中的对应字段；`data_options`
        会复制后返回，避免调用方与运行时共享可变字典。
    """

    resolved_mode = options.mode if options is not None else StorageMode.OPEN
    resolved_scheme = options.scheme if options is not None else StorageScheme.SET_DIR
    resolved_data_options = options.data_options.copy() if options and options.data_options is not None else None
    resolved_name_resolver = options.name_resolver if options is not None else None
    resolved_set_filename = options.set_filename if options is not None else default_set_filename

    if mode is not None:
        resolved_mode = mode
    if storage_scheme is not None:
        resolved_scheme = storage_scheme
    if data_options is not None:
        resolved_data_options = data_options.copy()
    if name_resolver is not None:
        resolved_name_resolver = name_resolver
    if set_filename is not None:
        resolved_set_filename = set_filename

    return ResolvedStorageConnectOptions(
        mode=resolved_mode,
        storage_scheme=resolved_scheme,
        data_options=resolved_data_options,
        name_resolver=resolved_name_resolver,
        set_filename=resolved_set_filename,
    )


def resolve_data_category(sample_attr: str) -> DataCategory:
    """将样本字段名映射为统一数据类别枚举。"""

    return _SAMPLE_ATTR_TO_DATA_CATEGORY.get(sample_attr, DataCategory.UNDEFINED)


_SAMPLE_ATTR_TO_DATA_CATEGORY: dict[str, DataCategory] = {
    "accel": DataCategory.TS_ACCEL,
    "vel": DataCategory.TS_VEL,
    "disp": DataCategory.TS_DISP,
    "force": DataCategory.TS_FORCE,
    "freqspec": DataCategory.FS_SPEC,
    "respspec": DataCategory.RS_SPEC,
    "zvl": DataCategory.ZVL_EVAL,
    "otovl": DataCategory.OTOVL_EVAL,
    "fpvdv": DataCategory.FPVDV_EVAL,
    "fdmvl": DataCategory.FDMVL_EVAL,
}


__all__ = [
    "AttrDataFormat",
    "ContainerFormat",
    "NameResolver",
    "ResolvedStorageConnectOptions",
    "StorageConnectOptions",
    "StorageMode",
    "StorageRepositoryReport",
    "StorageScheme",
    "resolve_connect_options",
    "resolve_data_category",
]
