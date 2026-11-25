"""默认对象 runtime 绑定。"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol, TypeVar, cast

from ..domain.runtime import bind_model_runtime, bind_sample_runtime, bind_sample_set_runtime
from ..storage.runtime import StorageRuntime


if TYPE_CHECKING:
    from ..domain.models import DataModelBase
    from ..domain.samples import SampleBase, SampleSetBase

ModelT = TypeVar("ModelT", bound="DataModelBase")
SampleT = TypeVar("SampleT", bound="SampleBase")
SampleSetT = TypeVar("SampleSetT", bound="SampleSetBase[Any]")


class _StorageRuntimeFactory(Protocol):
    """存储 runtime 工厂协议。"""

    def __call__(self) -> "_StorageRuntimeService": ...


class _StorageRuntimeService(Protocol):
    """默认对象 runtime 依赖的存储服务协议。"""

    def save_model_runtime(self, model: DataModelBase, path: Path, *, fmt: str = "h5", **options: Any) -> Path: ...
    def load_model_runtime(
        self, model_type: type[DataModelBase], path: Path, *, fmt: str = "h5", **options: Any
    ) -> DataModelBase: ...
    def inspect_model_units_runtime(
        self,
        model_type: type[DataModelBase],
        path: Path,
        *,
        fmt: str = "h5",
        **options: Any,
    ) -> dict[str, str]: ...
    def connect_sample_runtime(self, sample: SampleBase, base_dir: Path, **options: Any) -> SampleBase: ...
    def save_sample_runtime(self, sample: SampleBase, path: Path | None = None, **options: Any) -> SampleBase: ...
    def load_sample_runtime(self, sample: SampleBase, path: Path | None = None, **options: Any) -> SampleBase: ...
    def reload_sample_runtime(self, sample: SampleBase) -> SampleBase: ...
    def connect_sample_set_runtime(
        self, sample_set: SampleSetBase[Any], base_dir: Path, **options: Any
    ) -> SampleSetBase[Any]: ...
    def save_sample_set_runtime(
        self, sample_set: SampleSetBase[Any], path: Path | None = None, **options: Any
    ) -> SampleSetBase[Any]: ...
    def load_sample_set_runtime(
        self, sample_set: SampleSetBase[Any], path: Path | None = None, **options: Any
    ) -> SampleSetBase[Any]: ...
    def save_all_samples_runtime(self, sample_set: SampleSetBase[Any], **options: Any) -> dict[str, Exception]: ...
    def load_all_samples_runtime(self, sample_set: SampleSetBase[Any], **options: Any) -> dict[str, Exception]: ...
    def organize_sample_set_storage_runtime(self, sample_set: SampleSetBase[Any]) -> SampleSetBase[Any]: ...
    def export_scalar_frame_runtime(
        self, sample_set: SampleSetBase[Any], output_path: Path, **options: Any
    ) -> Path: ...
    def export_series_frame_runtime(
        self, sample_set: SampleSetBase[Any], output_path: Path, **options: Any
    ) -> Path: ...
    def export_peaks_frame_runtime(self, sample_set: SampleSetBase[Any], output_path: Path, **options: Any) -> Path: ...
    def export_report_package_runtime(
        self, sample_set: SampleSetBase[Any], output_dir: Path, **options: Any
    ) -> Path: ...


_storage_runtime_factory: _StorageRuntimeFactory | None = None
_default_object_runtime: "_DefaultObjectRuntime" | None = None


def configure_application_runtime_bindings(
    *,
    storage_runtime_factory: _StorageRuntimeFactory | None = None,
) -> None:
    """配置默认对象 runtime 的依赖。"""

    global _storage_runtime_factory
    global _default_object_runtime

    if storage_runtime_factory is not None:
        _storage_runtime_factory = storage_runtime_factory
    _default_object_runtime = None


def _build_storage_runtime() -> _StorageRuntimeService:
    """构造默认存储 runtime 实例。"""

    if _storage_runtime_factory is None:
        configure_application_runtime_bindings(storage_runtime_factory=StorageRuntime)
    assert _storage_runtime_factory is not None
    return cast(_StorageRuntimeService, _storage_runtime_factory())


class _DefaultObjectRuntime:
    """对象方法默认委托到的统一 runtime。"""

    def __init__(self, storage_service: _StorageRuntimeService) -> None:
        self._storage_service = storage_service

    def save_model(self, model: DataModelBase, path: str | Path, *, fmt: str = "h5", **options: Any) -> None:
        self._storage_service.save_model_runtime(model, Path(path), fmt=fmt, **options)

    def load_model(
        self,
        model_type: type[ModelT],
        path: str | Path,
        *,
        fmt: str = "h5",
        **options: Any,
    ) -> ModelT:
        return cast(ModelT, self._storage_service.load_model_runtime(model_type, Path(path), fmt=fmt, **options))

    def inspect_model_units(
        self,
        model_type: type[ModelT],
        path: str | Path,
        *,
        fmt: str = "h5",
        **options: Any,
    ) -> dict[str, str]:
        return cast(
            dict[str, str],
            self._storage_service.inspect_model_units_runtime(model_type, Path(path), fmt=fmt, **options),
        )

    def connect_sample_storage(self, sample: SampleT, base_dir: str | Path, **options: Any) -> SampleT:
        return cast(SampleT, self._storage_service.connect_sample_runtime(sample, Path(base_dir), **options))

    def save_sample(self, sample: SampleT, path: str | Path | None = None, **options: Any) -> SampleT:
        return cast(
            SampleT,
            self._storage_service.save_sample_runtime(
                sample,
                path=Path(path) if path is not None else None,
                **options,
            ),
        )

    def load_sample(self, sample: SampleT, path: str | Path | None = None, **options: Any) -> SampleT:
        return cast(
            SampleT,
            self._storage_service.load_sample_runtime(
                sample,
                path=Path(path) if path is not None else None,
                **options,
            ),
        )

    def reload_sample(self, sample: SampleT) -> SampleT:
        return cast(SampleT, self._storage_service.reload_sample_runtime(sample))

    def connect_sample_set_storage(self, sample_set: SampleSetT, base_dir: str | Path, **options: Any) -> SampleSetT:
        return cast(SampleSetT, self._storage_service.connect_sample_set_runtime(sample_set, Path(base_dir), **options))

    def save_sample_set(self, sample_set: SampleSetT, path: str | Path | None = None, **options: Any) -> SampleSetT:
        return cast(
            SampleSetT,
            self._storage_service.save_sample_set_runtime(
                sample_set,
                path=Path(path) if path is not None else None,
                **options,
            ),
        )

    def load_sample_set(self, sample_set: SampleSetT, path: str | Path | None = None, **options: Any) -> SampleSetT:
        return cast(
            SampleSetT,
            self._storage_service.load_sample_set_runtime(
                sample_set,
                path=Path(path) if path is not None else None,
                **options,
            ),
        )

    def save_all_samples(self, sample_set: SampleSetT, **options: Any) -> dict[str, Exception]:
        return cast(dict[str, Exception], self._storage_service.save_all_samples_runtime(sample_set, **options))

    def load_all_samples(self, sample_set: SampleSetT, **options: Any) -> dict[str, Exception]:
        return cast(dict[str, Exception], self._storage_service.load_all_samples_runtime(sample_set, **options))

    def organize_sample_set_storage(self, sample_set: SampleSetT) -> SampleSetT:
        return cast(SampleSetT, self._storage_service.organize_sample_set_storage_runtime(sample_set))

    def export_scalar_frame(self, sample_set: SampleSetT, output_path: str | Path, **options: Any) -> Path:
        return self._storage_service.export_scalar_frame_runtime(sample_set, Path(output_path), **options)

    def export_series_frame(self, sample_set: SampleSetT, output_path: str | Path, **options: Any) -> Path:
        return self._storage_service.export_series_frame_runtime(sample_set, Path(output_path), **options)

    def export_peaks_frame(self, sample_set: SampleSetT, output_path: str | Path, **options: Any) -> Path:
        return self._storage_service.export_peaks_frame_runtime(sample_set, Path(output_path), **options)

    def export_report_package(self, sample_set: SampleSetT, output_dir: str | Path, **options: Any) -> Path:
        return self._storage_service.export_report_package_runtime(sample_set, Path(output_dir), **options)


def bind_default_runtimes(*, force_recreate: bool = False) -> None:
    """为模型、样本和样本集绑定默认 runtime。"""

    global _default_object_runtime

    from ..domain.models import DataModelBase
    from ..domain.samples import SampleBase, SampleSetBase

    if _default_object_runtime is None or force_recreate:
        _default_object_runtime = _DefaultObjectRuntime(_build_storage_runtime())

    bind_model_runtime(DataModelBase, _default_object_runtime)
    bind_sample_runtime(SampleBase, _default_object_runtime)
    bind_sample_set_runtime(SampleSetBase, _default_object_runtime)


def _initialize_default_bindings() -> None:
    """按需初始化默认 runtime 绑定。"""

    bind_default_runtimes()


__all__ = [
    "_initialize_default_bindings",
    "bind_default_runtimes",
    "configure_application_runtime_bindings",
]
