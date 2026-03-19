"""类优先最小闭环集成测试。"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

import dyntool.plotting as dt_plotting
from dyntool import Sample, SampleDomain, SampleSet, StorageScheme


def test_class_first_roundtrip_from_accel_to_eval_to_h5(tmp_path: Path) -> None:
    sample = Sample.from_accel_data(
        np.random.randn(500) * 0.01,
        dt=0.002,
        sample_domain=SampleDomain.VIBRATION_TEST,
        case="case-1",
        point="P1",
        instr="ACC-01",
        dir="Z",
        record="R1",
        timestamp="2026-03-08 12:00:00",
    )
    sample_set = SampleSet.from_samples(
        [sample],
        sample_domain=SampleDomain.VIBRATION_TEST,
    )

    sample_set.eval_zvl(overwrite=True, freq_range=(2.0, 60.0))
    sample.calc_freqspec()
    sample.calc_respspec(overwrite=True)

    path = tmp_path / "samples.h5"
    sample_set.save(path, storage_scheme=StorageScheme.SET_H5)
    loaded = SampleSet.from_storage(
        path,
        sample_domain=SampleDomain.VIBRATION_TEST,
        storage_scheme=StorageScheme.SET_H5,
    )

    loaded_sample = loaded[sample.uid]
    assert loaded_sample.accel is not None
    assert loaded_sample.zvl is not None
    assert loaded_sample.metadata.uid == sample.metadata.uid

    plotter = dt_plotting.FramePlotter()
    plotter.add(
        loaded[sample.uid].accel,  # type: ignore[arg-type]
        name="loaded-accel",
        category=dt_plotting.PlotCategory.SAMPLE,
    )
    result = plotter.plot()
    assert result.figure is not None
    plt.close(result.figure)
