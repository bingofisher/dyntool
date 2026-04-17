"""关键持久化路径性能基线守护。"""

from __future__ import annotations

from pathlib import Path
from time import perf_counter

import numpy as np
import pandas as pd

from dyntool.domain.metadata import Metadata
from dyntool.domain.models import AccelSeries
from dyntool.domain.samples import DefaultSample, DefaultSampleSet
from dyntool.storage.types import StorageMode, StorageScheme


def _build_set(n_samples: int, n_points: int) -> DefaultSampleSet:
    sample_set = DefaultSampleSet()
    for i in range(n_samples):
        meta = Metadata(extra={"idx": i})
        accel = AccelSeries.from_data(np.random.randn(n_points) * 0.01, dt=0.002)
        sample = DefaultSample(metadata=meta, accel=accel)
        sample_set[sample.uid] = sample
    return sample_set


def test_save_load_baseline_sample_dir(tmp_path: Path) -> None:
    # Keep loose thresholds to detect order-of-magnitude regressions.
    save_threshold_sec = 8.0
    load_threshold_sec = 8.0

    source = _build_set(n_samples=30, n_points=2000)
    store_dir = tmp_path / "perf_sample_dir"
    source.connect_storage(
        store_dir,
        mode=StorageMode.CREATE,
        storage_scheme=StorageScheme.SET_DIR,
    )
    assert source.storage is not None

    t0 = perf_counter()
    save_errors = source.storage.save_all(strict=True)
    t_save = perf_counter() - t0
    assert save_errors == {}
    assert t_save < save_threshold_sec

    loaded = DefaultSampleSet()
    loaded.connect_storage(
        store_dir,
        mode=StorageMode.OPEN,
        storage_scheme=StorageScheme.SET_DIR,
    )
    assert loaded.storage is not None

    t1 = perf_counter()
    load_errors = loaded.storage.load_all(strict=True)
    t_load = perf_counter() - t1
    assert load_errors == {}
    assert t_load < load_threshold_sec
    assert len(loaded) == len(source)


def test_save_load_baseline_sample_set_sqlite_h5_summary_frame(tmp_path: Path) -> None:
    source = _build_set(n_samples=20, n_points=1500)
    store_dir = tmp_path / "perf_sample_set_sqlite_h5"
    source.connect_storage(
        store_dir,
        mode=StorageMode.CREATE,
        storage_scheme=StorageScheme.SET_SQLITE_H5,
    )
    assert source.storage is not None

    save_errors = source.storage.save_all(strict=True)
    assert save_errors == {}

    loaded = DefaultSampleSet()
    loaded.connect_storage(
        store_dir,
        mode=StorageMode.OPEN,
        storage_scheme=StorageScheme.SET_SQLITE_H5,
    )
    assert loaded.storage is not None

    load_errors = loaded.storage.load_all(strict=True, categories=["accel"])
    assert load_errors == {}
    assert len(loaded) == len(source)

    strategy = loaded.storage._sample_storage.strategy
    original_load_sample = strategy.load_sample
    original_load_sample_fields = strategy.load_sample_fields
    original_load_many_sample_fields = strategy.load_many_sample_fields

    def _unexpected(*args: object, **kwargs: object) -> object:
        del args, kwargs
        raise AssertionError("summary_frame 不应再触发 payload 读取")

    strategy.load_sample = _unexpected  # type: ignore[method-assign]
    strategy.load_sample_fields = _unexpected  # type: ignore[method-assign]
    strategy.load_many_sample_fields = _unexpected  # type: ignore[method-assign]
    try:
        summary_frame = loaded.storage.summary_frame(
            metadata_fields=["extra@idx"],
            features=["pga"],
        )
    finally:
        strategy.load_sample = original_load_sample  # type: ignore[method-assign]
        strategy.load_sample_fields = original_load_sample_fields  # type: ignore[method-assign]
        strategy.load_many_sample_fields = original_load_many_sample_fields  # type: ignore[method-assign]

    assert len(summary_frame) == len(source)
    assert set(summary_frame["extra@idx"]) == set(range(20))
    assert {"uid", "alias", "pga"} <= set(summary_frame.columns)


def test_save_load_baseline_sample_set_h5_scalar_frame(tmp_path: Path) -> None:
    source = _build_set(n_samples=20, n_points=1500)
    store_path = tmp_path / "perf_sample_set.h5"
    source.connect_storage(
        store_path,
        mode=StorageMode.CREATE,
        storage_scheme=StorageScheme.SET_H5,
    )
    assert source.storage is not None

    save_errors = source.storage.save_all(strict=True)
    assert save_errors == {}

    loaded = DefaultSampleSet()
    loaded.connect_storage(
        store_path,
        mode=StorageMode.OPEN,
        storage_scheme=StorageScheme.SET_H5,
    )
    assert loaded.storage is not None

    load_errors = loaded.storage.load_all(strict=True)
    assert load_errors == {}
    assert len(loaded) == len(source)

    strategy = loaded.storage._sample_storage.strategy
    original_load_sample = strategy.load_sample
    original_load_sample_fields = strategy.load_sample_fields
    original_load_many_sample_fields = strategy.load_many_sample_fields

    def _unexpected(*args: object, **kwargs: object) -> object:
        del args, kwargs
        raise AssertionError("summary_frame 不应再触发 payload 读取")

    strategy.load_sample = _unexpected  # type: ignore[method-assign]
    strategy.load_sample_fields = _unexpected  # type: ignore[method-assign]
    strategy.load_many_sample_fields = _unexpected  # type: ignore[method-assign]
    try:
        frame = loaded.scalar_frame(
            metadata_fields=["extra@idx"],
            features=["pga"],
        )
    finally:
        strategy.load_sample = original_load_sample  # type: ignore[method-assign]
        strategy.load_sample_fields = original_load_sample_fields  # type: ignore[method-assign]
        strategy.load_many_sample_fields = original_load_many_sample_fields  # type: ignore[method-assign]

    assert len(frame) == len(source)
    assert set(pd.to_numeric(frame["extra@idx"], errors="raise")) == set(range(20))
    assert {"uid", "alias", "extra@idx", "pga"} <= set(frame.columns)
