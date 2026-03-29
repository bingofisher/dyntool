"""样本集存储运行时实现。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Literal, cast, overload

from ..domain.enums import SampleDomain
from ..domain.samples import SampleSet, SampleSetBase, VibrationTestSampleSet
from ..domain.samples.factories import get_sample_set_class, require_sample_domain
from ._runtime_common import (
    bind_samples,
    infer_sample_set_scheme,
    logger,
    require_mode,
    require_scheme,
    resolve_sample_set_connect_target,
)
from .types import NameResolver, StorageConnectOptions, StorageMode, StorageScheme


class _SampleSetStorageRuntimeMixin:
    """封装样本集及批量样本存储行为。"""

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
        logger.info("load_sample_set request")
        try:
            result = sample_set_cls.from_storage(
                path_obj,
                sample_domain=resolved_domain,
                storage_scheme=scheme or infer_sample_set_scheme(path_obj),
                data_options=data_options,
                categories=categories,
                strict=strict,
                filter=filter,
                workers=workers,
                chunk_size=chunk_size,
                set_filename=set_filename,
            )
        except Exception:
            logger.exception("load_sample_set failed")
            raise
        logger.info("load_sample_set done")
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
        actual_scheme = require_scheme(resolved_scheme or StorageScheme.SAMPLE_DIR)
        logger.info("connect_sample_set request")
        try:
            from . import runtime as runtime_module

            storage = sample_set.storage
            if storage is None:
                storage = runtime_module.SampleSetStorage(sampleset=sample_set)
                sample_set.storage = storage
            storage.connect(
                resolved_base_dir,
                mode=actual_mode,
                storage_scheme=actual_scheme,
                data_options=resolved_data_options,
                name_resolver=resolved_name_resolver,
                set_filename=resolved_set_filename,
            )
            bind_samples(sample_set)
        except Exception:
            logger.exception("connect_sample_set failed")
            raise
        logger.info("connect_sample_set done")
        return sample_set

    def save_sample_set_runtime(
        self,
        sample_set: SampleSetBase[Any],
        path: str | Path | None = None,
        *,
        mode: StorageMode | None = None,
        storage_scheme: StorageScheme | None = None,
        data_options: dict[str, Any] | None = None,
        categories: list[str] | None = None,
        strict: bool | None = None,
        filter: Callable[[Any], bool] | None = None,
        workers: int = 1,
        chunk_size: int = 256,
        name_resolver: NameResolver | None = None,
        set_filename: str | None = None,
    ) -> SampleSetBase[Any]:
        """保存样本集及其样本。"""

        logger.info("save_sample_set request")
        try:
            if path is not None:
                target = Path(path)
                actual_scheme = require_scheme(storage_scheme or infer_sample_set_scheme(target))
                base_dir, actual_set_filename = resolve_sample_set_connect_target(
                    target,
                    actual_scheme,
                    set_filename=set_filename,
                )
                self.connect_sample_set_runtime(
                    sample_set,
                    base_dir,
                    mode=mode or StorageMode.CREATE,
                    storage_scheme=actual_scheme,
                    data_options=data_options,
                    name_resolver=name_resolver,
                    set_filename=actual_set_filename,
                )
            if sample_set.storage is None:
                raise RuntimeError("样本集尚未连接存储，请先调用 connect_storage()")
            effective_strict = sample_set.strict if strict is None else strict
            sample_set.storage.save_all(
                categories=categories,
                strict=effective_strict,
                filter=filter,
                workers=workers,
                chunk_size=chunk_size,
            )
            bind_samples(sample_set)
        except Exception:
            logger.exception("save_sample_set failed")
            raise
        logger.info("save_sample_set done")
        return sample_set

    def load_sample_set_runtime(
        self,
        sample_set: SampleSetBase[Any],
        path: str | Path | None = None,
        *,
        mode: StorageMode | None = None,
        storage_scheme: StorageScheme | None = None,
        data_options: dict[str, Any] | None = None,
        categories: list[str] | None = None,
        strict: bool | None = None,
        filter: Callable[[Any], bool] | None = None,
        workers: int = 1,
        chunk_size: int = 256,
        set_filename: str | None = None,
    ) -> SampleSetBase[Any]:
        """从已连接存储或目标路径加载样本集。"""

        logger.info("load_sample_set request")
        try:
            if path is not None:
                target = Path(path)
                actual_scheme = require_scheme(storage_scheme or infer_sample_set_scheme(target))
                base_dir, actual_set_filename = resolve_sample_set_connect_target(
                    target,
                    actual_scheme,
                    set_filename=set_filename,
                )
                self.connect_sample_set_runtime(
                    sample_set,
                    base_dir,
                    mode=mode or StorageMode.OPEN,
                    storage_scheme=actual_scheme,
                    data_options=data_options,
                    set_filename=actual_set_filename,
                )
            if sample_set.storage is None:
                raise RuntimeError("样本集尚未连接存储，请先调用 connect_storage()")
            effective_strict = sample_set.strict if strict is None else strict
            sample_set.storage.load_all(
                categories=categories,
                strict=effective_strict,
                filter=filter,
                workers=workers,
                chunk_size=chunk_size,
            )
            bind_samples(sample_set)
        except Exception:
            logger.exception("load_sample_set failed")
            raise
        logger.info("load_sample_set done")
        return sample_set

    def save_all_samples_runtime(
        self,
        sample_set: SampleSetBase[Any],
        **kwargs: Any,
    ) -> dict[str, Exception]:
        """批量保存样本集中的全部样本。"""

        if sample_set.storage is None:
            raise RuntimeError("样本集尚未连接存储，请先调用 connect_storage()")
        logger.info("save_all_samples request")
        try:
            result = cast(dict[str, Exception], sample_set.storage.save_all(**kwargs))
            bind_samples(sample_set)
        except Exception:
            logger.exception("save_all_samples failed")
            raise
        logger.info("save_all_samples done")
        return result

    def load_all_samples_runtime(
        self,
        sample_set: SampleSetBase[Any],
        **kwargs: Any,
    ) -> dict[str, Exception]:
        """批量加载样本集中的全部样本。"""

        if sample_set.storage is None:
            raise RuntimeError("样本集尚未连接存储，请先调用 connect_storage()")
        logger.info("load_all_samples request")
        try:
            if kwargs.get("strict") is None:
                kwargs["strict"] = sample_set.strict
            result = cast(dict[str, Exception], sample_set.storage.load_all(**kwargs))
            bind_samples(sample_set)
        except Exception:
            logger.exception("load_all_samples failed")
            raise
        logger.info("load_all_samples done")
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
            sample_set.storage.organize()
            bind_samples(sample_set)
        except Exception:
            logger.exception("organize_sample_set_storage failed")
            raise
        logger.info("organize_sample_set_storage done")
        return sample_set
