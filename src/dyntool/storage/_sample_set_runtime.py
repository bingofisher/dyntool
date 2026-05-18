"""样本集存储运行时实现。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Literal, cast, overload

from ..domain.enums import SampleDomain
from ..domain.samples import SampleSet, SampleSetBase, VibrationTestSampleSet
from ..domain.samples.factories import get_sample_set_class, require_sample_domain
from ..domain.samples.types import SampleLoadMode
from ._runtime_common import (
    bind_samples,
    infer_sample_set_scheme,
    logger,
    require_mode,
    require_scheme,
    resolve_sample_set_connect_target,
    resolve_sample_set_scheme_for_read,
)
from ._sample_set_request_summary import (
    summarize_sample_set_categories,
    summarize_sample_set_data_options,
    summarize_sample_set_scheme,
)
from .types import NameResolver, StorageConnectOptions, StorageMode, StorageScheme


@dataclass(slots=True)
class _ResolvedSampleSetConnectRequest:
    """样本集运行时连接请求的标准化结果。"""

    base_dir: Path
    mode: StorageMode
    storage_scheme: StorageScheme
    data_options: dict[str, Any] | None
    name_resolver: NameResolver | None
    set_filename: str | None


def _resolve_sample_set_connect_request(
    base_dir: str | Path,
    *,
    options: StorageConnectOptions | None = None,
    mode: StorageMode | None = None,
    storage_scheme: StorageScheme | None = None,
    data_options: dict[str, Any] | None = None,
    name_resolver: NameResolver | None = None,
    set_filename: str | None = None,
) -> _ResolvedSampleSetConnectRequest:
    """标准化样本集 connect 请求。"""

    resolved_base_dir = Path(base_dir)
    resolved_mode = mode
    resolved_scheme = storage_scheme
    resolved_data_options = data_options
    resolved_name_resolver = name_resolver
    resolved_set_filename = set_filename
    if options is not None:
        resolved_base_dir = Path(getattr(options, "base_dir", base_dir))
        resolved_mode = getattr(options, "mode", mode)
        resolved_scheme = getattr(options, "scheme", storage_scheme)
        resolved_data_options = getattr(options, "data_options", data_options)
        resolved_name_resolver = getattr(options, "name_resolver", name_resolver)
        resolved_set_filename = getattr(options, "set_filename", set_filename)
    actual_mode = require_mode(resolved_mode or StorageMode.OPEN)
    if actual_mode is StorageMode.OPEN and resolved_base_dir.exists() and resolved_scheme is None:
        actual_scheme = resolve_sample_set_scheme_for_read(
            resolved_base_dir,
            requested_scheme=resolved_scheme,
        )
    else:
        actual_scheme = require_scheme(resolved_scheme or StorageScheme.SET_DIR)
    actual_base_dir, actual_set_filename = resolve_sample_set_connect_target(
        resolved_base_dir,
        actual_scheme,
        set_filename=resolved_set_filename,
    )
    return _ResolvedSampleSetConnectRequest(
        base_dir=actual_base_dir,
        mode=actual_mode,
        storage_scheme=actual_scheme,
        data_options=resolved_data_options,
        name_resolver=resolved_name_resolver,
        set_filename=actual_set_filename,
    )


def _resolve_sample_set_path_request(
    path: str | Path,
    *,
    default_mode: StorageMode,
    storage_scheme: StorageScheme | None = None,
    data_options: dict[str, Any] | None = None,
    name_resolver: NameResolver | None = None,
    set_filename: str | None = None,
    for_read: bool,
) -> _ResolvedSampleSetConnectRequest:
    """标准化带 path 的样本集请求。"""

    target = Path(path)
    if for_read:
        actual_scheme = resolve_sample_set_scheme_for_read(
            target,
            requested_scheme=storage_scheme,
        )
    else:
        actual_scheme = require_scheme(storage_scheme or infer_sample_set_scheme(target))
    base_dir, actual_set_filename = resolve_sample_set_connect_target(
        target,
        actual_scheme,
        set_filename=set_filename,
    )
    return _ResolvedSampleSetConnectRequest(
        base_dir=base_dir,
        mode=require_mode(default_mode),
        storage_scheme=actual_scheme,
        data_options=data_options,
        name_resolver=name_resolver,
        set_filename=actual_set_filename,
    )


class _SampleSetStorageRuntimeMixin:
    """封装样本集及批量样本存储行为。"""

    @staticmethod
    def _resolve_storage_request_for_path(
        path: str | Path | None,
        *,
        default_mode: StorageMode,
        storage_scheme: StorageScheme | None = None,
        data_options: dict[str, Any] | None = None,
        name_resolver: NameResolver | None = None,
        set_filename: str | None = None,
        for_read: bool,
    ) -> _ResolvedSampleSetConnectRequest | None:
        """按需为带路径的批量动作解析 storage request。"""

        if path is None:
            return None
        return _resolve_sample_set_path_request(
            path,
            default_mode=default_mode,
            storage_scheme=storage_scheme,
            data_options=data_options,
            name_resolver=name_resolver,
            set_filename=set_filename,
            for_read=for_read,
        )

    def _ensure_sample_set_storage(
        self,
        sample_set: SampleSetBase[Any],
        *,
        request: _ResolvedSampleSetConnectRequest | None = None,
    ) -> Any:
        """在需要时先连接存储并返回已连接的 storage 对象。"""

        if request is not None:
            self._connect_resolved_sample_set_storage(sample_set, request)
        if sample_set.storage is None:
            raise RuntimeError("样本集尚未连接存储，请先调用 connect_storage()")
        return sample_set.storage

    @staticmethod
    def _connect_resolved_sample_set_storage(
        sample_set: SampleSetBase[Any],
        request: _ResolvedSampleSetConnectRequest,
    ) -> Any:
        """按已解析 request 连接 storage，并完成样本绑定。"""

        from . import runtime as runtime_module

        storage = sample_set.storage
        if storage is None:
            storage = runtime_module.SampleSetStorage(sampleset=sample_set)
            sample_set.storage = storage
        connect_resolved = getattr(storage, "_connect_resolved", None)
        if callable(connect_resolved):
            connect_resolved(
                base_dir=request.base_dir,
                mode=request.mode,
                storage_scheme=request.storage_scheme,
                data_options=request.data_options,
                name_resolver=request.name_resolver,
                set_filename=request.set_filename,
            )
        else:
            storage.connect(
                request.base_dir,
                mode=request.mode,
                storage_scheme=request.storage_scheme,
                data_options=request.data_options,
                name_resolver=request.name_resolver,
                set_filename=request.set_filename,
            )
        bind_samples(sample_set)
        return storage

    def _execute_with_connected_sample_set_storage(
        self,
        sample_set: SampleSetBase[Any],
        *,
        request: _ResolvedSampleSetConnectRequest | None,
        operation: Callable[[Any], object],
    ) -> object:
        """确保 storage 已连接后执行批量动作，并在结束后重绑样本。"""

        storage = self._ensure_sample_set_storage(sample_set, request=request)
        result = operation(storage)
        bind_samples(sample_set)
        return result

    @overload
    def load(
        self,
        path: str | Path,
        *,
        domain: Literal[SampleDomain.DEFAULT],
        scheme: StorageScheme | None = None,
        data_options: dict[str, Any] | None = None,
        set_filename: str | None = None,
    ) -> SampleSet: ...

    @overload
    def load(
        self,
        path: str | Path,
        *,
        domain: Literal[SampleDomain.VIBRATION_TEST],
        scheme: StorageScheme | None = None,
        data_options: dict[str, Any] | None = None,
        set_filename: str | None = None,
    ) -> VibrationTestSampleSet: ...

    def load(
        self,
        path: str | Path,
        *,
        domain: SampleDomain,
        scheme: StorageScheme | None = None,
        data_options: dict[str, Any] | None = None,
        progress_callback: Callable[[int, int], None] | None = None,
        show_progress: bool | None = None,
        set_filename: str | None = None,
        categories: list[str] | None = None,
        strict: bool | None = None,
        filter: Callable[[Any], bool] | None = None,
        workers: int = 1,
        chunk_size: int = 256,
    ) -> SampleSetBase[Any]:
        """按规范路径加载样本集。"""

        resolved_domain = require_sample_domain(domain)
        path_obj = Path(path)
        sample_set_cls = get_sample_set_class(resolved_domain)
        actual_scheme = resolve_sample_set_scheme_for_read(path_obj, requested_scheme=scheme)
        logger.info(
            "load_sample_set request: path=%s, domain=%s, scheme=%s, workers=%s, chunk_size=%s, strict=%s, "
            "categories=%s, set_filename=%s, data_options=%s",
            path_obj,
            resolved_domain.value,
            summarize_sample_set_scheme(actual_scheme),
            workers,
            chunk_size,
            strict,
            summarize_sample_set_categories(categories),
            set_filename,
            summarize_sample_set_data_options(data_options),
        )
        try:
            result = sample_set_cls.from_samples(
                None,
                sample_domain=resolved_domain,
            )
            category_resolver = getattr(result, "_categories_to_fields", None)
            runtime_categories: list[str] | None = []
            if callable(category_resolver):
                category_resolver(categories, load_mode=SampleLoadMode.LAZY)
            result = self.load_sample_set_runtime(
                result,
                path=path_obj,
                storage_scheme=actual_scheme,
                data_options=data_options,
                progress_callback=progress_callback,
                show_progress=show_progress,
                categories=runtime_categories,
                strict=strict,
                filter=filter,
                workers=workers,
                chunk_size=chunk_size,
                set_filename=set_filename,
            )
            for sample in result.values():
                if hasattr(sample, "_set_load_mode_internal"):
                    sample._set_load_mode_internal(SampleLoadMode.LAZY)
            result.storage_dirty = False
        except Exception:
            logger.exception("load_sample_set failed")
            raise
        logger.info("load_sample_set done: path=%s, domain=%s", path_obj, resolved_domain.value)
        return result

    def connect_sample_set_runtime(
        self,
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
        """连接样本集存储。"""

        request = _resolve_sample_set_connect_request(
            base_dir,
            options=options,
            mode=mode,
            storage_scheme=storage_scheme,
            data_options=data_options,
            name_resolver=name_resolver,
            set_filename=set_filename,
        )
        logger.info(
            "connect_sample_set request: base_dir=%s, mode=%s, storage_scheme=%s, set_filename=%s, "
            "name_resolver=%s, data_options=%s",
            request.base_dir,
            request.mode.value,
            request.storage_scheme.name,
            request.set_filename,
            "enabled" if request.name_resolver is not None else "disabled",
            summarize_sample_set_data_options(request.data_options),
        )
        try:
            self._connect_resolved_sample_set_storage(sample_set, request)
        except Exception:
            logger.exception("connect_sample_set failed")
            raise
        logger.info(
            "connect_sample_set done: base_dir=%s, mode=%s, storage_scheme=%s, set_filename=%s",
            request.base_dir,
            request.mode.value,
            request.storage_scheme.name,
            request.set_filename,
        )
        return sample_set

    def save_sample_set_runtime(
        self,
        sample_set: SampleSetBase[Any],
        path: str | Path | None = None,
        *,
        mode: StorageMode | None = None,
        storage_scheme: StorageScheme | None = None,
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
    ) -> SampleSetBase[Any]:
        """保存样本集及其样本。"""

        logger.info(
            "save_sample_set request: path=%s, mode=%s, storage_scheme=%s, workers=%s, chunk_size=%s, strict=%s, "
            "categories=%s, set_filename=%s, data_options=%s",
            path,
            getattr(mode, "value", mode),
            summarize_sample_set_scheme(storage_scheme)
            if isinstance(storage_scheme, StorageScheme)
            else storage_scheme,
            workers,
            chunk_size,
            strict,
            summarize_sample_set_categories(categories),
            set_filename,
            summarize_sample_set_data_options(data_options),
        )
        try:
            request = self._resolve_storage_request_for_path(
                path,
                default_mode=mode or StorageMode.CREATE,
                storage_scheme=storage_scheme,
                data_options=data_options,
                name_resolver=name_resolver,
                set_filename=set_filename,
                for_read=False,
            )
            effective_strict = sample_set.strict if strict is None else strict
            self._execute_with_connected_sample_set_storage(
                sample_set,
                request=request,
                operation=lambda storage: storage.save_all(
                    progress_callback=progress_callback,
                    show_progress=show_progress,
                    categories=categories,
                    strict=effective_strict,
                    filter=filter,
                    workers=workers,
                    chunk_size=chunk_size,
                ),
            )
        except Exception:
            logger.exception("save_sample_set failed")
            raise
        logger.info("save_sample_set done: path=%s", path)
        return sample_set

    def load_sample_set_runtime(
        self,
        sample_set: SampleSetBase[Any],
        path: str | Path | None = None,
        *,
        mode: StorageMode | None = None,
        storage_scheme: StorageScheme | None = None,
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
        """从已连接存储或目标路径加载样本集。"""

        logger.info(
            "load_sample_set request: path=%s, mode=%s, storage_scheme=%s, workers=%s, chunk_size=%s, strict=%s, "
            "categories=%s, set_filename=%s, data_options=%s",
            path,
            getattr(mode, "value", mode),
            summarize_sample_set_scheme(storage_scheme)
            if isinstance(storage_scheme, StorageScheme)
            else storage_scheme,
            workers,
            chunk_size,
            strict,
            summarize_sample_set_categories(categories),
            set_filename,
            summarize_sample_set_data_options(data_options),
        )
        try:
            request = self._resolve_storage_request_for_path(
                path,
                default_mode=mode or StorageMode.OPEN,
                storage_scheme=storage_scheme,
                data_options=data_options,
                set_filename=set_filename,
                for_read=True,
            )
            effective_strict = sample_set.strict if strict is None else strict
            self._execute_with_connected_sample_set_storage(
                sample_set,
                request=request,
                operation=lambda storage: storage.load_all(
                    progress_callback=progress_callback,
                    show_progress=show_progress,
                    categories=categories,
                    strict=effective_strict,
                    filter=filter,
                    workers=workers,
                    chunk_size=chunk_size,
                ),
            )
        except Exception:
            logger.exception("load_sample_set failed")
            raise
        logger.info("load_sample_set done: path=%s", path)
        return sample_set

    def save_all_samples_runtime(
        self,
        sample_set: SampleSetBase[Any],
        **kwargs: Any,
    ) -> dict[str, Exception]:
        """批量保存样本集中的全部样本。"""

        if sample_set.storage is None:
            raise RuntimeError("样本集尚未连接存储，请先调用 connect_storage()")
        logger.info(
            "save_all_samples request: total=%s, workers=%s, chunk_size=%s, strict=%s, storage_scheme=%s, categories=%s",
            len(sample_set),
            kwargs.get("workers", 1),
            kwargs.get("chunk_size", 256),
            kwargs.get("strict"),
            summarize_sample_set_scheme(getattr(sample_set.storage, "storage_scheme", None)),
            summarize_sample_set_categories(kwargs.get("categories")),
        )
        try:
            result = cast(
                dict[str, Exception],
                self._execute_with_connected_sample_set_storage(
                    sample_set,
                    request=None,
                    operation=lambda storage: storage.save_all(**kwargs),
                ),
            )
        except Exception:
            logger.exception("save_all_samples failed")
            raise
        logger.info("save_all_samples done: fail=%s", len(result))
        return result

    def load_all_samples_runtime(
        self,
        sample_set: SampleSetBase[Any],
        **kwargs: Any,
    ) -> dict[str, Exception]:
        """批量加载样本集中的全部样本。"""

        if sample_set.storage is None:
            raise RuntimeError("样本集尚未连接存储，请先调用 connect_storage()")
        logger.info(
            "load_all_samples request: total=%s, workers=%s, chunk_size=%s, strict=%s, storage_scheme=%s, categories=%s",
            len(sample_set),
            kwargs.get("workers", 1),
            kwargs.get("chunk_size", 256),
            kwargs.get("strict", sample_set.strict),
            summarize_sample_set_scheme(getattr(sample_set.storage, "storage_scheme", None)),
            summarize_sample_set_categories(kwargs.get("categories")),
        )
        try:
            if kwargs.get("strict") is None:
                kwargs["strict"] = sample_set.strict
            result = cast(
                dict[str, Exception],
                self._execute_with_connected_sample_set_storage(
                    sample_set,
                    request=None,
                    operation=lambda storage: storage.load_all(**kwargs),
                ),
            )
        except Exception:
            logger.exception("load_all_samples failed")
            raise
        logger.info("load_all_samples done: fail=%s", len(result))
        return result

    def organize_sample_set_storage_runtime(
        self,
        sample_set: SampleSetBase[Any],
    ) -> SampleSetBase[Any]:
        """整理样本集存储目录。"""

        if sample_set.storage is None:
            raise RuntimeError("样本集尚未连接存储，请先调用 connect_storage()")
        logger.info("organize_sample_set_storage request")
        try:
            self._execute_with_connected_sample_set_storage(
                sample_set,
                request=None,
                operation=lambda storage: storage.organize(),
            )
        except Exception:
            logger.exception("organize_sample_set_storage failed")
            raise
        logger.info("organize_sample_set_storage done")
        return sample_set
