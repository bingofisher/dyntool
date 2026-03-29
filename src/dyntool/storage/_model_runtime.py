"""模型与元数据存储运行时实现。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from ..domain.metadata import MetadataBase
from ..domain.models import DataModelBase
from ..infrastructure import persistence as persistence_runtime
from ._runtime_common import MetadataT, ModelT, infer_model_format, logger


class _ModelStorageRuntimeMixin:
    """封装模型与元数据存储行为。"""

    @staticmethod
    def infer_model_format(path: str | Path) -> str:
        """根据路径后缀推断模型存储格式。"""

        return infer_model_format(path)

    def save_model_runtime(
        self,
        model: DataModelBase,
        path: str | Path,
        *,
        fmt: str = "h5",
        **options: Any,
    ) -> Path:
        """保存模型文件。"""

        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        logger.info("save_model request")
        try:
            persistence_runtime.save(target, model, fmt=fmt, **options)
        except Exception:
            logger.exception("save_model failed")
            raise
        logger.info("save_model done")
        return target

    def load_model_runtime(
        self,
        model_type: type[ModelT],
        path: str | Path,
        *,
        fmt: str = "h5",
        strict: bool | None = None,
        **options: Any,
    ) -> ModelT:
        """加载模型文件。"""

        target = Path(path)
        logger.info("load_model request")
        try:
            result = cast(
                ModelT,
                persistence_runtime.load(
                    target,
                    fmt=fmt,
                    category=model_type.category,
                    strict=getattr(model_type, "strict", True) if strict is None else strict,
                    **options,
                ),
            )
        except Exception:
            logger.exception("load_model failed")
            raise
        logger.info("load_model done")
        return result

    def inspect_model_units_runtime(
        self,
        model_type: type[DataModelBase],
        path: str | Path,
        *,
        fmt: str = "h5",
        strict: bool | None = None,
        **options: Any,
    ) -> dict[str, str]:
        """检查模型文件中的单位信息。"""

        target = Path(path)
        logger.info("inspect_model_units request")
        try:
            result = cast(
                dict[str, str],
                persistence_runtime.inspect(
                    target,
                    fmt=fmt,
                    category=model_type.category,
                    strict=getattr(model_type, "strict", True) if strict is None else strict,
                    **options,
                ),
            )
        except Exception:
            logger.exception("inspect_model_units failed")
            raise
        logger.info("inspect_model_units done")
        return result

    @staticmethod
    def save_metadata(metadata: MetadataBase, path: str | Path) -> Path:
        """保存元数据 JSON 文件。"""

        target = Path(path)
        logger.info("save_metadata request")
        try:
            metadata.to_json(target)
        except Exception:
            logger.exception("save_metadata failed")
            raise
        logger.info("save_metadata done")
        return target

    @staticmethod
    def load_metadata(path: str | Path, metadata_type: type[MetadataT]) -> MetadataT:
        """加载元数据 JSON 文件。"""

        logger.info("load_metadata request")
        try:
            result = cast(MetadataT, metadata_type.from_json(path))
        except Exception:
            logger.exception("load_metadata failed")
            raise
        logger.info("load_metadata done")
        return result
