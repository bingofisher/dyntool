"""正式公开面回归测试。"""

from __future__ import annotations

from pathlib import Path

import dyntool
import dyntool.config as dt_config
import dyntool.logging as dt_logging
import dyntool.plotting as dt_plotting
import dyntool.plotting.plotters as dt_plotters_module
import dyntool.reporting as dt_reporting
import dyntool.resources as dt_resource
import dyntool.storage as dt_storage
from dyntool import (
    AccelSeries,
    AttrDataFormat,
    BatchOperationReport,
    ContainerFormat,
    DefaultSample,
    DefaultSampleSet,
    DispSeries,
    FDMVLEval,
    FDMVLLimit,
    FPVDVEval,
    FPVDVLimit,
    FreqAmpSeries,
    FreqPhaSeries,
    FreqSpec,
    ForceSeries,
    LoggingMode,
    MagnitudeConversion,
    Metadata,
    OperationResult,
    OTOVLEval,
    OTOVLLimit,
    PlotKind,
    PSpecAccelSeries,
    PSpecVelSeries,
    RespSpec,
    ResponseSpectrum,
    SampleDomain,
    SpecAccelSeries,
    SpecDispSeries,
    SpecVelSeries,
    StorageMode,
    StorageConnectOptions,
    StorageScheme,
    TimeSeries,
    UnitSystem,
    VelSeries,
    VibrationTestMetadata,
    VibrationTestSample,
    VibrationTestSampleSet,
    ZVLEval,
    ZVLLimit,
    config,
    logging,
    plotting,
    reporting,
    resources,
    storage,
)


def _make_vibration_kwargs() -> dict[str, object]:
    return {
        "case": "c1",
        "point": "p1",
        "instr": "ACC-01",
        "dir": "Z",
        "record": "R1",
        "timestamp": "2026-03-08 12:00:00",
    }


def test_top_level_exports_match_current_public_surface() -> None:
    assert set(dyntool.__all__) == {
        "__version__",
        "MagnitudeConversion",
        "TimeSeries",
        "AccelSeries",
        "VelSeries",
        "DispSeries",
        "ForceSeries",
        "FreqAmpSeries",
        "FreqPhaSeries",
        "FreqSpec",
        "ResponseSpectrum",
        "SpecAccelSeries",
        "SpecVelSeries",
        "SpecDispSeries",
        "PSpecAccelSeries",
        "PSpecVelSeries",
        "RespSpec",
        "BatchOperationReport",
        "OperationResult",
        "TransferFunctionAnalyzer",
        "TransferFunctionResult",
        "ZVLEval",
        "OTOVLEval",
        "FPVDVEval",
        "FDMVLEval",
        "ZVLLimit",
        "OTOVLLimit",
        "FPVDVLimit",
        "FDMVLLimit",
        "ZVLLimitStandard",
        "OTOVLLimitStandard",
        "FPVDVLimitStandard",
        "FDMVLLimitStandard",
        "Metadata",
        "VibrationTestMetadata",
        "DefaultSample",
        "DefaultSampleSet",
        "VibrationTestSample",
        "VibrationTestSampleSet",
        "SampleDomain",
        "UnitSystem",
        "StorageScheme",
        "StorageMode",
        "StorageConnectOptions",
        "AttrDataFormat",
        "ContainerFormat",
        "LoggingMode",
        "logging",
        "storage",
        "config",
        "resources",
        "reporting",
        "PlotKind",
        "plotting",
    }


def test_removed_top_level_symbols_stay_removed() -> None:
    for name in (
        "DynTool",
        "Sample",
        "SampleSet",
        "resource",
        "PlotBackend",
        "DataModelBase",
        "MetadataBase",
        "SampleBase",
        "SampleBaseModel",
        "SampleSetBase",
        "MetadataSchema",
        "SampleSchema",
        "SampleSlotSpec",
        "MetadataIDGenerator",
        "model_from_structured_payload",
        "metadata_from_structured_payload",
        "sample_from_structured_payload",
        "sample_set_from_structured_payload",
        "VibEvalCommand",
    ):
        assert not hasattr(dyntool, name)


