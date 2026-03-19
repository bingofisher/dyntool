"""独立存储模块的内部运行时实现。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Literal, TypeVar, cast, overload

from ..domain.enums import SampleDomain
from ..domain.metadata import MetadataBase
from ..domain.models import DataModelBase
from ..domain.samples import (
    SampleBaseModel,
    SampleSet,
    SampleSetBase,
    VibrationTestSampleSet,
)
from ..domain.samples.factories import get_sample_set_class, require_sample_domain
from ..infrastructure import persistence as persistence_runtime
from ..infrastructure.sample_set_storage import SampleSetStorage
from ..logging import get_logger
from .types import NameResolver, StorageConnectOptions, StorageMode, StorageScheme

logger = get_logger("storage")

ModelT = TypeVar("ModelT", bound=DataModelBase)
MetadataT = TypeVar("MetadataT", bound=MetadataBase)
SampleT = TypeVar("SampleT", bound=SampleBaseModel)

_H5_SUFFIXES = {".h5", ".hdf5", ".hdf"}


class StorageRuntime:
    """统一封装模型、样本和样本集存储流程的运行时门面。

    Attributes:
        该门面通过类变量 `scheme` 和 `mode` 暴露标准存储方案与存储模式枚举，
        供上层代码在不额外导入类型模块时复用一致的枚举入口。
    """

    #: 存储方案枚举入口，供上层代码复用 `StorageScheme` 成员。
    scheme = StorageScheme
    #: 存储模式枚举入口，供上层代码复用 `StorageMode` 成员。
    mode = StorageMode

    @staticmethod
    def infer_model_format(path: str | Path) -> str:
        """根据路径后缀推断模型存储格式。"""

        return "h5" if Path(path).suffix.lower() in _H5_SUFFIXES else "csv"

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
        """按规范路径加载样本集。

        Args:
            path: 样本集目录或集合级 HDF5 文件路径。
            domain: 样本域枚举，用于选择具体样本集类型。
            scheme: 可选存储方案；为空时根据路径后缀自动推断。
            data_options: 存储上下文数据选项，例如属性载荷格式和精度设置。
            set_filename: 当目标为集合级 HDF5 时使用的文件名。
            categories: 仅加载指定槽位；为空时加载全部可存储槽位。
            strict: 严格模式；为空时交由样本集类自己的 `from_storage()` 默认行为决定。
            filter: 样本过滤函数；返回 `True` 的样本才会被保留。
            workers: 批量加载并发数。
            chunk_size: 在途任务窗口上限控制参数。

        Returns:
            SampleSetBase[Any]: 与 `domain` 对应的样本集实例。

        Raises:
            Exception: 样本集构造、连接或批量加载过程中产生的异常会原样上传。

        Notes:
            `scheme` 为空时，`.h5/.hdf5/.hdf` 后缀会被解释为 `StorageScheme.SET_H5`，
            其它路径默认解释为目录方案 `StorageScheme.SAMPLE_DIR`。
        """

        resolved_domain = require_sample_domain(domain)
        path_obj = Path(path)
        sample_set_cls = get_sample_set_class(resolved_domain)
        logger.info("load_sample_set request")
        try:
            result = sample_set_cls.from_storage(
                path_obj,
                sample_domain=resolved_domain,
                storage_scheme=scheme or self._infer_scheme(path_obj),
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
        """连接样本集存储。

        Args:
            sample_set: 待连接的样本集对象。
            base_dir: 存储根目录或样本集目标路径。
            options: 聚合连接参数对象；若提供，则可作为后续显式参数的默认值来源。
            mode: 显式连接模式，优先于 `options.mode`。
            storage_scheme: 显式存储方案，优先于 `options.scheme`。
            data_options: 显式数据选项，优先于 `options.data_options`。
            name_resolver: 显式样本命名解析器，优先于 `options.name_resolver`。
            set_filename: 显式集合级文件名，优先于 `options.set_filename`。

        Returns:
            SampleSetBase[Any]: 已建立存储绑定的样本集对象。

        Raises:
            TypeError: `mode` 或 `storage_scheme` 不是对应枚举对象时抛出。
            Exception: 底层连接或目录准备失败时抛出的异常。

        Notes:
            显式参数优先级高于 `options` 中的同名字段。
            未显式提供时默认使用 `StorageMode.OPEN` 和 `StorageScheme.SAMPLE_DIR`。
            连接成功后会为样本集中的每个样本重新绑定 `_storage_set`。
        """

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
        actual_mode = self._require_mode(resolved_mode or StorageMode.OPEN)
        actual_scheme = self._require_scheme(resolved_scheme or StorageScheme.SAMPLE_DIR)
        logger.info("connect_sample_set request")
        try:
            storage = sample_set.storage
            if storage is None:
                storage = SampleSetStorage(sampleset=sample_set)
                sample_set.storage = storage
            storage.connect(
                resolved_base_dir,
                mode=actual_mode,
                storage_scheme=actual_scheme,
                data_options=resolved_data_options,
                name_resolver=resolved_name_resolver,
                set_filename=resolved_set_filename,
            )
            self._bind_samples(sample_set)
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
        """保存样本集及其样本。

        Args:
            sample_set: 待保存的样本集对象。
            path: 可选目标路径；提供时先建立或重建连接。
            mode: 可选连接模式。
            storage_scheme: 可选存储方案；为空时若提供了 `path` 会按路径自动推断。
            data_options: 存储上下文数据选项。
            categories: 仅保存指定槽位。
            strict: 为 `True` 时遇到首个样本保存错误立即终止。
            filter: 样本过滤函数。
            workers: 批量保存并发数。
            chunk_size: 在途任务窗口上限控制参数。
            name_resolver: 可选样本命名解析器。
            set_filename: 集合级 HDF5 文件名。

        Returns:
            SampleSetBase[Any]: 保存后的样本集对象。

        Raises:
            RuntimeError: 在未连接存储且未提供 `path` 时抛出。
            TypeError: 存储方案或连接模式类型不合法时抛出。
            Exception: 批量保存过程中产生的异常。

        Notes:
            当 `path` 指向 HDF5 文件时，会自动切换到 `StorageScheme.SET_H5`，
            并把连接根目录解释为该文件的父目录，文件名解释为 `set_filename`。
            实际批量保存由 `sample_set.storage.save_all()` 执行。
        """

        logger.info("save_sample_set request")
        try:
            if path is not None:
                target = Path(path)
                actual_scheme = self._require_scheme(storage_scheme or self._infer_scheme(target))
                base_dir, actual_set_filename = self._resolve_sample_set_connect_target(
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
                raise RuntimeError("样本集尚未连接存储，请先调用 connect_storage()。")
            effective_strict = sample_set.strict if strict is None else strict
            sample_set.storage.save_all(
                categories=categories,
                strict=effective_strict,
                filter=filter,
                workers=workers,
                chunk_size=chunk_size,
            )
            self._bind_samples(sample_set)
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
        """从已连接存储或目标路径加载样本集。

        Args:
            sample_set: 目标样本集对象。
            path: 可选来源路径；提供时先建立连接。
            mode: 可选连接模式。
            storage_scheme: 可选存储方案；为空时若提供了 `path` 会按路径自动推断。
            data_options: 存储上下文数据选项。
            categories: 仅加载指定槽位。
            strict: 严格模式；为空时使用 `sample_set.strict`。
            filter: 样本过滤函数。
            workers: 批量加载并发数。
            chunk_size: 在途任务窗口上限控制参数。
            set_filename: 集合级 HDF5 文件名。

        Returns:
            SampleSetBase[Any]: 已加载内容的样本集对象。

        Raises:
            RuntimeError: 在未连接存储且未提供 `path` 时抛出。
            TypeError: 存储方案或连接模式类型不合法时抛出。
            Exception: 批量加载过程中产生的异常。

        Notes:
            当 `strict` 为 `None` 时，会回退到样本集自身的 `strict` 设置。
            实际批量加载由 `sample_set.storage.load_all()` 完成，随后会重新绑定样本与样本集。
        """

        logger.info("load_sample_set_runtime request")
        try:
            if path is not None:
                target = Path(path)
                actual_scheme = self._require_scheme(storage_scheme or self._infer_scheme(target))
                base_dir, actual_set_filename = self._resolve_sample_set_connect_target(
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
                raise RuntimeError("样本集尚未连接存储，请先调用 connect_storage()。")
            effective_strict = sample_set.strict if strict is None else strict
            sample_set.storage.load_all(
                categories=categories,
                strict=effective_strict,
                filter=filter,
                workers=workers,
                chunk_size=chunk_size,
            )
            self._bind_samples(sample_set)
        except Exception:
            logger.exception("load_sample_set_runtime failed")
            raise
        logger.info("load_sample_set_runtime done")
        return sample_set

    def save_all_samples_runtime(
        self,
        sample_set: SampleSetBase[Any],
        **kwargs: Any,
    ) -> dict[str, Exception]:
        """批量保存样本集中的全部样本。

        Args:
            sample_set: 待保存的样本集对象。
            **kwargs: 透传给 `sample_set.storage.save_all()` 的批量保存参数。

        Returns:
            dict[str, Exception]: 保存失败样本的 `uid -> 异常` 映射。

        Raises:
            RuntimeError: 样本集尚未连接存储时抛出。
            Exception: 底层批量保存过程中产生的异常。

        Notes:
            常用 `**kwargs` 包括 `categories`、`strict`、`filter`、`workers`、`chunk_size`。
            保存完成后会重新绑定样本到样本集的引用，确保后续单样本操作仍能复用当前存储。
        """

        if sample_set.storage is None:
            raise RuntimeError("样本集尚未连接存储，请先调用 connect_storage()。")
        logger.info("save_all_samples request")
        try:
            result = cast(dict[str, Exception], sample_set.storage.save_all(**kwargs))
            self._bind_samples(sample_set)
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
        """批量加载样本集中的全部样本。

        Args:
            sample_set: 目标样本集对象。
            **kwargs: 透传给 `sample_set.storage.load_all()` 的批量加载参数。

        Returns:
            dict[str, Exception]: 加载失败样本的 `uid -> 异常` 映射。

        Raises:
            RuntimeError: 样本集尚未连接存储时抛出。
            Exception: 底层批量加载过程中产生的异常。

        Notes:
            常用 `**kwargs` 包括 `categories`、`strict`、`filter`、`workers`、`chunk_size`
            和 `progress_callback`。如果调用方未提供 `strict`，这里会自动回退到 `sample_set.strict`。
        """

        if sample_set.storage is None:
            raise RuntimeError("样本集尚未连接存储，请先调用 connect_storage()。")
        logger.info("load_all_samples request")
        try:
            if kwargs.get("strict") is None:
                kwargs["strict"] = sample_set.strict
            result = cast(dict[str, Exception], sample_set.storage.load_all(**kwargs))
            self._bind_samples(sample_set)
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
            raise RuntimeError("样本集尚未连接存储，请先调用 connect_storage()。")
        logger.info("organize_sample_set_storage request")
        try:
            sample_set.storage.organize()
            self._bind_samples(sample_set)
        except Exception:
            logger.exception("organize_sample_set_storage failed")
            raise
        logger.info("organize_sample_set_storage done")
        return sample_set

    def connect_sample_runtime(
        self,
        sample: SampleBaseModel,
        base_dir: str | Path,
        **kwargs: Any,
    ) -> SampleBaseModel:
        """连接单个样本的存储。

        Args:
            sample: 待连接的样本对象。
            base_dir: 样本根目录、单样本文件路径或容器目录。
            **kwargs: 支持键包括 `mode`、`storage_scheme`、`data_options`、
                `name_resolver`、`set_filename`。这些键会先在 runtime 层完成默认值
                补全，再转发给样本集存储连接逻辑。
        """

        sample_set = sample._storage_set
        if sample_set is None:
            sample_set = sample.__class__.sample_set_type()({sample.uid: sample})
            sample._storage_set = sample_set
        else:
            sample_set[sample.uid] = sample
        if kwargs.get("storage_scheme") is None and kwargs.get("scheme") is None:
            kwargs["storage_scheme"] = self._infer_sample_scheme(Path(base_dir))
        self.connect_sample_set_runtime(sample_set, base_dir, **kwargs)
        sample._storage_set = sample_set
        return sample

    def save_sample_runtime(
        self,
        sample: SampleT,
        path: str | Path | None = None,
        **kwargs: Any,
    ) -> SampleT:
        """保存单个样本。

        Args:
            sample: 待保存的样本对象。
            path: 可选的显式目标路径；为 `None` 时要求样本已连接存储。
            **kwargs: 支持键包括 `mode`、`storage_scheme`、`data_options`、
                `name_resolver`、`set_filename`、`categories`。`categories` 用于选
                择要写回的顶层槽位；其余键会在需要重建连接时转发给
                `connect_sample_runtime()`。
        """

        if path is not None:
            mode = kwargs.pop("mode", StorageMode.CREATE)
            self.connect_sample_runtime(sample, path, mode=mode, **kwargs)
        if sample._storage_set is None or sample._storage_set.storage is None:
            raise RuntimeError("样本尚未连接存储，请先调用 connect_storage()。")
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
        """加载单个样本。

        Args:
            sample: 待加载的样本对象。
            path: 可选的显式来源路径；为 `None` 时从已连接存储读取。
            **kwargs: 支持键包括 `mode`、`storage_scheme`、`data_options`、
                `name_resolver`、`set_filename`、`categories`。`categories` 用于选
                择要恢复的顶层槽位；其余键会在需要重建连接时转发给
                `connect_sample_runtime()`。
        """

        if path is not None:
            mode = kwargs.pop("mode", StorageMode.OPEN)
            self.connect_sample_runtime(sample, path, mode=mode, **kwargs)
        return self.reload_sample_runtime(
            sample,
            categories=kwargs.pop("categories", None),
        )

    def reload_sample_runtime(
        self,
        sample: SampleT,
        *,
        categories: list[str] | None = None,
    ) -> SampleT:
        """从已连接存储中重新加载单个样本。"""

        if sample._storage_set is None or sample._storage_set.storage is None:
            raise RuntimeError("样本尚未连接存储，请先调用 connect_storage()。")
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

    @staticmethod
    def _bind_samples(sample_set: SampleSetBase[Any]) -> None:
        """为样本集中的样本回填 `_storage_set` 绑定。"""

        for sample in sample_set.values():
            sample._storage_set = sample_set

    @staticmethod
    def _infer_scheme(path: Path) -> StorageScheme:
        """根据样本集路径推断存储方案。"""

        return StorageScheme.SET_H5 if path.suffix.lower() in _H5_SUFFIXES else StorageScheme.SAMPLE_DIR

    @staticmethod
    def _infer_sample_scheme(path: Path) -> StorageScheme:
        """根据单样本路径推断存储方案。"""

        suffix = path.suffix.lower()
        if suffix in _H5_SUFFIXES:
            return StorageScheme.SAMPLE_H5
        if suffix == ".json":
            return StorageScheme.SAMPLE_JSON
        return StorageScheme.SAMPLE_DIR

    @staticmethod
    def _resolve_sample_set_connect_target(
        path: Path,
        scheme: StorageScheme,
        *,
        set_filename: str | None,
    ) -> tuple[Path, str | None]:
        """解析样本集连接时的根目录和集合级文件名。"""

        if scheme is not StorageScheme.SET_H5:
            return path, set_filename
        if path.suffix.lower() in _H5_SUFFIXES:
            return path.parent, set_filename or path.name
        return path, set_filename

    @staticmethod
    def _require_scheme(scheme: StorageScheme | str) -> StorageScheme:
        """校验并返回存储方案枚举。"""

        if isinstance(scheme, StorageScheme):
            return scheme
        if isinstance(scheme, str):
            try:
                return StorageScheme(scheme)
            except ValueError as exc:
                raise TypeError("scheme 必须是 StorageScheme 枚举或其合法字符串值") from exc
        raise TypeError("scheme 必须是 StorageScheme 枚举或其合法字符串值")

    @staticmethod
    def _require_mode(mode: StorageMode | str) -> StorageMode:
        """校验并返回存储模式枚举。"""

        if isinstance(mode, StorageMode):
            return mode
        if isinstance(mode, str):
            try:
                return StorageMode(mode)
            except ValueError as exc:
                raise TypeError("mode 必须是 StorageMode 枚举或其合法字符串值") from exc
        raise TypeError("mode 必须是 StorageMode 枚举或其合法字符串值")


__all__ = ["StorageRuntime"]
