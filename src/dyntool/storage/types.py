"""存储层公开枚举、连接选项与辅助解析工具。"""

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
        `OPEN`: 连接已存在的目标，不主动创建目录或文件；路径不存在时应立即失败。
        `CREATE`: 如目标不存在则创建，若已存在则复用现有内容。
        `RECREATE`: 如目标已存在则先删除再重建，会清空旧存储内容。

    影响:
        该枚举直接影响 `connect()` 和保存入口在连接阶段是否创建目录、是否允许复用旧内容，
        以及是否会破坏性地重建存储根路径。
    """

    OPEN = "open"
    CREATE = "create"
    RECREATE = "recreate"


class StorageScheme(StrEnum):
    """正式存储方案枚举。

    枚举值:
        `SAMPLE_JSON`: 每个样本使用 JSON 容器保存。
        `SAMPLE_H5`: 每个样本使用独立 HDF5 容器保存。
        `SET_H5`: 整个样本集写入同一个 HDF5 文件。
        `ATTR_TABLE`: 以表格布局组织元数据和属性索引。
        `SAMPLE_DIR`: 每个样本对应一个目录，目录内再保存各数据槽位文件。

    影响:
        该枚举决定 `SampleStorage` 选择的底层策略、目录结构、容器格式，
        以及 `base_dir`、`set_filename` 和样本命名解析器的解释方式。
    """

    SAMPLE_JSON = "sample_json"
    SAMPLE_H5 = "sample_h5"
    SET_H5 = "set_h5"
    ATTR_TABLE = "attr_table"
    SAMPLE_DIR = "sample_dir"


class ContainerFormat(StrEnum):
    """单个数据模型容器格式枚举。

    枚举值:
        `CSV`: 文本表格格式，便于人工检查和互操作。
        `H5`: HDF5 二进制格式，适合保存结构化数组与单位信息。
        `NPY`: NumPy 原生数组文件。
        `JSON`: JSON 文本格式。
    """

    CSV = "csv"
    H5 = "h5"
    NPY = "npy"
    JSON = "json"


class AttrDataFormat(StrEnum):
    """样本属性数据载荷格式枚举。

    枚举值:
        `CSV`: 将属性数据按 CSV 文本导出。
        `NPY`: 将属性数据按 NumPy 二进制数组导出。

    影响:
        该枚举会改变样本目录方案中属性数据文件的落盘格式，
        也会改变精度收敛和后续反序列化使用的 I/O 路径。
    """

    CSV = "csv"
    NPY = "npy"


# 样本命名解析器类型。输入为样本对象和包含 `uid`、`alias`、`storage_scheme`
# 的上下文映射，返回最终文件名或目录名。
NameResolver = Callable[["SampleBaseModel", dict[str, Any]], str]


@dataclass(slots=True)
class StorageConnectOptions:
    """面向调用方的存储连接参数。

    Attributes:
        base_dir: 存储根目录或样本集根路径。
        scheme: 存储方案枚举，决定底层策略与目录布局。
        mode: 连接模式枚举，决定是否创建或重建目标。
        data_options: 透传给存储上下文的格式和精度选项。
        name_resolver: 自定义样本文件名解析函数。
        set_filename: 当 `scheme` 为 `SET_H5` 时使用的样本集文件名。
    """

    base_dir: str | Path | None = None
    scheme: StorageScheme = StorageScheme.SAMPLE_DIR
    mode: StorageMode = StorageMode.OPEN
    data_options: dict[str, Any] | None = None
    name_resolver: NameResolver | None = None
    set_filename: str = "all_samples.h5"


@dataclass(slots=True)
class ResolvedStorageConnectOptions:
    """合并默认值与显式覆盖后的标准化连接参数。

    Attributes:
        mode: 实际生效的连接模式。
        storage_scheme: 实际生效的存储方案。
        data_options: 复制后的数据选项字典。
        name_resolver: 实际生效的命名解析器。
        set_filename: 实际生效的样本集文件名。
    """

    mode: StorageMode
    storage_scheme: StorageScheme
    data_options: dict[str, Any] | None
    name_resolver: NameResolver | None
    set_filename: str


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
        options: 聚合连接参数对象，可提供默认值。
        mode: 显式连接模式；提供时覆盖 `options.mode`。
        storage_scheme: 显式存储方案；提供时覆盖 `options.scheme`。
        data_options: 显式数据选项；提供时覆盖 `options.data_options`。
        name_resolver: 显式命名解析器；提供时覆盖 `options.name_resolver`。
        set_filename: 显式样本集文件名；提供时覆盖 `options.set_filename`。
        default_set_filename: 当调用方与 `options` 都未指定时使用的默认文件名。

    Returns:
        ResolvedStorageConnectOptions: 已合并优先级并复制可变字段后的标准化结果。

    Notes:
        参数优先级为：显式关键字参数 > `options` 中的对应字段 > 内部默认值。
        `data_options` 会复制一份，避免调用方在连接后继续修改原字典时污染运行时状态。
    """

    resolved_mode = options.mode if options is not None else StorageMode.OPEN
    resolved_scheme = options.scheme if options is not None else StorageScheme.SAMPLE_DIR
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
    """将样本属性名映射为统一数据类别枚举。"""

    return _SAMPLE_ATTR_TO_DATA_CATEGORY.get(sample_attr, DataCategory.UNDEFINED)


# 样本字段名到标准数据类别的映射，用于统一存储分类和序列化分发。
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
    "StorageScheme",
    "resolve_connect_options",
    "resolve_data_category",
]
