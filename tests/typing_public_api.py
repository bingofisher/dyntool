"""公开 API 的 pyright 类型烟测。"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, assert_type

import pandas as pd

import dyntool.config as dt_config
import dyntool.logging as dt_logging
import dyntool.plotting as dt_plotting
import dyntool.resources as dt_resource
import dyntool.storage as dt_storage
from matplotlib.artist import Artist
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from dyntool import (
    AccelSeries,
    BatchOperationReport,
    ContainerFormat,
    LoggingMode,
    Metadata,
    OperationResult,
    PlotKind,
    Sample,
    SampleDomain,
    SampleSet,
    StorageMode,
    StorageScheme,
    UnitSystem,
    VibrationTestMetadata,
    VibrationTestSample,
    VibrationTestSampleSet,
)

if TYPE_CHECKING:
    accel = AccelSeries.from_data(
        [0.0, 0.1, -0.05],
        dt=0.01,
        axis_unit="second",
        data_unit="meter/second**2",
    )
    assert_type(accel, AccelSeries)
    assert_type(UnitSystem.si(), UnitSystem)
    assert_type(StorageScheme.SET_H5, StorageScheme)
    assert_type(StorageScheme.SET_SQLITE_H5, StorageScheme)
    assert_type(StorageMode.OPEN, StorageMode)
    assert_type(ContainerFormat.H5, ContainerFormat)
    assert_type(PlotKind.TIME, PlotKind)

    metadata = Metadata(attributes={"line": "A"})
    assert_type(metadata, Metadata)

    vibration_meta = VibrationTestMetadata(
        case="c1",
        point="p1",
        instr="a1",
        dir="Z",
        record="r1",
        timestamp="2026-03-08 12:00:00",
    )
    assert_type(vibration_meta, VibrationTestMetadata)

    vib_sample = Sample.from_accel_data(
        [0.0, 0.1, -0.02],
        dt=0.01,
        sample_domain=SampleDomain.VIBRATION_TEST,
        metadata_cls=VibrationTestMetadata,
        case="typing-demo",
        point="P1",
        instr="ACC-01",
        dir="Z",
        record="R1",
        timestamp="2026-03-08 12:00:00",
    )
    assert_type(vib_sample, VibrationTestSample)
    assert_type(vib_sample.eval_zvl(freq_range=(2.0, 60.0)), OperationResult[VibrationTestSample])

    vib_sample_set = SampleSet.from_samples([vib_sample], sample_domain=SampleDomain.VIBRATION_TEST)
    assert_type(vib_sample_set, VibrationTestSampleSet)
    assert_type(
        vib_sample_set.eval_zvl(freq_range=(2.0, 60.0)),
        BatchOperationReport[VibrationTestSampleSet],
    )
    assert_type(
        vib_sample_set.convert_storage("out/converted.h5", storage_scheme=StorageScheme.SET_H5),
        VibrationTestSampleSet,
    )

    saved_model_path = dt_storage.save_model(accel, "out/accel.csv")
    assert_type(saved_model_path, Path)
    assert_type(dt_storage.load_model("out/accel.csv", AccelSeries), AccelSeries)
    assert_type(dt_storage.inspect_model_units("out/accel.csv", AccelSeries), dict[str, str])

    logger = dt_logging.get_logger("storage")
    assert_type(logger, logging.Logger | logging.LoggerAdapter[logging.Logger])
    assert_type(
        dt_logging.configure_logging(provider="stdlib", mode=LoggingMode.CONSOLE_ONLY),
        dt_logging.LoggingConfig,
    )
    assert_type(dt_logging.available_providers(), tuple[str, ...])
    assert_type(dt_logging.get_active_provider_name(), str)

    assert_type(dt_resource.keys(), tuple[str, ...])
    assert_type(dt_resource.manifest(), dict[str, str])
    assert_type(dt_resource.path("center_freq"), Path)
    assert_type(dt_resource.csv("center_freq"), pd.DataFrame)
    freqs, freq_index = dt_resource.center_freqs((2.0, 80.0))
    assert_type(freqs, object)
    assert_type(freq_index, pd.Index)

    dataset = dt_plotting.PlotDataset.from_axis_value(
        axis=[0.0, 0.1, 0.2],
        value=[0.0, 0.1, -0.05],
        name="sample-1",
        category=dt_plotting.PlotCategory.SAMPLE,
    )
    assert_type(dataset, dt_plotting.PlotDataset)
    result = dt_plotting.FramePlotter().plot_dataset(dataset)
    assert_type(result, dt_plotting.PlotResult)
    assert_type(result.figure, Figure | None)
    assert_type(result.axes, tuple[Axes, ...])
    assert_type(result.artists, tuple[Artist, ...])

    config_loader = dt_config.load_config("config/demo.toml")
    assert_type(config_loader, dt_config.Config)
