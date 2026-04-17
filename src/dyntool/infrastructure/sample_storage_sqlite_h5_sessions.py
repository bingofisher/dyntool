"""`SET_SQLITE_H5` 的读写 session。"""

from __future__ import annotations

from time import perf_counter
from typing import TYPE_CHECKING
import sqlite3

import h5py
import pandas as pd

from . import sample_storage_sqlite_h5_types as sqlite_h5_types
from .sample_storage_sqlite_h5_payload import _load_many_sample_fields
from .sample_storage_sqlite_h5_types import (
    _SQLITE_H5_LOCK_TIMEOUT_SECONDS,
    _SqliteTransferArtifact,
    _SqliteWriteMetrics,
)
from .sample_storage_strategy_base import _StorageReadSession, _StorageWriteSession

if TYPE_CHECKING:
    from ..domain.samples.base import SampleBaseModel
    from .sample_storage_sqlite_h5_strategy import _SetSqliteH5Strategy


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
            self._strategy._ensure_schema(self._conn)
            self._strategy._begin_reader_transaction(self._conn)
        except Exception:  # noqa: BLE001
            if self._h5_file is not None:
                self._h5_file.close()
                self._h5_file = None
            if self._conn is not None:
                self._conn.rollback()
                self._conn.close()
                self._conn = None
            raise
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        del exc_type, exc, tb
        if self._h5_file is not None:
            self._h5_file.close()
            self._h5_file = None
        if self._conn is not None:
            self._conn.rollback()
            self._conn.close()
            self._conn = None

    def _require_h5_file(self) -> h5py.File:
        if self._h5_file is None:
            self._h5_file = h5py.File(self._strategy.ctx.sqlite_payload_h5_path(), "r")
        return self._h5_file

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
    """`SET_SQLITE_H5` 写入会话。"""

    def __init__(self, strategy: _SetSqliteH5Strategy) -> None:
        super().__init__(strategy)
        self._strategy = strategy
        self._conn: sqlite3.Connection | None = None
        self._h5_file: h5py.File | None = None
        self._pending_artifacts: list[_SqliteTransferArtifact] = []
        self._metrics = _SqliteWriteMetrics()

    def __enter__(self) -> "_SetSqliteH5WriteSession":
        self._conn = self._strategy._connect(
            timeout=_SQLITE_H5_LOCK_TIMEOUT_SECONDS,
            isolation_level=None,
        )
        try:
            self._strategy._ensure_schema(self._conn)
            self._strategy._begin_writer_transaction(self._conn)
            self._h5_file = h5py.File(self._strategy.ctx.sqlite_payload_h5_path(), "a")
            self._h5_file.require_group("samples")
        except Exception:  # noqa: BLE001
            if self._h5_file is not None:
                self._h5_file.close()
                self._h5_file = None
            if self._conn is not None:
                self._conn.rollback()
                self._conn.close()
                self._conn = None
            raise
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        if self._conn is not None and exc_type is None:
            self._flush_pending()
        if self._h5_file is not None:
            self._h5_file.close()
            self._h5_file = None
        if self._conn is not None:
            if exc_type is None:
                self._conn.commit()
            else:
                self._conn.rollback()
            self._conn.close()
            self._conn = None
        self._pending_artifacts.clear()
        self._strategy._last_write_metrics = self._metrics
        del exc_type, exc, tb

    def save_sample(self, sample: SampleBaseModel, categories: list[str] | None = None) -> None:
        if self._conn is None or self._h5_file is None:
            raise RuntimeError("SET_SQLITE_H5 写入会话尚未打开")
        artifact_started = perf_counter()
        artifact, data_dict = self._strategy._build_transfer_artifact(
            sample,
            categories=categories,
            conn=self._conn,
        )
        self._metrics.artifact_seconds += perf_counter() - artifact_started
        payload_started = perf_counter()
        self._strategy._write_payload(
            artifact.sample_row.payload_id,
            sample,
            data_dict,
            artifact.sample_row.timestamp,
            h5_file=self._h5_file,
        )
        self._metrics.payload_seconds += perf_counter() - payload_started
        self._metrics.sample_count += 1
        sample._storage_payload_id = artifact.sample_row.payload_id
        self._pending_artifacts.append(artifact)
        if len(self._pending_artifacts) >= sqlite_h5_types._SQLITE_H5_WRITE_FLUSH_BATCH_SIZE:
            self._flush_pending()

    def _flush_pending(self) -> None:
        if self._conn is None or not self._pending_artifacts:
            return
        flush_result = self._strategy._flush_transfer_artifacts(self._conn, self._pending_artifacts)
        self._metrics.flush_count += 1
        self._metrics.sample_seconds += flush_result.sample_seconds
        self._metrics.metadata_seconds += flush_result.metadata_seconds
        self._metrics.presence_seconds += flush_result.presence_seconds
        self._metrics.summary_seconds += flush_result.summary_seconds
        refresh_started = perf_counter()
        self._strategy._apply_cache_update(
            sample_rows_by_uid=flush_result.sample_rows_by_uid,
            presence_rows_by_uid=flush_result.presence_rows_by_uid,
        )
        self._metrics.refresh_cache_seconds += perf_counter() - refresh_started
        self._pending_artifacts.clear()


__all__ = ["_SetSqliteH5ReadSession", "_SetSqliteH5WriteSession"]
