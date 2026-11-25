"""`SET_SQLITE_H5` 的读写 session。"""

from __future__ import annotations

from time import perf_counter
from typing import TYPE_CHECKING, Callable
import sqlite3

import h5py
import pandas as pd

from ._storage_commit import _StorageConsistencyError, _WriteMarker
from .sample_storage_sqlite_h5_payload import _load_many_sample_fields
from .sample_storage_sqlite_h5_types import (
    _SQLITE_H5_LOCK_TIMEOUT_SECONDS,
    _SqliteWriteMetrics,
)
from .sample_storage_strategy_base import _StorageReadSession, _StorageWriteSession

if TYPE_CHECKING:
    from ..domain.samples.base import SampleBaseModel
    from .sample_storage_sqlite_h5_strategy import _SetSqliteH5Strategy


class _SqliteSessionCleanup:
    """尝试释放全部会话资源，收尾异常不得掩盖原始失败。"""

    @staticmethod
    def close(conn: sqlite3.Connection | None, h5_file: h5py.File | None, error: object) -> None:
        actions: list[Callable[[], object]] = []
        if h5_file is not None:
            actions.append(h5_file.close)
        if conn is not None:
            actions.extend((conn.rollback, conn.close))
        failures: list[BaseException] = []
        for action in actions:
            try:
                action()
            except BaseException as cleanup_error:
                failures.append(cleanup_error)
        if isinstance(error, BaseException):
            for failure in failures:
                error.add_note(f"会话资源清理失败：{failure}")
        elif failures:
            raise _StorageConsistencyError("会话资源清理失败，必须停止批次") from failures[0]


class _SetSqliteH5ReadSession(_StorageReadSession):
    """`SET_SQLITE_H5` 读取会话。"""

    def __init__(self, strategy: _SetSqliteH5Strategy) -> None:
        super().__init__(strategy)
        self._strategy = strategy
        self._conn: sqlite3.Connection | None = None
        self._h5_file: h5py.File | None = None

    def __enter__(self) -> "_SetSqliteH5ReadSession":
        self._conn = self._strategy._connect(
            timeout=_SQLITE_H5_LOCK_TIMEOUT_SECONDS,
            isolation_level=None,
        )
        try:
            self._strategy._begin_reader_transaction(self._conn)
            _WriteMarker.check(self._strategy.ctx.base_dir)
        except BaseException as error:
            self.__exit__(type(error), error, error.__traceback__)
            raise
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        conn, h5_file = self._conn, self._h5_file
        self._conn, self._h5_file = None, None
        _SqliteSessionCleanup.close(conn, h5_file, exc)

    def _require_h5_file(self) -> h5py.File:
        if self._h5_file is None:
            self._h5_file = h5py.File(self._strategy.ctx.sqlite_payload_h5_path(), "r")
        return self._h5_file

    def uid_name_index(self) -> dict[str, str]:
        """在当前读事务内取得完整索引，供集合整体加载使用。"""
        self._strategy._refresh_cache(self._conn)
        return {uid: uid for uid in self._strategy._sample_rows_by_uid}

    def select_uids(self, uids: list[str]) -> dict[str, str]:
        """在一个读事务中只获取目标样本及其槽位索引。"""
        self._strategy._refresh_cache(self._conn, uids=uids)
        return {uid: uid for uid in uids if uid in self._strategy._sample_rows_by_uid}

    def load_sample(
        self,
        uid: str,
        name: str,
        categories: list[str] | None = None,
    ) -> SampleBaseModel:
        del name
        return self._strategy._load_sample_from_resources(
            uid,
            categories=categories,
            h5_file=self._require_h5_file(),
        )

    def load_sample_fields(
        self,
        uid: str,
        name: str,
        categories: list[str],
    ) -> dict[str, object]:
        del name
        return self._strategy._load_sample_fields_from_resources(
            uid,
            categories=categories,
            h5_file=self._require_h5_file(),
        )

    def load_many_sample_fields(
        self,
        items: list[tuple[str, str]],
        categories: list[str],
    ) -> dict[str, dict[str, object]]:
        return _load_many_sample_fields(
            self._strategy,
            items=items,
            categories=categories,
            h5_file=self._require_h5_file(),
        )

    def sample_presence(
        self,
        uid: str,
        name: str,
    ) -> dict[str, bool]:
        del name
        return self._strategy.sample_presence(uid, uid)

    def summary_frame(
        self,
        *,
        uids: list[str] | None = None,
        metadata_fields: list[str] | None = None,
        data_vars: list[str] | None = None,
        features: list[str] | None = None,
    ) -> pd.DataFrame:
        if self._conn is None:
            raise RuntimeError("SET_SQLITE_H5 读取会话尚未打开")
        return self._strategy._summary_frame_from_conn(
            self._conn,
            uids=uids,
            metadata_fields=metadata_fields,
            data_vars=data_vars,
            features=features,
        )


