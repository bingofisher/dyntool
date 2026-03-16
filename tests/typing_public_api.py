"""Pyright smoke for final public API typing."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, assert_type

import dyntool.config as dt_config
import dyntool.logging as dt_logging
import dyntool.plotting as dt_plotting
import dyntool.storage as dt_storage
from dyntool import (
    AccelSeries,
    DataModelBase,
    DispSeries,
    DynTool,
    ForceSeries,
    Metadata,
    model_from_structured_payload,
    Sample,
    SampleDomain,
    SampleSet,
    VibrationTestSample,
    VibrationTestSampleSet,
    VibrationTestMetadata,
)
from dyntool.compute.flow import ComputeFlow
from dyntool.plotting import PlotResult

if TYPE_CHECKING:
    tool = DynTool()
    assert_type(tool.resource, object)
    assert_type(tool.options, object)

    accel = AccelSeries.from_data(
        [0.0, 0.1, -0.05],
        dt=0.01,
        axis_unit="second",
        data_unit="meter/second**2",
    )
    assert_type(accel, AccelSeries)
    assert_type(DispSeries.from_data([0.0, 0.1], dt=0.1), DispSeries)
    assert_type(ForceSeries.from_data([0.0, 1.0], dt=0.1), ForceSeries)

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
    eval_result = vib_sample.eval_zvl(freq_range=(2.0, 60.0))
    assert_type(eval_result, tuple[bool, str])

    sample_preprocess = vib_sample.preprocess_accel(highpass=0.5)
    assert_type(sample_preprocess, tuple[bool, str])

    sample_flow = vib_sample.flow()
    assert_type(sample_flow, ComputeFlow)

    canonical_sample_set = SampleSet.from_samples(
        [vib_sample],
        sample_domain=SampleDomain.VIBRATION_TEST,
    )
    assert_type(canonical_sample_set, VibrationTestSampleSet)

    sampleset_preprocess = canonical_sample_set.preprocess_accel(highpass=0.5)
    assert_type(sampleset_preprocess, dict[str, tuple[bool, str]] | tuple[bool, str])

    sampleset_eval = canonical_sample_set.eval_zvl(freq_range=(2.0, 60.0))
    assert_type(sampleset_eval, dict[str, tuple[bool, str]] | tuple[bool, str])

    sampleset_flow = canonical_sample_set.flow()
    assert_type(sampleset_flow, ComputeFlow)

    filtered_sample_set = canonical_sample_set.get_samples(lambda sample: sample.metadata.point == "P1")
    assert_type(filtered_sample_set, VibrationTestSampleSet)

    single_sample = canonical_sample_set.get_sample(lambda sample: sample.metadata.point == "P1")
    assert_type(single_sample, VibrationTestSample | None)

    loaded_set = SampleSet.from_storage(
        "out/sample_set.h5",
        sample_domain=SampleDomain.VIBRATION_TEST,
        storage_scheme=dt_storage.StorageScheme.SET_H5,
    )
    assert_type(loaded_set, VibrationTestSampleSet)
    assert_type(model_from_structured_payload(accel.to_structured_payload()), DataModelBase)

    saved_model_path = dt_storage.save_model(accel, "out/accel.csv")
    assert_type(saved_model_path, Path)

    reloaded_model = dt_storage.load_model("out/accel.csv", AccelSeries)
    assert_type(reloaded_model, AccelSeries)

    unit_map = dt_storage.inspect_model_units("out/accel.csv", AccelSeries)
    assert_type(unit_map, dict[str, str])

    logger = dt_logging.get_logger("storage")
    assert_type(logger, logging.Logger | logging.LoggerAdapter[logging.Logger])

    logging_config = dt_logging.configure_logging(
        provider="stdlib",
        mode=dt_logging.LoggingMode.CONSOLE_ONLY,
    )
    assert_type(logging_config, dt_logging.LoggingConfig)

    providers = dt_logging.available_providers()
    assert_type(providers, tuple[str, ...])

    active_provider = dt_logging.get_active_provider_name()
    assert_type(active_provider, str)

    plot_payload = accel.to_plot_payload()
    assert_type(plot_payload, dict[str, object])

    plot_result = dt_plotting.render_payload(plot_payload)
    assert_type(plot_result, PlotResult)

    config_loader = dt_config.load_config("config/demo.toml")
    assert_type(config_loader, dt_config.Config)
