"""公开入口最小闭环测试。"""

from __future__ import annotations

from pathlib import Path

import dyntool.resources as dt_resource
from dyntool import DefaultSample, DefaultSampleSet, SampleDomain, StorageScheme


def test_resource_module_replaces_facade_resource_entry() -> None:
    manifest = dt_resource.manifest()

    assert "center_freq" in manifest
    assert dt_resource.path("center_freq").exists()


def test_sample_class_can_build_vibration_sample_from_accel_data() -> None:
    sample = DefaultSample.from_accel_data(
        [0.0, 0.08, -0.02, 0.03, 0.0],
        dt=0.01,
        sample_domain=SampleDomain.VIBRATION_TEST,
        case="sample-demo",
        point="P1",
        instr="ACC-01",
        dir="Z",
        record="R1",
        timestamp="2026-03-08 12:00:00",
    )

    assert sample.accel is not None
    assert sample.metadata.uid


def test_sample_class_can_build_from_models_and_eval_zvl() -> None:
    source = DefaultSample.from_accel_data(
        [0.0, 0.08, -0.02, 0.03, 0.0],
        dt=0.01,
        sample_domain=SampleDomain.VIBRATION_TEST,
        case="sample-demo",
        point="P1",
        instr="ACC-01",
        dir="Z",
        record="R1",
        timestamp="2026-03-08 12:00:00",
    )

    sample = DefaultSample.from_models(
        sample_domain=SampleDomain.VIBRATION_TEST,
        metadata=source.metadata,
        accel=source.accel,
    )

    result = sample.eval_zvl(overwrite=True, freq_range=(2.0, 60.0))

    assert result.success is True
    assert sample.zvl is not None


def test_sample_set_class_supports_from_samples_eval_and_h5_roundtrip(tmp_path: Path) -> None:
    sample = DefaultSample.from_accel_data(
        [0.0, 0.08, -0.02, 0.03, 0.0],
        dt=0.01,
        sample_domain=SampleDomain.VIBRATION_TEST,
        case="set-demo",
        point="P1",
        instr="ACC-01",
        dir="Z",
        record="R1",
        timestamp="2026-03-08 12:00:00",
    )
    sample_set = DefaultSampleSet.from_samples([sample], sample_domain=SampleDomain.VIBRATION_TEST)

    result = sample_set.eval_zvl(overwrite=True, freq_range=(2.0, 60.0))
    store_path = tmp_path / "samples.h5"

    sample_set.save(store_path, storage_scheme=StorageScheme.SET_H5)
    loaded = DefaultSampleSet.from_storage(
        store_path,
        sample_domain=SampleDomain.VIBRATION_TEST,
        storage_scheme=StorageScheme.SET_H5,
    )

    assert sample.uid in result
    assert loaded[sample.uid].zvl is not None
