"""公开枚举与参数校验测试。"""

from __future__ import annotations

from pathlib import Path

import pytest

from dyntool import AccelSeries, PlotKind, Sample, SampleDomain, SampleSet, StorageMode


def test_plot_kind_requires_enum_value() -> None:
    accel = AccelSeries.from_data([0.0, 0.1, -0.05], dt=0.01)

    assert PlotKind.TIME.value == "time"
    with pytest.raises(TypeError):
        accel.to_plot_payload(kind="time")  # type: ignore[arg-type]


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
