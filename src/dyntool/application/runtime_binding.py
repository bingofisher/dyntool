"""默认对象运行时绑定。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol, cast

from ..domain.runtime import bind_model_runtime, bind_sample_runtime, bind_sample_set_runtime
from ..storage.runtime import StorageRuntime


class _StorageRuntimeFactory(Protocol):
    """存储运行时工厂协议。"""

    def __call__(self) -> "_StorageRuntimeService":
        """返回统一承接对象 I/O 的运行时实例。"""


class _StorageRuntimeService(Protocol):
    """默认对象运行时依赖的存储服务协议。"""

    def save_model_runtime(self, model: Any, path: Path, *, fmt: str = "h5", **options: Any) -> None: ...

    def load_model_runtime(
        self,
        model_type: type[Any],
        path: Path,
        *,
        fmt: str = "h5",
        **options: Any,
    ) -> Any: ...

    def inspect_model_units_runtime(
        self,
        model_type: type[Any],
        path: Path,
        *,
        fmt: str = "h5",
        **options: Any,
    ) -> dict[str, str]: ...

    def connect_sample_runtime(self, sample: Any, base_dir: Path, **options: Any) -> Any: ...

    def save_sample_runtime(self, sample: Any, path: Path | None = None, **options: Any) -> Any: ...

    def load_sample_runtime(self, sample: Any, path: Path | None = None, **options: Any) -> Any: ...

    def reload_sample_runtime(self, sample: Any) -> Any: ...

    def connect_sample_set_runtime(self, sample_set: Any, base_dir: Path, **options: Any) -> Any: ...

    def save_sample_set_runtime(
        self,
        sample_set: Any,
        path: Path | None = None,
        **options: Any,
    ) -> Any: ...

    def load_sample_set_runtime(
        self,
        sample_set: Any,
        path: Path | None = None,
        **options: Any,
    ) -> Any: ...

    def save_all_samples_runtime(self, sample_set: Any, **options: Any) -> dict[str, Exception]: ...

    def load_all_samples_runtime(self, sample_set: Any, **options: Any) -> dict[str, Exception]: ...

    def organize_sample_set_storage_runtime(self, sample_set: Any) -> Any: ...


_storage_runtime_factory: _StorageRuntimeFactory | None = None
_default_object_runtime: "_DefaultObjectRuntime" | None = None


def configure_application_runtime_bindings(
    *,
    storage_runtime_factory: _StorageRuntimeFactory | None = None,
) -> None:
    """配置默认对象运行时依赖。"""

    global _storage_runtime_factory
    global _default_object_runtime

    if storage_runtime_factory is not None:
        _storage_runtime_factory = storage_runtime_factory
    _default_object_runtime = None


def _build_storage_runtime() -> _StorageRuntimeService:
    """构造默认存储运行时实例。"""

    if _storage_runtime_factory is None:
        configure_application_runtime_bindings(storage_runtime_factory=StorageRuntime)
    assert _storage_runtime_factory is not None
    return cast(_StorageRuntimeService, _storage_runtime_factory())


class _DefaultObjectRuntime:
    """对象方法默认委托到的统一运行时。"""

    def __init__(self, storage_service: _StorageRuntimeService) -> None:
        """初始化默认对象运行时。"""

        self._storage_service = storage_service

    def save_model(self, model: Any, path: str | Path, *, fmt: str = "h5", **options: Any) -> None:
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

        return self._storage_service.load_model_runtime(model_type, Path(path), fmt=fmt, **options)

    def inspect_model_units(
        self,
        model_type: type[Any],
        path: str | Path,
        *,
        fmt: str = "h5",
        **options: Any,
    ) -> dict[str, str]:
        """检查模型文件中的单位。"""

        return cast(
            dict[str, str],
            self._storage_service.inspect_model_units_runtime(
                model_type,
                Path(path),
                fmt=fmt,
                **options,
            ),
        )

    def connect_sample_storage(self, sample: Any, base_dir: str | Path, **options: Any) -> Any:
        """为样本绑定存储上下文。"""

        return self._storage_service.connect_sample_runtime(sample, Path(base_dir), **options)

    def save_sample(self, sample: Any, path: str | Path | None = None, **options: Any) -> Any:
        """保存样本。"""

        return self._storage_service.save_sample_runtime(
            sample,
            path=Path(path) if path is not None else None,
            **options,
        )

    def load_sample(self, sample: Any, path: str | Path | None = None, **options: Any) -> Any:
        """加载样本。"""

        return self._storage_service.load_sample_runtime(
            sample,
            path=Path(path) if path is not None else None,
            **options,
        )

    def reload_sample(self, sample: Any) -> Any:
        """按当前上下文重新加载样本。"""

        return self._storage_service.reload_sample_runtime(sample)

    def connect_sample_set_storage(self, sample_set: Any, base_dir: str | Path, **options: Any) -> Any:
        """为样本集绑定存储上下文。"""

        return self._storage_service.connect_sample_set_runtime(sample_set, Path(base_dir), **options)

    def save_sample_set(self, sample_set: Any, path: str | Path | None = None, **options: Any) -> Any:
        """保存样本集。"""

        return self._storage_service.save_sample_set_runtime(
            sample_set,
            path=Path(path) if path is not None else None,
            **options,
        )

    def load_sample_set(self, sample_set: Any, path: str | Path | None = None, **options: Any) -> Any:
        """加载样本集。"""

        return self._storage_service.load_sample_set_runtime(
            sample_set,
            path=Path(path) if path is not None else None,
            **options,
        )

    def save_all_samples(self, sample_set: Any, **options: Any) -> dict[str, Exception]:
        """批量保存样本集中的样本。"""

        return cast(
            dict[str, Exception],
            self._storage_service.save_all_samples_runtime(sample_set, **options),
        )

    def load_all_samples(self, sample_set: Any, **options: Any) -> dict[str, Exception]:
        """批量加载样本集中的样本。"""

        return cast(
            dict[str, Exception],
            self._storage_service.load_all_samples_runtime(sample_set, **options),
        )

    def organize_sample_set_storage(self, sample_set: Any) -> Any:
        """整理样本集存储布局。"""

        return self._storage_service.organize_sample_set_storage_runtime(sample_set)


def bind_default_runtimes(*, force_recreate: bool = False) -> None:
    """为模型、样本和样本集绑定默认运行时。"""

    global _default_object_runtime

    from ..domain.models import DataModelBase
    from ..domain.samples import SampleBase, SampleSetBase

    if _default_object_runtime is None or force_recreate:
        _default_object_runtime = _DefaultObjectRuntime(_build_storage_runtime())

    bind_model_runtime(DataModelBase, _default_object_runtime)
    bind_sample_runtime(SampleBase, _default_object_runtime)
    bind_sample_set_runtime(SampleSetBase, _default_object_runtime)


def _initialize_default_bindings() -> None:
    """在顶层包导入时初始化默认运行时绑定。"""

    bind_default_runtimes()


__all__ = [
    "_initialize_default_bindings",
    "bind_default_runtimes",
    "configure_application_runtime_bindings",
]
