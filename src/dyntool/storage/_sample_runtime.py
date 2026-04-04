"""单样本存储运行时实现。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..domain.samples import SampleBaseModel
from ._runtime_common import SampleT, StorageMode, infer_sample_scheme, logger, resolve_sample_scheme_for_read


class _SampleStorageRuntimeMixin:
    """封装单样本存储行为。"""

    def connect_sample_runtime(
        self,
        sample: SampleBaseModel,
        base_dir: str | Path,
        **kwargs: Any,
    ) -> SampleBaseModel:
        """连接单个样本的存储。"""

        sample_set = sample._storage_set
        if sample_set is None:
            sample_set = sample.__class__.sample_set_type()({sample.uid: sample})
            sample._storage_set = sample_set
        else:
            sample_set[sample.uid] = sample
        if kwargs.get("storage_scheme") is None and kwargs.get("scheme") is None:
            kwargs["storage_scheme"] = infer_sample_scheme(Path(base_dir))
        elif Path(base_dir).exists():
            kwargs["storage_scheme"] = resolve_sample_scheme_for_read(
                Path(base_dir),
                requested_scheme=kwargs.get("storage_scheme") or kwargs.get("scheme"),
            )
        self.connect_sample_set_runtime(sample_set, base_dir, **kwargs)
        sample._storage_set = sample_set
        return sample

    def save_sample_runtime(
        self,
        sample: SampleT,
        path: str | Path | None = None,
        **kwargs: Any,
    ) -> SampleT:
        """保存单个样本。"""

        if path is not None:
            mode = kwargs.pop("mode", StorageMode.CREATE)
            self.connect_sample_runtime(sample, path, mode=mode, **kwargs)
        if sample._storage_set is None or sample._storage_set.storage is None:
            raise RuntimeError("样本尚未连接存储，请先调用 connect_storage()")
        logger.info("save_sample request")
        try:
            categories = kwargs.pop("categories", None)
            sample._storage_set[sample.uid] = sample
            sample._storage_set.storage.save_sample(sample, categories)
        except Exception:
            logger.exception("save_sample failed")
            raise
        logger.info("save_sample done")
        return sample

    def load_sample_runtime(
        self,
        sample: SampleT,
        path: str | Path | None = None,
        **kwargs: Any,
    ) -> SampleT:
        """加载单个样本。"""

        if path is not None:
            mode = kwargs.pop("mode", StorageMode.OPEN)
            self.connect_sample_runtime(sample, path, mode=mode, **kwargs)
        return self.reload_sample_runtime(sample, categories=kwargs.pop("categories", None))

    def reload_sample_runtime(
        self,
        sample: SampleT,
        *,
        categories: list[str] | None = None,
    ) -> SampleT:
        """从已连接存储中重新加载单个样本。"""

        if sample._storage_set is None or sample._storage_set.storage is None:
            raise RuntimeError("样本尚未连接存储，请先调用 connect_storage()")
        logger.info("load_sample request")
        try:
            loaded = sample._storage_set.storage.load_sample(sample.uid, categories)
            sample._replace_metadata(loaded.metadata)
            sample._restore_alias_internal(loaded.alias)
            sample._replace_data_vars_internal(loaded.data_vars.copy())
            sample._storage_set[sample.uid] = sample
        except Exception:
            logger.exception("load_sample failed")
            raise
        logger.info("load_sample done")
        return sample
