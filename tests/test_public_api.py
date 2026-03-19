"""正式公开面回归测试。"""

from __future__ import annotations

from pathlib import Path

import dyntool
import dyntool.config as dt_config
import dyntool.logging as dt_logging
import dyntool.plotting as dt_plotting
import dyntool.resources as dt_resource
import dyntool.storage as dt_storage
from dyntool import (
    AccelSeries,
    AttrDataFormat,
    BatchOperationReport,
    ContainerFormat,
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
    Sample,
    SampleDomain,
    SampleSet,
    SpecAccelSeries,
    SpecDispSeries,
    SpecVelSeries,
    StorageMode,
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
        "Sample",
        "SampleSet",
        "VibrationTestSample",
        "VibrationTestSampleSet",
        "SampleDomain",
        "UnitSystem",
        "StorageScheme",
        "StorageMode",
        "AttrDataFormat",
        "ContainerFormat",
        "LoggingMode",
        "logging",
        "storage",
        "config",
        "resources",
        "PlotKind",
        "plotting",
    }


def test_removed_top_level_symbols_stay_removed() -> None:
    for name in (
        "DynTool",
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
    assert Sample.__name__ == "Sample"
    assert SampleSet.__name__ == "SampleSet"
    assert VibrationTestSample.__name__ == "VibrationTestSample"
    assert VibrationTestSampleSet.__name__ == "VibrationTestSampleSet"
    assert SampleDomain.VIBRATION_TEST.value == "vibration_test"
    assert UnitSystem.si() is not None
    assert StorageScheme.SET_H5.value == "set_h5"
    assert StorageMode.OPEN.value == "open"
    assert AttrDataFormat.CSV.value == "csv"
    assert ContainerFormat.H5.value == "h5"
    assert LoggingMode.CONSOLE_ONLY.value == "console_only"
    assert PlotKind.TIME.value == "time"


def test_formal_modules_are_available() -> None:
    assert logging is dt_logging
    assert storage is dt_storage
    assert config is dt_config
    assert resources is dt_resource
    assert plotting is dt_plotting


def test_resource_module_exposes_formal_actions() -> None:
    manifest = dt_resource.manifest()

    assert isinstance(dt_resource.keys(), tuple)
    assert "center_freq" in manifest
    assert dt_resource.path("center_freq").exists()
    csv = dt_resource.csv("center_freq")
    assert not csv.empty
    freqs, index = dt_resource.center_freqs((2.0, 80.0))
    assert len(freqs) == len(index)


def test_sample_and_sampleset_support_current_class_first_flow(tmp_path: Path) -> None:
    sample = Sample.from_accel_data(
        [0.0, 0.1, -0.02],
        dt=0.01,
        sample_domain=SampleDomain.VIBRATION_TEST,
        metadata_cls=VibrationTestMetadata,
        **_make_vibration_kwargs(),
    )
    result = sample.eval_zvl(overwrite=True, freq_range=(2.0, 60.0))
    sample_set = SampleSet.from_samples([sample], sample_domain=SampleDomain.VIBRATION_TEST)
    store_path = tmp_path / "sample_set.h5"
    sample_set.save(store_path, storage_scheme=StorageScheme.SET_H5)
    loaded = SampleSet.from_storage(
        store_path,
        sample_domain=SampleDomain.VIBRATION_TEST,
        storage_scheme=StorageScheme.SET_H5,
    )

    assert isinstance(result, OperationResult)
    assert isinstance(sample_set.eval_zvl(overwrite=True, freq_range=(2.0, 60.0)), BatchOperationReport)
    assert loaded[sample.uid].zvl is not None


def test_config_module_keeps_generic_loader() -> None:
    assert hasattr(dt_config, "Config")
    assert hasattr(dt_config, "load_config")
    assert hasattr(dt_config, "read_config_file")


def test_plotting_module_no_longer_exposes_backend_tokens() -> None:
    assert not hasattr(dt_plotting, "PlotBackend")
    assert "PlotBackend" not in getattr(dyntool, "__all__", ())
