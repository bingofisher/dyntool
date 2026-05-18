"""公开枚举与参数校验测试。"""

from __future__ import annotations

from pathlib import Path

import pytest

from dyntool import AccelSeries, DefaultSample, DefaultSampleSet, PlotKind, SampleDomain, StorageMode
from dyntool.infrastructure.storage_options import (
    resolve_h5_dataset_options,
    resolve_storage_data_options,
)
from dyntool.storage.types import StorageScheme


def test_plot_payload_bridge_is_removed() -> None:
    accel = AccelSeries.from_data([0.0, 0.1, -0.05], dt=0.01)

    assert PlotKind.TIME.value == "time"
    assert not hasattr(accel, "to_plot_payload")


def test_storage_mode_requires_enum_value(tmp_path: Path) -> None:
    sample = DefaultSample.from_accel_data(
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
    sample_set = DefaultSampleSet.from_samples(
        [sample],
        sample_domain=SampleDomain.VIBRATION_TEST,
    )
    with pytest.raises(TypeError):
        sample_set.save(
            tmp_path / "samples.h5",
            mode="create",  # type: ignore[arg-type]
        )

    sample_set.save(tmp_path / "samples.h5", mode=StorageMode.CREATE)


def test_resolve_storage_data_options_rejects_unknown_keys() -> None:
    with pytest.raises(ValueError, match="unsupported_key"):
        resolve_storage_data_options(
            StorageScheme.SET_H5,
            {"unsupported_key": True},
        )


def test_resolve_storage_data_options_rejects_invalid_compression_level() -> None:
    with pytest.raises(ValueError, match="h5_compression_level"):
        resolve_storage_data_options(
            StorageScheme.SET_H5,
            {
                "h5_compression": "lzf",
                "h5_compression_level": 3,
            },
        )


def test_resolve_h5_dataset_options_normalizes_default_gzip_settings() -> None:
    resolved = resolve_h5_dataset_options(
        dataset_options={"shuffle": True},
        compression="gzip",
        compression_level=4,
    )

    assert resolved["compression"] == "gzip"
    assert resolved["compression_opts"] == 4
    assert resolved["shuffle"] is True
