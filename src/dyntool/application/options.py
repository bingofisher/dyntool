"""应用层保留的公开选项类型。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from ..compute.context import ComputeContext
from ..domain.enums import SampleDomain
from ..domain.plot_types import PlotBackend, PlotKind
from .runtime_binding import get_logging_mode_cls, get_storage_mode_cls

NameResolver = Callable[[object, dict[str, Any]], str]


@dataclass(slots=True)
class MetadataOptions:
    """元数据构造参数。"""

    domain: SampleDomain = SampleDomain.DEFAULT
    fields: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class SampleCreateOptions:
    """样本构造参数。"""

    domain: SampleDomain = SampleDomain.DEFAULT
    alias: str = ""
    metadata_kwargs: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class CsvReadOptions:
    """CSV 读取参数。"""

    skiprows: int | list[int] | None = None
    sep: str | None = None
    delimiter: str | None = None
    header: int | list[int] | None = 0
    names: list[str] | None = None
    index_col: int | str | None = 0
    encoding: str | None = "utf-8"
    comment: str | None = None
    decimal: str | None = None
    extras: dict[str, Any] = field(default_factory=dict)

    def to_kwargs(self) -> dict[str, Any]:
        """转换为 `read_csv` 参数。"""

        kwargs: dict[str, Any] = dict(self.extras)
        for key in (
            "skiprows",
            "sep",
            "delimiter",
            "header",
            "names",
            "index_col",
            "encoding",
            "comment",
            "decimal",
        ):
            value = getattr(self, key)
            if value is not None:
                kwargs.setdefault(key, value)
        return kwargs


@dataclass(slots=True)
class StorageSaveOptions:
    """存储保存参数。"""

    path: str | Path
    scheme: object | None = None
    data_options: dict[str, Any] | None = None
    set_filename: str | None = None


@dataclass(slots=True)
class StorageLoadOptions:
    """存储加载参数。"""

    path: str | Path
    domain: SampleDomain
    scheme: object | None = None
    data_options: dict[str, Any] | None = None
    set_filename: str | None = None


@dataclass(slots=True)
class ProcessOptions:
    """处理参数。"""

    context: ComputeContext = field(default_factory=ComputeContext)
    dt: float | None = None
    truncate_range: tuple[float, float] | None = None
    baseline: str | None = None
    baseline_order: int = 1
    highpass: float | None = None
    lowpass: float | None = None
    bandpass: tuple[float, float] | None = None
    filter_order: int = 4
    extras: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class EvalOptions:
    """评价参数。"""

    context: ComputeContext = field(default_factory=ComputeContext)
    overwrite: bool = False
    extras: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class PlotOptions:
    """绘图参数。"""

    kind: PlotKind = PlotKind.TIME
    backend: PlotBackend = PlotBackend.MATPLOTLIB
    attr: str | None = None
    uid: str | None = None
    use_chinese: bool = True
    extras: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ResourceQueryOptions:
    """资源查询参数。"""

    key: str | None = None
    freq_range: tuple[float, float] = (1.0, 80.0)
    csv_options: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class LoggingOptions:
    """日志配置参数。"""

    provider: str = "loguru"
    provider_options: dict[str, Any] = field(default_factory=dict)
    mode: object = field(default_factory=lambda: get_logging_mode_cls().CONSOLE_ONLY)
    log_file: str | Path | None = None
    log_dir: str | Path | None = None
    level: str = "INFO"
    mirror_to_console: bool = True
    max_bytes: int = 0
    backup_count: int = 0
    fmt: str | None = None
    datefmt: str | None = None


@dataclass(slots=True)
class StorageConnectOptions:
    """样本集连接存储参数。"""

    base_dir: str | Path
    scheme: object
    mode: object = field(default_factory=lambda: get_storage_mode_cls().OPEN)
    data_options: dict[str, Any] | None = None
    name_resolver: NameResolver | None = None
    set_filename: str | None = None


__all__ = [
    "CsvReadOptions",
    "EvalOptions",
    "LoggingOptions",
    "MetadataOptions",
    "PlotOptions",
    "ProcessOptions",
    "ResourceQueryOptions",
    "SampleCreateOptions",
    "StorageConnectOptions",
    "StorageLoadOptions",
    "StorageSaveOptions",
]
