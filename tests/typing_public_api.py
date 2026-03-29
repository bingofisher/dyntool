"""公开 API 的 pyright 类型烟测。"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, assert_type

import pandas as pd

import dyntool.config as dt_config
import dyntool.compute as dt_compute
import dyntool.domain as dt_domain
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
    DefaultSample,
    DefaultSampleSet,
    LoggingMode,
    Metadata,
    OperationResult,
    PlotKind,
    SampleDomain,
    StorageMode,
    StorageScheme,
    UnitSystem,
    VibrationTestMetadata,
    VibrationTestSample,
    VibrationTestSampleSet,
    ZVLLimit,
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
    assert_type(StorageMode.OPEN, StorageMode)
    assert_type(ContainerFormat.H5, ContainerFormat)
    assert_type(PlotKind.TIME, PlotKind)
    assert_type(dt_storage.DataCategory.TS_ACCEL, dt_storage.DataCategory)
    assert_type(dt_storage.SampleLoadMode.LAZY, dt_storage.SampleLoadMode)
    assert_type(dt_storage.SampleDomain.VIBRATION_TEST, dt_storage.SampleDomain)
    assert_type(dt_storage.StorageAccessMode.READ_ONLY, dt_storage.StorageAccessMode)
    assert_type(
        dt_storage.SampleSetViewOptions(
            load_mode=dt_storage.SampleLoadMode.LAZY,
            access_mode=dt_storage.StorageAccessMode.READ_ONLY,
        ),
        dt_storage.SampleSetViewOptions,
    )

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

    vib_sample = DefaultSample.from_accel_data(
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

    vib_sample_set = DefaultSampleSet.from_samples([vib_sample], sample_domain=SampleDomain.VIBRATION_TEST)
    assert_type(vib_sample_set, VibrationTestSampleSet)
    assert_type(
        vib_sample_set.eval_zvl(freq_range=(2.0, 60.0)),
        BatchOperationReport[VibrationTestSampleSet],
    )
    assert_type(vib_sample.replace_metadata(vibration_meta), VibrationTestSample)
    assert_type(vib_sample.patch_metadata(extra={"source": "typing"}), VibrationTestSample)
    assert_type(vib_sample.reset_alias(), VibrationTestSample)
    assert_type(vib_sample.compute.available(), tuple[object, ...])
    assert_type(vib_sample.compute.feature.rms(), float)
    assert_type(vib_sample.compute.feature.crest_factor(), float)
    assert_type(vib_sample.pga(), float)
    assert_type(vib_sample_set.metadata_frame(), pd.DataFrame)
    assert_type(vib_sample_set.data_map("accel"), dict[str, object])
    assert_type(vib_sample_set.find_many(), VibrationTestSampleSet)
    assert_type(vib_sample_set.find_one(), VibrationTestSample | None)
    assert_type(vib_sample_set.distinct_metadata("case"), tuple[object, ...])
    assert_type(
        vib_sample_set.scalar_frame(
            metadata_fields=["case"],
            data_vars=["zvl"],
            features=["pga", "rms", "crest_factor"],
        ),
        pd.DataFrame,
    )
    assert_type(vib_sample_set.series_frame("accel", metadata_fields=["case"]), pd.DataFrame)
    assert_type(vib_sample_set.peaks_frame(source="accel"), pd.DataFrame)
    assert_type(dt_compute.metrics.zvl_from_accel([0.0, 0.1, -0.1], 0.01), dict[str, object])
    assert_type(dt_compute.features.rms_feature([0.0, 0.1, -0.1]), dict[str, float])
    assert_type(dt_domain.models.AccelSeries, type[AccelSeries])
    assert_type(dt_domain.limits.ZVLLimit, type[ZVLLimit])
    assert_type(dt_domain.SampleDomain.VIBRATION_TEST, SampleDomain)

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
    axis_helper = dt_plotting.AxisHelper(ax=Axes(Figure(), [0.0, 0.0, 1.0, 1.0]))
    assert_type(axis_helper, dt_plotting.AxisHelper)
    axis_helper.format_axis(
        side="left",
        mode="continuous",
        data=[0.0, 0.1, -0.05],
        baseline=0.0,
        num_segments=4,
    )

    box_dataset = dt_plotting.PlotDataset.from_axis_value(
        axis=[0.0, 1.0, 2.0],
        value=[64.0, 66.0, 65.0],
        name="point-1",
        category=dt_plotting.PlotCategory.SAMPLE,
    )
    assert_type(dt_plotting.PlotStatMetric.MEAN, dt_plotting.PlotStatMetric)
    box_result = dt_plotting.BoxPlotter().plot_dataset(
        box_dataset,
        stats=[dt_plotting.PlotStatMetric.MEAN],
        style_defaults={"box.facecolor": "#dddddd"},
    )
    assert_type(box_result, dt_plotting.PlotResult)

    config_loader = dt_config.load_config("config/demo.toml")
    assert_type(config_loader, dt_config.Config)