def test_top_level_exports_reference_expected_objects() -> None:
    assert MagnitudeConversion.__name__ == "MagnitudeConversion"
    assert TimeSeries.__name__ == "TimeSeries"
    assert AccelSeries.__name__ == "AccelSeries"
    assert VelSeries.__name__ == "VelSeries"
    assert DispSeries.__name__ == "DispSeries"
    assert ForceSeries.__name__ == "ForceSeries"
    assert FreqAmpSeries.__name__ == "FreqAmpSeries"
    assert FreqPhaSeries.__name__ == "FreqPhaSeries"
    assert FreqSpec.__name__ == "FreqSpec"
    assert ResponseSpectrum.__name__ == "ResponseSpectrum"
    assert SpecAccelSeries.__name__ == "SpecAccelSeries"
    assert SpecVelSeries.__name__ == "SpecVelSeries"
    assert SpecDispSeries.__name__ == "SpecDispSeries"
    assert PSpecAccelSeries.__name__ == "PSpecAccelSeries"
    assert PSpecVelSeries.__name__ == "PSpecVelSeries"
    assert RespSpec.__name__ == "RespSpec"
    assert ZVLEval.__name__ == "ZVLEval"
    assert OTOVLEval.__name__ == "OTOVLEval"
    assert FPVDVEval.__name__ == "FPVDVEval"
    assert FDMVLEval.__name__ == "FDMVLEval"
    assert ZVLLimit.__name__ == "ZVLLimit"
    assert OTOVLLimit.__name__ == "OTOVLLimit"
    assert FPVDVLimit.__name__ == "FPVDVLimit"
    assert FDMVLLimit.__name__ == "FDMVLLimit"
    assert Metadata.__name__ == "Metadata"
    assert VibrationTestMetadata.__name__ == "VibrationTestMetadata"
    assert hasattr(DefaultSample, "sample_schema")
    assert hasattr(DefaultSampleSet, "from_storage")
    assert VibrationTestSample.__name__ == "VibrationTestSample"
    assert VibrationTestSampleSet.__name__ == "VibrationTestSampleSet"
    assert SampleDomain.VIBRATION_TEST.value == "vibration_test"
    assert UnitSystem.si() is not None
    assert StorageScheme.SET_H5.value == "set_h5"
    assert StorageScheme.SET_SQLITE_H5.value == "set_sqlite_h5"
    assert StorageScheme.SET_DIR.value == "sample_dir"
    assert StorageScheme.SET_ATTR_TABLE.value == "attr_table"
    assert StorageMode.OPEN.value == "open"
    assert StorageConnectOptions().scheme is StorageScheme.SET_DIR
    assert AttrDataFormat.CSV.value == "csv"
    assert ContainerFormat.H5.value == "h5"
    assert LoggingMode.CONSOLE_ONLY.value == "console_only"
    assert PlotKind.TIME.value == "time"


def test_storage_scheme_legacy_aliases_are_removed() -> None:
    assert not hasattr(StorageScheme, "SAMPLE_DIR")
    assert not hasattr(StorageScheme, "ATTR_TABLE")


def test_formal_modules_are_available() -> None:
    assert logging is dt_logging
    assert storage is dt_storage
    assert config is dt_config
    assert resources is dt_resource
    assert reporting is dt_reporting
    assert plotting is dt_plotting


def test_reporting_module_exports_formal_table_and_package_helpers(tmp_path: Path) -> None:
    sample = DefaultSample.from_accel_data(
        [0.0, 0.1, -0.02, 0.03],
        dt=0.01,
        sample_domain=SampleDomain.VIBRATION_TEST,
        metadata_cls=VibrationTestMetadata,
        **_make_vibration_kwargs(),
    )
    sample_set = DefaultSampleSet.from_samples([sample], sample_domain=SampleDomain.VIBRATION_TEST)

    scalar_path = dt_reporting.export_scalar_frame(
        sample_set,
        tmp_path / "scalar_frame.xlsx",
        features=["pga", "rms"],
    )
    report_dir = dt_reporting.export_report_package(
        sample_set,
        tmp_path / "report_package",
        include_plots=False,
    )

    assert scalar_path.exists()
    assert report_dir.exists()
    assert (report_dir / "report.xlsx").exists()


def test_storage_module_exports_connect_options_contract() -> None:
    options = dt_storage.StorageConnectOptions(
        scheme=dt_storage.StorageScheme.SET_H5,
        mode=dt_storage.StorageMode.CREATE,
        set_filename="bundle.h5",
    )

    assert isinstance(options, dt_storage.StorageConnectOptions)
    assert options.scheme is dt_storage.StorageScheme.SET_H5
    assert options.mode is dt_storage.StorageMode.CREATE


def test_storage_module_exposes_detection_and_inspection_helpers(tmp_path: Path) -> None:
    sample = DefaultSample(metadata=Metadata(extra={"source": "public-api"}))
    store_dir = tmp_path / "public_api_set_dir"
    DefaultSampleSet({sample.uid: sample}).save(store_dir, storage_scheme=StorageScheme.SET_DIR)

    detected = dt_storage.detect_storage_scheme(store_dir, kind="sample_set")
    report = dt_storage.inspect_storage_repository(store_dir, level="quick")

    assert detected is StorageScheme.SET_DIR
    assert isinstance(report, dt_storage.StorageRepositoryReport)
    assert report.detected_scheme is StorageScheme.SET_DIR
    assert report.is_valid is True


