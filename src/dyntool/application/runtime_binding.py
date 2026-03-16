"""应用层默认运行时绑定。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from ..domain.runtime import (
    bind_model_runtime,
    bind_sample_runtime,
    bind_sample_set_runtime,
)

_resource_loader_cls: type[Any] | None = None
_logging_mode_cls: type[Any] | None = None
_storage_mode_cls: type[Any] | None = None
_storage_runtime_factory: type[Any] | None = None
_default_object_runtime: DefaultObjectRuntime | None = None


def configure_application_runtime_bindings(
    *,
    resource_loader_cls: type[Any] | None = None,
    logging_mode_cls: type[Any] | None = None,
    storage_mode_cls: type[Any] | None = None,
    storage_runtime_factory: type[Any] | None = None,
) -> None:
    """配置应用层运行时依赖。"""

    global _resource_loader_cls
    global _logging_mode_cls
    global _storage_mode_cls
    global _storage_runtime_factory
    global _default_object_runtime

    if resource_loader_cls is not None:
        _resource_loader_cls = resource_loader_cls
    if logging_mode_cls is not None:
        _logging_mode_cls = logging_mode_cls
    if storage_mode_cls is not None:
        _storage_mode_cls = storage_mode_cls
    if storage_runtime_factory is not None:
        _storage_runtime_factory = storage_runtime_factory
    _default_object_runtime = None


def get_resource_loader_cls() -> type[Any]:
    """返回资源加载器类型。"""

    if _resource_loader_cls is None:
        from .resource_loader import ResourceLoader

        configure_application_runtime_bindings(resource_loader_cls=ResourceLoader)
    assert _resource_loader_cls is not None
    return _resource_loader_cls


def get_logging_mode_cls() -> type[Any]:
    """返回日志模式枚举类型。"""

    if _logging_mode_cls is None:
        from ..logging.types import LoggingMode

        configure_application_runtime_bindings(logging_mode_cls=LoggingMode)
    assert _logging_mode_cls is not None
    return _logging_mode_cls


def get_storage_mode_cls() -> type[Any]:
    """返回存储模式枚举类型。"""

    if _storage_mode_cls is None:
        from ..storage.types import StorageMode

        configure_application_runtime_bindings(storage_mode_cls=StorageMode)
    assert _storage_mode_cls is not None
    return _storage_mode_cls


def _build_storage_runtime() -> Any:
    """构造默认存储运行时。"""

    if _storage_runtime_factory is None:
        from ..storage.runtime import StorageRuntime

        configure_application_runtime_bindings(storage_runtime_factory=StorageRuntime)
    assert _storage_runtime_factory is not None
    return _storage_runtime_factory()


class DefaultObjectRuntime:
    """默认对象运行时委托。

    Attributes:
        _storage_service: 统一承接模型、样本和样本集 I/O 的存储运行时实例。
    """

    def __init__(self, storage_service: Any) -> None:
        """初始化默认对象运行时。

        Args:
            storage_service: 提供模型、样本和样本集存储能力的服务对象。
        """

        self._storage_service = storage_service

    def save_model(
        self,
        model: Any,
        path: str | Path,
        *,
        fmt: str = "h5",
        **options: Any,
    ) -> None:
        """保存数据模型。"""

        self._storage_service.save_model_runtime(model, Path(path), fmt=fmt, **options)

    def load_model(
        self,
        model_type: type[Any],
        path: str | Path,
        *,
        fmt: str = "h5",
        **options: Any,
    ) -> Any:
        """加载数据模型。"""

        return self._storage_service.load_model_runtime(
            model_type,
            Path(path),
            fmt=fmt,
            **options,
        )

    def inspect_model_units(
        self,
        model_type: type[Any],
        path: str | Path,
        *,
        fmt: str = "h5",
        **options: Any,
    ) -> dict[str, str]:
        """检查模型文件中的单位信息。"""

        return cast(
            dict[str, str],
            self._storage_service.inspect_model_units_runtime(
                model_type,
                Path(path),
                fmt=fmt,
                **options,
            ),
        )

    def connect_sample_storage(
        self,
        sample: Any,
        base_dir: str | Path,
        **kwargs: Any,
    ) -> Any:
        """为样本对象绑定存储上下文。"""

        return self._storage_service.connect_sample_runtime(
            sample,
            Path(base_dir),
            **kwargs,
        )

    def save_sample(
        self,
        sample: Any,
        path: str | Path | None = None,
        **kwargs: Any,
    ) -> Any:
        """保存样本对象。"""

        return self._storage_service.save_sample_runtime(
            sample,
            path=Path(path) if path is not None else None,
            **kwargs,
        )

    def load_sample(
        self,
        sample: Any,
        path: str | Path | None = None,
        **kwargs: Any,
    ) -> Any:
        """加载样本对象。"""

        return self._storage_service.load_sample_runtime(
            sample,
            path=Path(path) if path is not None else None,
            **kwargs,
        )

    def reload_sample(self, sample: Any) -> Any:
        """按样本已连接的上下文重新加载样本。"""

        return self._storage_service.reload_sample_runtime(sample)

    def connect_sample_set_storage(
        self,
        sample_set: Any,
        base_dir: str | Path,
        **kwargs: Any,
    ) -> Any:
        """为样本集对象绑定存储上下文。"""

        return self._storage_service.connect_sample_set_runtime(
            sample_set,
            Path(base_dir),
            **kwargs,
        )

    def save_sample_set(
        self,
        sample_set: Any,
        path: str | Path | None = None,
        **kwargs: Any,
    ) -> Any:
        """保存样本集对象。"""

        return self._storage_service.save_sample_set_runtime(
            sample_set,
            path=Path(path) if path is not None else None,
            **kwargs,
        )

    def load_sample_set(
        self,
        sample_set: Any,
        path: str | Path | None = None,
        **kwargs: Any,
    ) -> Any:
        """加载样本集对象。"""

        return self._storage_service.load_sample_set_runtime(
            sample_set,
            path=Path(path) if path is not None else None,
            **kwargs,
        )

    def save_all_samples(
        self,
        sample_set: Any,
        **kwargs: Any,
    ) -> dict[str, Exception]:
        """批量保存样本集中的全部样本。"""

        return cast(
            dict[str, Exception],
            self._storage_service.save_all_samples_runtime(sample_set, **kwargs),
        )

    def load_all_samples(
        self,
        sample_set: Any,
        **kwargs: Any,
    ) -> dict[str, Exception]:
        """批量加载样本集中的全部样本。"""

        return cast(
            dict[str, Exception],
            self._storage_service.load_all_samples_runtime(sample_set, **kwargs),
        )

    def organize_sample_set_storage(self, sample_set: Any) -> Any:
        """整理样本集存储布局。"""

        return self._storage_service.organize_sample_set_storage_runtime(sample_set)


def bind_default_runtimes(*, force_recreate: bool = False) -> None:
    """为领域对象绑定默认运行时。"""

    global _default_object_runtime

    from ..domain.models import DataModelBase
    from ..domain.samples import SampleBase, SampleSetBase

    if _default_object_runtime is None or force_recreate:
        _default_object_runtime = DefaultObjectRuntime(_build_storage_runtime())

    bind_model_runtime(DataModelBase, _default_object_runtime)
    bind_sample_runtime(SampleBase, _default_object_runtime)
    bind_sample_set_runtime(SampleSetBase, _default_object_runtime)


def _initialize_default_bindings() -> None:
    """在顶层包导入时初始化默认运行时绑定。"""

    bind_default_runtimes()


__all__ = [
    "DefaultObjectRuntime",
    "_initialize_default_bindings",
    "bind_default_runtimes",
    "configure_application_runtime_bindings",
    "get_logging_mode_cls",
    "get_resource_loader_cls",
    "get_storage_mode_cls",
]
