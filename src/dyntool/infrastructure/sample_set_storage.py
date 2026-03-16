"""样本集存储门面。"""

from __future__ import annotations

import shutil
from concurrent.futures import Future, ThreadPoolExecutor
from functools import wraps
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Self

from ..logging import get_logger
from ..storage.types import (
    NameResolver,
    StorageConnectOptions,
    StorageMode,
    StorageScheme,
    resolve_connect_options,
)
from .data_storage import DataStorage
from .persistence import RecoverableIOError
from .sample_set_storage_concurrency import drain_completed, submit_until_limit
from .sample_storage import SampleStorage
from .sample_storage_context import StorageContext
from .storage_constants import DEFAULT_SET_H5_FILENAME

if TYPE_CHECKING:
    from ..domain.samples.base import SampleBaseModel
    from ..domain.samples.sets import SampleSetBase

logger = get_logger("infrastructure.sample_storage")


class SampleSetStorage:
    """样本集存储门面，负责连接、批量保存、批量加载与目录整理。

    Attributes:
        sampleset: 当前绑定的样本集对象。
        base_dir: 已连接的存储根目录；未连接时为 `None`。
        storage_scheme: 当前生效的存储方案枚举。
        name_resolver: 样本文件名解析器。
        set_filename: 集合级 HDF5 文件名，仅在 `SET_H5` 方案下生效。
        data_options: 传给底层存储上下文的格式与精度选项。
        data_storage: 数据模型级持久化辅助对象。
    """

    def __init__(self, sampleset: "SampleSetBase") -> None:
        self.sampleset = sampleset
        self.base_dir: Path | None = None
        self._connected: bool = False
        self.storage_scheme: StorageScheme = StorageScheme.SAMPLE_DIR
        self.name_resolver: NameResolver | None = None
        self.set_filename: str = DEFAULT_SET_H5_FILENAME
        self.data_options: dict[str, Any] = {}
        self.data_storage = DataStorage()
        self._ctx: StorageContext | None = None
        self._sample_storage: SampleStorage | None = None

    def connect(
        self,
        base_dir: str | Path,
        *,
        options: StorageConnectOptions | None = None,
        mode: StorageMode | None = None,
        storage_scheme: StorageScheme | None = None,
        data_options: dict[str, Any] | None = None,
        name_resolver: NameResolver | None = None,
        set_filename: str | None = None,
    ) -> Self:
        """连接样本集存储目录并初始化内部上下文。

        Args:
            base_dir: 存储根目录。
            options: 面向调用方的聚合连接参数。
            mode: 显式连接模式，优先级高于 `options.mode`。
            storage_scheme: 显式存储方案，优先级高于 `options.scheme`。
            data_options: 显式数据选项，优先级高于 `options.data_options`。
            name_resolver: 显式命名解析器，优先级高于 `options.name_resolver`。
            set_filename: 显式集合级文件名，优先级高于 `options.set_filename`。

        Returns:
            Self: 当前存储门面对象，便于链式调用。

        Raises:
            FileNotFoundError: `mode` 为 `OPEN` 且路径不存在时抛出。
            NotADirectoryError: `mode` 为 `OPEN` 且目标路径不是目录时抛出。
            ValueError: `mode` 不属于受支持的连接模式时抛出。

        Notes:
            连接参数优先级为：显式关键字参数 > `options` 中对应字段 > 默认值。
            `RECREATE` 会删除原有目录或文件后重建，属于破坏性操作。
        """

        base_dir = Path(base_dir).resolve()
        resolved = resolve_connect_options(
            options=options,
            mode=mode,
            storage_scheme=storage_scheme,
            data_options=data_options,
            name_resolver=name_resolver,
            set_filename=set_filename,
            default_set_filename=DEFAULT_SET_H5_FILENAME,
        )
        resolved_mode = resolved.mode
        resolved_scheme = resolved.storage_scheme
        resolved_data_options = resolved.data_options
        resolved_name_resolver = resolved.name_resolver
        resolved_set_filename = resolved.set_filename

        logger.info(
            "connect sample-set storage: %s (mode=%s, storage_scheme=%s)",
            base_dir,
            resolved_mode,
            resolved_scheme,
        )
        if resolved_mode is StorageMode.RECREATE:
            if base_dir.exists():
                if base_dir.is_dir():
                    shutil.rmtree(base_dir)
                else:
                    base_dir.unlink()
            base_dir.mkdir(parents=True, exist_ok=True)
        elif resolved_mode is StorageMode.CREATE:
            base_dir.mkdir(parents=True, exist_ok=True)
        elif resolved_mode is StorageMode.OPEN:
            if not base_dir.exists():
                raise FileNotFoundError(f"存储目录不存在: {base_dir}")
            if not base_dir.is_dir():
                raise NotADirectoryError(f"目标路径不是目录: {base_dir}")
        else:
            raise ValueError("mode 必须是 StorageMode.OPEN、StorageMode.CREATE 或 StorageMode.RECREATE。")

        self.base_dir = base_dir
        self._connected = True
        self.storage_scheme = resolved_scheme
        self.data_options = resolved_data_options.copy() if resolved_data_options else {}
        self.name_resolver = resolved_name_resolver
        self.set_filename = resolved_set_filename
        self._ctx = StorageContext(
            self.sampleset,
            base_dir=base_dir,
            storage_scheme=resolved_scheme,
            data_options=self.data_options,
            name_resolver=resolved_name_resolver,
            set_filename=resolved_set_filename,
            data_storage=self.data_storage,
        )
        self._sample_storage = SampleStorage(self._ctx)
        logger.info(
            "sample-set storage ready: %s (mode=%s, storage_scheme=%s)",
            base_dir,
            resolved_mode,
            resolved_scheme,
        )
        return self

    @staticmethod
    def ensure_connected(method: Callable[..., Any]) -> Callable[..., Any]:
        """为要求已连接状态的方法添加连接校验。"""

        @wraps(method)
        def wrapper(self: "SampleSetStorage", *args: Any, **kwargs: Any) -> Any:
            if not self._connected or self.base_dir is None or self._sample_storage is None:
                raise RuntimeError("样本集存储尚未连接，请先调用 connect()")
            return method(self, *args, **kwargs)

        return wrapper

    def _require_sample_storage(self) -> SampleStorage:
        if self._sample_storage is None:
            raise RuntimeError("样本集存储尚未连接，请先调用 connect()")
        return self._sample_storage

    def _selected_items(
        self,
        filter: Callable[[SampleBaseModel], bool] | None = None,
    ) -> list[tuple[str, SampleBaseModel]]:
        if filter is None:
            return list(self.sampleset.items())
        return [(uid, sample) for uid, sample in self.sampleset.items() if filter(sample)]

    @staticmethod
    def _duplicate_uid_error(uid: str) -> ValueError:
        return ValueError(f"读取到重复 UID 的样本: {uid}")

    def _raise_or_collect_load_error(
        self,
        uid: str,
        error: Exception,
        *,
        strict: bool,
        errors: dict[str, Exception],
        pending: dict[Future[Any], str] | None = None,
    ) -> None:
        logger.error("加载样本失败 (UID=%s): %s", uid, error)
        errors[uid] = error
        if strict:
            if pending is not None:
                for pending_future in pending:
                    pending_future.cancel()
            raise RecoverableIOError(f"加载样本失败: {uid}") from error

    @ensure_connected
    def save_sample(self, sample: SampleBaseModel, categories: list[str] | None = None) -> None:
        """保存单个样本及其选定槽位。"""

        self._require_sample_storage().save(sample, categories)

    @ensure_connected
    def save_all(
        self,
        *,
        categories: list[str] | None = None,
        strict: bool = True,
        filter: Callable[[SampleBaseModel], bool] | None = None,
        workers: int = 1,
        chunk_size: int = 256,
    ) -> dict[str, Exception]:
        """批量保存样本集中的样本。

        Args:
            categories: 仅保存指定槽位；为空时保存全部可存储槽位。
            strict: 为 `True` 时遇到首个错误立即终止并抛异常。
            filter: 样本过滤函数，仅保存返回 `True` 的样本。
            workers: 并发保存线程数，至少为 1。
            chunk_size: 在途任务上限控制参数，至少为 1。

        Returns:
            dict[str, Exception]: 保存失败样本的 `uid -> 异常` 映射。

        Raises:
            ValueError: `workers` 或 `chunk_size` 小于 1 时抛出。
            RecoverableIOError: 严格模式下首个样本保存失败时抛出。

        Notes:
            `filter` 只影响本次批量保存，不会修改样本集本身内容。
            当 `workers > 1` 时，`chunk_size` 用于限制并发提交窗口，避免一次性压入过多任务。
        """

        if workers < 1:
            raise ValueError("workers 必须大于等于 1")
        if chunk_size < 1:
            raise ValueError("chunk_size 必须大于等于 1")
        selected_items = self._selected_items(filter)
        total = len(selected_items)
        logger.info("start saving samples: total=%s", total)
        ok = 0
        fail = 0
        errors: dict[str, Exception] = {}
        if workers == 1:
            for uid, sample in selected_items:
                try:
                    self.save_sample(sample, categories)
                    ok += 1
                except Exception as error:  # noqa: BLE001
                    logger.error("保存样本失败 (UID=%s): %s", uid, error)
                    fail += 1
                    errors[uid] = error
                    if strict:
                        raise RecoverableIOError(f"保存样本失败: {uid}") from error
        else:
            in_flight_limit = max(workers, chunk_size)
            tasks_iter = iter(selected_items)
            with ThreadPoolExecutor(max_workers=workers) as executor:
                pending: dict[Future[Any], str] = {}
                submit_until_limit(
                    executor,
                    pending,
                    tasks_iter,
                    lambda sample: self.save_sample(sample, categories),
                    limit=in_flight_limit,
                )
                while pending:
                    completed = drain_completed(pending)
                    for uid, future in completed:
                        try:
                            future.result()
                            ok += 1
                        except Exception as error:  # noqa: BLE001
                            logger.error("保存样本失败 (UID=%s): %s", uid, error)
                            fail += 1
                            errors[uid] = error
                            if strict:
                                for pending_future in pending:
                                    pending_future.cancel()
                                raise RecoverableIOError(f"保存样本失败: {uid}") from error
                    submit_until_limit(
                        executor,
                        pending,
                        tasks_iter,
                        lambda sample: self.save_sample(sample, categories),
                        limit=in_flight_limit,
                    )
        logger.info("save samples finished: ok=%s, fail=%s, total=%s", ok, fail, total)
        return errors

    @ensure_connected
    def load_sample(self, uid: str, categories: list[str] | None = None) -> SampleBaseModel:
        """读取单个样本及其选定槽位。"""

        return self._require_sample_storage().load(uid, categories)

    @ensure_connected
    def load_all(
        self,
        progress_callback: Callable[[int, int], None] | None = None,
        *,
        categories: list[str] | None = None,
        strict: bool = True,
        filter: Callable[[SampleBaseModel], bool] | None = None,
        workers: int = 1,
        chunk_size: int = 256,
    ) -> dict[str, Exception]:
        """批量加载样本集存储中的样本。

        Args:
            progress_callback: 可选进度回调，参数为 `(completed, total)`。
            categories: 仅加载指定槽位；为空时加载全部可存储槽位。
            strict: 为 `True` 时遇到首个错误立即终止并抛异常。
            filter: 样本过滤函数，仅保留返回 `True` 的样本。
            workers: 并发读取线程数，至少为 1。
            chunk_size: 在途任务上限控制参数，至少为 1。

        Returns:
            dict[str, Exception]: 加载失败样本的 `uid -> 异常` 映射。

        Raises:
            ValueError: `workers` 或 `chunk_size` 小于 1 时抛出。
            RecoverableIOError: 严格模式下首个样本读取失败或出现重复 UID 时抛出。

        Notes:
            当 `filter` 为 `None` 时，本方法会把样本集视为“全量替换模式”：
            先清空当前内存样本，再回填成功加载的样本；如果某个 `uid` 加载失败，
            会尽量保留原样本集里该 `uid` 的旧对象，避免完全丢失已有内存数据。
        """

        if workers < 1:
            raise ValueError("workers 必须大于等于 1")
        if chunk_size < 1:
            raise ValueError("chunk_size 必须大于等于 1")

        sample_storage = self._require_sample_storage()
        index = sample_storage.index()
        total = len(index)
        existing_samples = dict(self.sampleset.items())
        existing_uids = set(existing_samples)
        replace_mode = filter is None
        loaded_samples: dict[str, SampleBaseModel] = {}
        ok = 0
        fail = 0
        errors: dict[str, Exception] = {}

        def accept_loaded_sample(sample: SampleBaseModel) -> None:
            nonlocal ok, fail
            uid = sample.uid
            if filter is not None and not filter(sample):
                return
            if uid in existing_uids or uid in loaded_samples:
                fail += 1
                self._raise_or_collect_load_error(
                    uid,
                    self._duplicate_uid_error(uid),
                    strict=strict,
                    errors=errors,
                )
                return
            loaded_samples[uid] = sample
            ok += 1

        if workers == 1:
            for i, uid in enumerate(index.keys(), start=1):
                try:
                    accept_loaded_sample(sample_storage.load(uid, categories))
                except RecoverableIOError:
                    raise
                except Exception as error:  # noqa: BLE001
                    fail += 1
                    self._raise_or_collect_load_error(uid, error, strict=strict, errors=errors)
                if progress_callback is not None:
                    progress_callback(i, total)
        else:
            completed_count = 0
            in_flight_limit = max(workers, chunk_size)
            tasks_iter = ((uid, uid) for uid in index.keys())
            with ThreadPoolExecutor(max_workers=workers) as executor:
                pending: dict[Future[Any], str] = {}
                submit_until_limit(
                    executor,
                    pending,
                    tasks_iter,
                    lambda uid: sample_storage.load(uid, categories),
                    limit=in_flight_limit,
                )
                while pending:
                    completed = drain_completed(pending)
                    for uid, future in completed:
                        completed_count += 1
                        try:
                            accept_loaded_sample(future.result())
                        except RecoverableIOError:
                            raise
                        except Exception as error:  # noqa: BLE001
                            fail += 1
                            self._raise_or_collect_load_error(
                                uid,
                                error,
                                strict=strict,
                                errors=errors,
                                pending=pending,
                            )
                        if progress_callback is not None:
                            progress_callback(completed_count, total)
                    submit_until_limit(
                        executor,
                        pending,
                        tasks_iter,
                        lambda uid: sample_storage.load(uid, categories),
                        limit=in_flight_limit,
                    )

        if replace_mode:
            self.sampleset.clear()
            for uid, sample in existing_samples.items():
                if uid in errors:
                    self.sampleset[uid] = sample
            for uid, sample in loaded_samples.items():
                self.sampleset[uid] = sample
        else:
            for uid, sample in loaded_samples.items():
                self.sampleset[uid] = sample

        logger.info("load samples finished: ok=%s, fail=%s, total=%s", ok, fail, total)
        return errors

    @ensure_connected
    def organize(self) -> None:
        """清理存储目录中不再属于当前样本集的陈旧条目。"""

        removed = self._require_sample_storage().organize(set(self.sampleset.keys()))
        logger.info("organize finished, removed stale entries: %s", removed)
