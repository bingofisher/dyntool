"""关键持久化路径性能基线守护。"""

from __future__ import annotations

from pathlib import Path
from time import perf_counter

import numpy as np

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
        storage_scheme=StorageScheme.SAMPLE_DIR,
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
        storage_scheme=StorageScheme.SAMPLE_DIR,
    )
    assert loaded.storage is not None

    t1 = perf_counter()
    load_errors = loaded.storage.load_all(strict=True)
    t_load = perf_counter() - t1
    assert load_errors == {}
    assert t_load < load_threshold_sec
    assert len(loaded) == len(source)
