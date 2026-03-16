"""公开 API 回归测试。"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pytest

import dyntool
import dyntool.config as dt_config
import dyntool.logging as dt_logging
import dyntool.plotting as dt_plotting
import dyntool.storage as dt_storage
from dyntool import (
    AccelSeries,
    DispSeries,
    DataModelBase,
    DynTool,
    FDMVLEval,
    FPVDVEval,
    FreqAmpSeries,
    FreqPhaSeries,
    FreqSpec,
    ForceSeries,
    LoggingMode,
    Metadata,
    MetadataBase,
    MetadataIDGenerator,
    MetadataSchema,
    OTOVLEval,
    PSpecAccelSeries,
    PSpecVelSeries,
    PlotKind,
    RespSpec,
    ResponseSpectrum,
    Sample,
    SampleBase,
    SampleBaseModel,
    SampleDomain,
    SampleSchema,
    SampleSet,
    SampleSetBase,
    SampleSlotSpec,
    SpecAccelSeries,
    SpecDispSeries,
    SpecVelSeries,
    StorageMode,
    TimeSeries,
    UnitSystem,
    VelSeries,
    VibrationTestSample,
    VibrationTestSampleSet,
    VibrationTestMetadata,
    ZVLEval,
    metadata_from_structured_payload,
    model_from_structured_payload,
    sample_from_structured_payload,
    sample_set_from_structured_payload,
)
from dyntool.plotting import FramePlotter, PlotResult, StoryValuePlotter


def _make_vibration_kwargs() -> dict[str, object]:
    return {
        "case": "c1",
        "point": "p1",
        "instr": "ACC-01",
        "dir": "Z",
        "record": "R1",
        "timestamp": "2026-03-08 12:00:00",
    }


def test_dyntool_exposes_only_resource_and_options() -> None:
    tool = DynTool()
    public_members = {name for name in vars(tool) if not name.startswith("_")}

    assert public_members == {"resource", "options"}
    assert not hasattr(tool, "models")
    assert not hasattr(tool, "sample")


def test_top_level_exports_match_canonical_baseline() -> None:
    assert set(dyntool.__all__) == {
        "__version__",
        "DynTool",
        "DataModelBase",
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
        "ZVLEval",
        "OTOVLEval",
        "FPVDVEval",
        "FDMVLEval",
        "MetadataBase",
        "Metadata",
        "MetadataIDGenerator",
        "MetadataSchema",
        "metadata_from_structured_payload",
        "SampleBase",
        "SampleBaseModel",
        "SampleSchema",
        "SampleSlotSpec",
        "Sample",
        "SampleSetBase",
        "SampleSet",
        "VibrationTestSample",
        "VibrationTestSampleSet",
        "sample_from_structured_payload",
        "sample_set_from_structured_payload",
        "SampleDomain",
        "VibrationTestMetadata",
        "model_from_structured_payload",
        "UnitSystem",
        "StorageScheme",
        "StorageMode",
        "AttrDataFormat",
        "ContainerFormat",
        "LoggingMode",
        "logging",
        "storage",
        "config",
        "PlotKind",
        "PlotBackend",
        "plotting",
        "VibEvalCommand",
    }


def test_top_level_extension_exports_are_available() -> None:
    assert issubclass(AccelSeries, DataModelBase)
    assert issubclass(VelSeries, DataModelBase)
    assert issubclass(DispSeries, DataModelBase)
    assert issubclass(ForceSeries, DataModelBase)
    assert issubclass(TimeSeries, DataModelBase)
    assert issubclass(Metadata, MetadataBase)
    assert issubclass(Sample, SampleBase)
    assert issubclass(SampleSet, SampleSetBase)
    assert issubclass(VibrationTestSample, SampleBase)
    assert issubclass(VibrationTestSampleSet, SampleSetBase)
    assert issubclass(FreqAmpSeries, DataModelBase)
    assert issubclass(FreqPhaSeries, DataModelBase)
    assert issubclass(FreqSpec, DataModelBase)
    assert issubclass(ResponseSpectrum, DataModelBase)
    assert issubclass(SpecAccelSeries, DataModelBase)
    assert issubclass(SpecVelSeries, DataModelBase)
    assert issubclass(SpecDispSeries, DataModelBase)
    assert issubclass(PSpecAccelSeries, DataModelBase)
    assert issubclass(PSpecVelSeries, DataModelBase)
    assert issubclass(RespSpec, DataModelBase)
    assert issubclass(ZVLEval, DataModelBase)
    assert issubclass(OTOVLEval, DataModelBase)
    assert issubclass(FPVDVEval, DataModelBase)
    assert issubclass(FDMVLEval, DataModelBase)
    assert issubclass(SampleBaseModel, SampleBaseModel)
    assert isinstance(MetadataSchema(name="demo"), MetadataSchema)
    assert isinstance(SampleSlotSpec(name="accel", model_type=AccelSeries), SampleSlotSpec)
    assert MetadataIDGenerator.quick_id({"demo": 1})
    assert isinstance(SampleSchema(name="demo"), SampleSchema)
    assert callable(model_from_structured_payload)
    assert callable(metadata_from_structured_payload)
    assert callable(sample_from_structured_payload)
    assert callable(sample_set_from_structured_payload)


def test_top_level_exports_reference_same_objects_as_submodules() -> None:
    from dyntool.domain.metadata import Metadata as DomainMetadata
    from dyntool.domain.metadata import metadata_from_structured_payload as domain_metadata_from_structured_payload
    from dyntool.domain.models import FreqSpec as DomainFreqSpec
    from dyntool.domain.models import model_from_structured_payload as domain_model_from_structured_payload
    from dyntool.domain.samples import Sample as DomainSample
    from dyntool.domain.samples import sample_set_from_structured_payload as domain_sample_set_from_structured_payload
    from dyntool.domain.samples import sample_from_structured_payload as domain_sample_from_structured_payload

    assert Metadata is DomainMetadata
    assert FreqSpec is DomainFreqSpec
    assert Sample is DomainSample
    assert model_from_structured_payload is domain_model_from_structured_payload
    assert metadata_from_structured_payload is domain_metadata_from_structured_payload
    assert sample_from_structured_payload is domain_sample_from_structured_payload
    assert sample_set_from_structured_payload is domain_sample_set_from_structured_payload


def test_custom_time_series_can_register_with_string_category_and_roundtrip() -> None:
    class JerkSeries(TimeSeries):
        category = "ts_jerk_test_public_api"

        @classmethod
        def _base_value_unit(cls) -> str:
            return "meter/second**3"

    jerk = JerkSeries.from_data(
        [0.0, 1.0, -0.5],
        dt=0.1,
        axis_unit="second",
        data_unit="meter/second**3",
    )

    restored = model_from_structured_payload(jerk.to_structured_payload())

    assert DataModelBase.from_category("ts_jerk_test_public_api") is JerkSeries
    assert isinstance(restored, JerkSeries)


def test_top_level_core_exports_are_available() -> None:
    accel = AccelSeries.from_data([0.0, 0.1, -0.02], dt=0.01)
    sample = Sample.from_models(
        metadata=Metadata(attributes={"source": "top-level"}),
        accel=accel,
    )
    sample_set = SampleSet.from_samples([sample])

    assert accel.__class__.__name__ == "AccelSeries"
    assert sample.accel is not None
    assert len(sample_set) == 1
    assert isinstance(UnitSystem.si(), UnitSystem)


def test_sample_set_no_longer_exposes_direct_csv_h5_shortcuts() -> None:
    assert not hasattr(SampleSet, "to_h5")
    assert not hasattr(SampleSet, "from_h5")
    assert not hasattr(SampleSet, "to_csv")
    assert not hasattr(SampleSet, "from_csv")


def test_top_level_metadata_exports_are_available() -> None:
    vibration_meta = VibrationTestMetadata(**_make_vibration_kwargs())
    assert vibration_meta.uid


def test_sample_class_supports_class_first_creation_and_eval() -> None:
    sample = Sample.from_accel_data(
        [0.0, 0.1, -0.02],
        dt=0.01,
        sample_domain=SampleDomain.VIBRATION_TEST,
        metadata_cls=VibrationTestMetadata,
        **_make_vibration_kwargs(),
    )

    success, _ = sample.eval_zvl(overwrite=True, freq_range=(2.0, 60.0))

    assert success is True
    assert sample.zvl is not None


def test_sample_set_class_supports_from_samples_and_storage_roundtrip(tmp_path: Path) -> None:
    sample = Sample.from_accel_data(
        [0.0, 0.1, -0.02],
        dt=0.01,
        sample_domain=SampleDomain.VIBRATION_TEST,
        metadata_cls=VibrationTestMetadata,
        **_make_vibration_kwargs(),
    )
    sample_set = SampleSet.from_samples([sample], sample_domain=SampleDomain.VIBRATION_TEST)
    result = sample_set.eval_zvl(overwrite=True, freq_range=(2.0, 60.0))
    store_path = tmp_path / "samples.h5"

    sample_set.save(store_path, storage_scheme=dyntool.StorageScheme.SET_H5)

    loaded = SampleSet.from_storage(
        store_path,
        sample_domain=SampleDomain.VIBRATION_TEST,
        storage_scheme=dyntool.StorageScheme.SET_H5,
    )

    assert sample.uid in result
    assert loaded[sample.uid].zvl is not None


def test_logging_module_supports_directory_mode(tmp_path: Path) -> None:
    log_dir = tmp_path / "logs"
    config = dt_logging.configure_logging(
        provider="stdlib",
        mode=LoggingMode.DIRECTORY,
        log_dir=log_dir,
        level="INFO",
        mirror_to_console=False,
    )
    logger = dt_logging.get_logger("storage")
    logger.info("save done")

    assert config.log_dir == log_dir
    assert log_dir.exists()
    assert (log_dir / "storage.log").exists()
    assert "stdlib" in dt_logging.available_providers()
    assert dt_logging.get_active_provider_name() == "stdlib"


def test_storage_module_roundtrip_model_and_sample_set(tmp_path: Path) -> None:
    accel = AccelSeries.from_data([0.0, 0.1, -0.05], dt=0.01)
    model_path = tmp_path / "accel.csv"
    sample = Sample.from_accel_data(
        [0.0, 0.1, -0.02],
        dt=0.01,
        sample_domain=SampleDomain.VIBRATION_TEST,
        metadata_cls=VibrationTestMetadata,
        **_make_vibration_kwargs(),
    )
    sample_set = SampleSet.from_samples([sample], sample_domain=SampleDomain.VIBRATION_TEST)
    set_path = tmp_path / "samples.h5"

    saved_path = dt_storage.save_model(accel, model_path)
    loaded_model = dt_storage.load_model(saved_path, type(accel))
    units = dt_storage.inspect_model_units(saved_path, type(accel))
    dt_storage.save_sample_set(sample_set, set_path)
    loaded_set = dt_storage.load_sample_set(set_path, domain=SampleDomain.VIBRATION_TEST)

    assert loaded_model.get_value().shape == accel.get_value().shape
    assert "time" in units
    assert loaded_set[sample.uid].accel is not None


def test_plotting_module_returns_plot_result_for_model_payloads() -> None:
    accel = AccelSeries.from_data([0.0, 0.1, -0.05], dt=0.01)
    model_result = dt_plotting.render_payload(accel.to_plot_payload(kind=PlotKind.TIME))
    raw_result = dt_plotting.render_payload(
        dt_plotting.FramePlotPayload(
            panels=(
                dt_plotting.FramePanelPayload(
                    series=(dt_plotting.PlotLinePayload(y=[0.0, 1.0], label="curve-1"),),
                ),
            ),
        )
    )

    assert isinstance(model_result, PlotResult)
    assert isinstance(raw_result, PlotResult)


def test_plotting_module_exports_plotter_first_types() -> None:
    assert FramePlotter.__module__ == "dyntool.plotting.plotters"
    assert StoryValuePlotter.__module__ == "dyntool.plotting.plotters"


def test_package_import_does_not_apply_default_zh_font_side_effect() -> None:
    original = list(plt.rcParams["font.sans-serif"])
    try:
        plt.rcParams["font.sans-serif"] = ["__sentinel_font__"]
        importlib.reload(dyntool)
        assert plt.rcParams["font.sans-serif"][0] == "__sentinel_font__"
    finally:
        plt.rcParams["font.sans-serif"] = original
        importlib.reload(dyntool)


def test_object_level_plotting_methods_are_removed() -> None:
    accel = AccelSeries.from_data([0.0, 0.1, -0.05], dt=0.01)
    sample = Sample.from_accel_data(
        [0.0, 0.1, -0.02],
        dt=0.01,
        sample_domain=SampleDomain.VIBRATION_TEST,
        metadata_cls=VibrationTestMetadata,
        **_make_vibration_kwargs(),
    )
    sample_set = SampleSet.from_samples([sample], sample_domain=SampleDomain.VIBRATION_TEST)

    assert not hasattr(accel, "plot")
    assert not hasattr(accel, "plot_static")
    assert not hasattr(sample, "plot")
    assert not hasattr(sample_set, "plot_sample")


def test_enum_only_guards() -> None:
    sample = Sample.from_accel_data(
        [0.0, 0.1, -0.02],
        dt=0.01,
        sample_domain=SampleDomain.VIBRATION_TEST,
        metadata_cls=VibrationTestMetadata,
        **_make_vibration_kwargs(),
    )
    sample_set = SampleSet.from_samples([sample], sample_domain=SampleDomain.VIBRATION_TEST)
    with pytest.raises(TypeError):
        sample_set.connect_storage(
            ".",
            storage_scheme="sample_dir",  # type: ignore[arg-type]
            mode=StorageMode.CREATE,
        )
    with pytest.raises(TypeError):
        sample_set.save(
            "tmp-invalid.h5",
            storage_scheme="set_h5",  # type: ignore[arg-type]
        )


def test_config_module_exposes_generic_loader() -> None:
    assert hasattr(dt_config, "Config")
    assert hasattr(dt_config, "load_config")
    assert not hasattr(dt_config, "get_preset_path")


def test_interfaces_package_is_removed() -> None:
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("dyntool.interfaces")
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("dyntool.interfaces.plot")
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("dyntool.interfaces.cli")


def test_legacy_models_module_is_removed() -> None:
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("dyntool.models")
    assert "dyntool.models" not in sys.modules


def test_compat_modules_are_removed() -> None:
    for module_name in (
        "dyntool._bootstrap_runtime",
        "dyntool._compat_warnings",
        "dyntool.compute.processing",
        "dyntool.domain.metadata._core",
    ):
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module(module_name)


def test_sample_compat_alias_methods_are_removed() -> None:
    sample = Sample.from_accel_data(
        [0.0, 0.1, -0.02],
        dt=0.01,
        sample_domain=SampleDomain.VIBRATION_TEST,
        metadata_cls=VibrationTestMetadata,
        **_make_vibration_kwargs(),
    )

    assert not hasattr(sample, "save_data")
    assert not hasattr(sample, "load_data")