def test_resource_module_exposes_formal_actions() -> None:
    manifest = dt_resource.manifest()

    assert isinstance(dt_resource.keys(), tuple)
    assert "center_freq" in manifest
    assert dt_resource.path("center_freq").exists()
    csv = dt_resource.csv("center_freq")
    assert not csv.empty
    freqs, index = dt_resource.center_freqs((2.0, 80.0))
    assert len(freqs) == len(index)


def test_default_sample_and_set_support_current_public_flow(tmp_path: Path) -> None:
    sample = DefaultSample.from_accel_data(
        [0.0, 0.1, -0.02],
        dt=0.01,
        sample_domain=SampleDomain.VIBRATION_TEST,
        metadata_cls=VibrationTestMetadata,
        **_make_vibration_kwargs(),
    )
    result = sample.eval_zvl(overwrite=True, freq_range=(2.0, 60.0))
    sample_set = DefaultSampleSet.from_samples([sample], sample_domain=SampleDomain.VIBRATION_TEST)
    store_path = tmp_path / "sample_set.h5"
    sample_set.save(store_path, storage_scheme=StorageScheme.SET_H5)
    loaded = DefaultSampleSet.from_storage(
        store_path,
        sample_domain=SampleDomain.VIBRATION_TEST,
        storage_scheme=StorageScheme.SET_H5,
    )

    assert isinstance(result, OperationResult)
    assert isinstance(sample_set.eval_zvl(overwrite=True, freq_range=(2.0, 60.0)), BatchOperationReport)
    assert hasattr(sample_set, "convert_storage")
    comparison = sample_set.compare_with(sample_set, data_vars=["zvl"], features=["pga"])
    assert comparison.same_type is True
    assert comparison.scalar_diff.empty
    assert loaded[sample.uid].zvl is not None


def test_config_module_keeps_generic_loader() -> None:
    assert hasattr(dt_config, "Config")
    assert hasattr(dt_config, "load_config")
    assert hasattr(dt_config, "read_config_file")


def test_plotting_module_no_longer_exposes_backend_tokens() -> None:
    assert not hasattr(dt_plotting, "PlotBackend")
    assert "PlotBackend" not in getattr(dyntool, "__all__", ())


def test_plotting_module_exports_match_stage_c_public_surface() -> None:
    assert set(dt_plotting.__all__) == {
        "AxisConfig",
        "BoxPlotter",
        "ContinuousAxisSpec",
        "FramePlotter",
        "OctaveAxisSpec",
        "OneThirdOctavePlotter",
        "PlotCategory",
        "PlotDataset",
        "PlotKind",
        "PlotResult",
        "PlotStatMetric",
        "PlotTheme",
        "StoryValuePlotter",
    }


def test_plotting_public_objects_keep_expected_module_locations() -> None:
    assert dt_plotting.AxisConfig.__module__ == "dyntool.plotting.axis_config"
    assert dt_plotting.ContinuousAxisSpec.__module__ == "dyntool.plotting.axis_config"
    assert dt_plotting.OctaveAxisSpec.__module__ == "dyntool.plotting.axis_config"
    assert dt_plotting.PlotDataset.__module__ == "dyntool.plotting.dataset"
    assert dt_plotting.PlotTheme.__module__ == "dyntool.plotting.config"
    assert dt_plotting.PlotResult.__module__ == "dyntool.plotting.types"
    assert dt_plotting.FramePlotter.__module__ == "dyntool.plotting.plotters"
    assert dt_plotting.BoxPlotter.__module__ == "dyntool.plotting.plotters"
    assert dt_plotting.OneThirdOctavePlotter.__module__ == "dyntool.plotting.plotters"
    assert dt_plotting.StoryValuePlotter.__module__ == "dyntool.plotting.plotters"


def test_plotting_module_no_longer_exports_internal_helpers_and_compat_entries() -> None:
    # v1.2.0 起，这些 plotting compat / legacy 顶层入口应保持删除状态。
    for name in (
        "AxisFrame",
        "AxisHelper",
        "AxisNumberFormatter",
        "DiscreteAxisFormatter",
        "GridFrame",
        "LegendHelper",
        "OctaveBandSpec",
        "PlotterBase",
        "PlotterKind",
        "ZhPlotConfig",
        "configure_zh",
    ):
        assert not hasattr(dt_plotting, name)


def test_plotters_submodule_only_exposes_formal_concrete_plotters() -> None:
    assert set(dt_plotters_module.__all__) == {
        "BoxPlotter",
        "FramePlotter",
        "OneThirdOctavePlotter",
        "StoryValuePlotter",
    }
    assert not hasattr(dt_plotters_module, "PlotterBase")
    assert not hasattr(dt_plotters_module, "OctaveBandSpec")
