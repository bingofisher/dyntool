"""公开枚举与参数校验测试。"""

from __future__ import annotations

from pathlib import Path

import pytest

from dyntool import AccelSeries, PlotKind, Sample, SampleDomain, SampleSet, StorageMode, StorageScheme


def test_plot_payload_bridge_is_removed() -> None:
    accel = AccelSeries.from_data([0.0, 0.1, -0.05], dt=0.01)

    assert PlotKind.TIME.value == "time"
    assert not hasattr(accel, "to_plot_payload")


def test_storage_mode_requires_enum_value(tmp_path: Path) -> None:
    sample = Sample.from_accel_data(
        [0.0, 0.1, -0.02],
        dt=0.01,
        sample_domain=SampleDomain.VIBRATION_TEST,
        case="c1",
        point="p1",
        instr="a1",
        dir="Z",
        record="r1",
        timestamp="2026-03-08 12:00:00",
    )
    sample_set = SampleSet.from_samples(
        [sample],
        sample_domain=SampleDomain.VIBRATION_TEST,
    )
    with pytest.raises(TypeError):
        sample_set.save(
            tmp_path / "samples.h5",
            mode="create",  # type: ignore[arg-type]
        )

    sample_set.save(tmp_path / "samples.h5", mode=StorageMode.CREATE)


def test_connect_storage_rejects_unknown_data_option(tmp_path: Path) -> None:
    sample_set = SampleSet()

    with pytest.raises(ValueError, match="data_options"):
        sample_set.connect_storage(
            tmp_path / "unknown_data_option",
            mode=StorageMode.CREATE,
            storage_scheme=StorageScheme.SAMPLE_DIR,
            data_options={"unknown_option": 1},
        )


def test_connect_storage_rejects_h5_options_for_non_h5_scheme(tmp_path: Path) -> None:
    sample_set = SampleSet()

    with pytest.raises(ValueError, match="h5_compression"):
        sample_set.connect_storage(
            tmp_path / "not_h5",
            mode=StorageMode.CREATE,
            storage_scheme=StorageScheme.SAMPLE_DIR,
            data_options={"h5_compression": "gzip"},
        )


def test_connect_storage_exposes_normalized_h5_data_options(tmp_path: Path) -> None:
    sample_set = SampleSet()

    sample_set.connect_storage(
        tmp_path / "sample_h5",
        mode=StorageMode.CREATE,
        storage_scheme=StorageScheme.SAMPLE_H5,
    )

    assert sample_set.storage is not None
    assert sample_set.storage.data_options["h5_compression"] == "gzip"
    assert sample_set.storage.data_options["h5_compression_level"] == 4
    assert sample_set.storage.data_options["h5_dataset_options"] == {
        "compression": "gzip",
        "compression_opts": 4,
    }


def test_connect_storage_exposes_normalized_h5_data_options_for_set_sqlite_h5(tmp_path: Path) -> None:
    sample_set = SampleSet()

    sample_set.connect_storage(
        tmp_path / "sample_set_sqlite_h5",
        mode=StorageMode.CREATE,
        storage_scheme=StorageScheme.SET_SQLITE_H5,
    )

    assert sample_set.storage is not None
    assert sample_set.storage.data_options["h5_compression"] == "gzip"
    assert sample_set.storage.data_options["h5_compression_level"] == 4
    assert sample_set.storage.data_options["h5_dataset_options"] == {
        "compression": "gzip",
        "compression_opts": 4,
    }