class _SetSqliteH5WriteSession(_StorageWriteSession):
    """复用连接，但每个样本独立提交；H5 关闭后才发布 SQLite 索引。"""

    def __init__(self, strategy: _SetSqliteH5Strategy) -> None:
        super().__init__(strategy)
        self._strategy = strategy
        self._conn: sqlite3.Connection | None = None
        self._metrics = _SqliteWriteMetrics()

    def __enter__(self) -> "_SetSqliteH5WriteSession":
        self._conn = self._strategy._connect(
            timeout=_SQLITE_H5_LOCK_TIMEOUT_SECONDS,
            isolation_level=None,
        )
        try:
            self._strategy._ensure_schema(self._conn)
            _WriteMarker.check(self._strategy.ctx.base_dir)
        except BaseException as error:
            self.__exit__(type(error), error, error.__traceback__)
            raise
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        conn, self._conn = self._conn, None
        self._strategy._last_write_metrics = self._metrics
        _SqliteSessionCleanup.close(conn, None, exc)

    def save_sample(self, sample: SampleBaseModel, categories: list[str] | None = None) -> None:
        if categories == []:
            return
        if self._conn is None:
            raise RuntimeError("SET_SQLITE_H5 写入会话尚未打开")
        conn = self._conn
        with self._strategy.ctx.write_lock:
            self._strategy._begin_writer_transaction(conn)
            marker = _WriteMarker(self._strategy.ctx.base_dir, f"SQLite/H5 样本 {sample.uid}")
            started = False
            try:
                _WriteMarker.check(self._strategy.ctx.base_dir)
                artifact_started = perf_counter()
                artifact, data_dict = self._strategy._build_transfer_artifact(sample, categories=categories, conn=conn)
                self._metrics.artifact_seconds += perf_counter() - artifact_started
                marker.start()
                started = True
                payload_started = perf_counter()
                with h5py.File(self._strategy.ctx.sqlite_payload_h5_path(), "a") as h5_file:
                    self._strategy._write_payload(
                        artifact.sample_row.payload_id,
                        sample,
                        data_dict,
                        artifact.sample_row.timestamp,
                        h5_file=h5_file,
                    )
                    previous_id = artifact.sample_row.previous_payload_id
                    if previous_id is not None:
                        previous_slots = h5_file[f"samples/{previous_id}/slots"]
                        new_slots = h5_file[f"samples/{artifact.sample_row.payload_id}/slots"]
                        for name in previous_slots:
                            if name not in data_dict:
                                new_slots[name] = previous_slots[name]
                self._metrics.payload_seconds += perf_counter() - payload_started
                result = self._strategy._flush_transfer_artifacts(conn, [artifact])
                conn.commit()
            except BaseException as error:
                try:
                    conn.rollback()
                except BaseException as rollback_error:
                    error.add_note(f"SQLite 回滚失败：{rollback_error}；保留标记 {marker.path}")
                    raise _StorageConsistencyError("SQLite 回滚失败，必须停止批次") from error
                if started:
                    try:
                        marker.finish()
                    except OSError as cleanup_error:
                        error.add_note(f"中断标记清理失败：{cleanup_error}")
                        raise _StorageConsistencyError("中断标记无法清理，必须停止批次") from error
                raise
            sample._storage_payload_id = artifact.sample_row.payload_id
            self._metrics.sample_count += 1
            self._metrics.flush_count += 1
            self._metrics.sample_seconds += result.sample_seconds
            self._metrics.presence_seconds += result.presence_seconds
            self._metrics.summary_seconds += result.summary_seconds
            try:
                self._strategy._apply_cache_update(
                    sample_rows_by_uid=result.sample_rows_by_uid,
                    presence_rows_by_uid=result.presence_rows_by_uid,
                )
                marker.finish()
            except Exception as cleanup_error:
                raise _StorageConsistencyError(
                    f"样本已提交，但缓存或标记收尾失败：{marker.path}",
                    committed=True,
                ) from cleanup_error


__all__ = ["_SetSqliteH5ReadSession", "_SetSqliteH5WriteSession"]
