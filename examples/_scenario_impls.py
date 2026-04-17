"""示例场景与 recipes 的共享实现。"""

from __future__ import annotations

from importlib import import_module
from pathlib import Path
from typing import Any, ClassVar

import matplotlib
import numpy as np

import dyntool.logging as dt_logging
import dyntool.plotting as dt_plotting
import dyntool.reporting as dt_reporting
import dyntool.resources as dt_resource
import dyntool.storage as dt_storage
from dyntool import (
    AccelSeries,
    DefaultSample,
    DefaultSampleSet,
    OTOVLLimit,
    OTOVLLimitStandard,
    LoggingMode,
    Metadata,
    ZVLLimit,
    ZVLLimitStandard,
    SampleDomain,
    StorageScheme,
    TimeSeries,
    VibrationTestMetadata,
)

matplotlib.use("Agg")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
INPUT_DATA_DIR = PROJECT_ROOT / "examples" / "input_data"
PLOT_THEME_REPORT = PROJECT_ROOT / "src" / "dyntool" / "plotting" / "assets" / "plot_theme_report.toml"


def _ensure_output_dir(output_dir: Path | None, name: str) -> Path:
    target = output_dir or PROJECT_ROOT / "tmp" / "examples" / name
    target.mkdir(parents=True, exist_ok=True)
    return target


def _make_vibration_kwargs(*, suffix: str) -> dict[str, str]:
    return {
        "case": f"case-{suffix}",
        "point": "P1",
        "instr": f"ACC-{suffix}",
        "dir": "Z",
        "record": "R1",
        "timestamp": "2026-03-16 12:00:00",
    }


def _make_vibration_sample(*, suffix: str, values: list[float] | np.ndarray) -> Any:
    return DefaultSample.from_accel_data(
        values,
        dt=0.01,
        sample_domain=SampleDomain.VIBRATION_TEST,
        metadata_cls=VibrationTestMetadata,
        **_make_vibration_kwargs(suffix=suffix),
    )


def _make_reporting_sample_set(*, suffix: str, with_eval: bool = False) -> Any:
    axis = np.linspace(0.0, 20.47, 2048, dtype=float)
    sample_a = _make_vibration_sample(
        suffix=f"{suffix}-a",
        values=np.sin(axis * 2.0 * np.pi * 1.5) * 0.08,
    )
    sample_b = _make_vibration_sample(
        suffix=f"{suffix}-b",
        values=np.cos(axis * 2.0 * np.pi * 0.75) * 0.05,
    )
    sample_set = DefaultSampleSet.from_samples(
        [sample_a, sample_b],
        sample_domain=SampleDomain.VIBRATION_TEST,
    )
    if with_eval:
        sample_set.eval_zvl(overwrite=True, freq_range=(2.0, 60.0))
        sample_set.eval_otovl(overwrite=True, freq_range=(2.0, 80.0))
    return sample_set


def _scenario_import_and_normalize(output_dir: Path | None = None) -> dict[str, object]:
    output_root = _ensure_output_dir(output_dir, "import_and_normalize")
    source = INPUT_DATA_DIR / "simple_accel_with_units.csv"
    normalized_csv = output_root / "normalized.csv"
    store_path = output_root / "sample_set.h5"

    accel = AccelSeries.from_csv(source)
    normalized = accel.convert_units(
        {"time": "second", "value": "meter/second**2"},
        replace=False,
    )
    normalized.to_csv(normalized_csv)
    inspected = AccelSeries.inspect_units(normalized_csv, fmt="csv")

    sample = DefaultSample.from_models(
        sample_domain=SampleDomain.VIBRATION_TEST,
        accel=normalized,
        **_make_vibration_kwargs(suffix="import"),
    )
    sample.eval_zvl(overwrite=True, freq_range=(2.0, 60.0))
    sample_set = DefaultSampleSet.from_samples([sample], sample_domain=SampleDomain.VIBRATION_TEST)
    sample_set.save(store_path, storage_scheme=StorageScheme.SET_H5)
    loaded = DefaultSampleSet.from_storage(
        store_path,
        sample_domain=SampleDomain.VIBRATION_TEST,
        storage_scheme=StorageScheme.SET_H5,
    )

    return {
        "source": str(source),
        "normalized_csv": str(normalized_csv),
        "store_path": str(store_path),
        "inspected_units": inspected,
        "has_zvl": loaded[sample.uid].zvl is not None,
    }


def _scenario_build_and_manage_samples(output_dir: Path | None = None) -> dict[str, object]:
    _ = output_dir
    samples = [
        _make_vibration_sample(suffix="build-a", values=[0.0, 0.1, -0.02, 0.04]),
        _make_vibration_sample(suffix="build-b", values=[0.0, -0.05, 0.03, 0.02]),
    ]
    sample_set = DefaultSampleSet.from_samples(samples, sample_domain=SampleDomain.VIBRATION_TEST)
    sample_set.eval_zvl(overwrite=True, freq_range=(2.0, 60.0))
    evaluated_count = sum(1 for sample in sample_set.values() if sample.zvl is not None)
    return {
        "sample_count": len(sample_set),
        "evaluated_count": evaluated_count,
    }


def _scenario_evaluate_vibration(output_dir: Path | None = None) -> dict[str, object]:
    _ = output_dir
    sample = _make_vibration_sample(
        suffix="eval",
        values=np.sin(np.linspace(0.0, 4.0 * np.pi, 512)) * 0.05,
    )
    sample.calc_freqspec()
    sample.calc_respspec(overwrite=True)
    sample.eval_zvl(overwrite=True, freq_range=(2.0, 60.0))
    return {
        "freqspec_type": type(sample.freqspec).__name__,
        "respspec_type": type(sample.respspec).__name__,
        "has_zvl": sample.zvl is not None,
    }


def _scenario_store_and_reload(output_dir: Path | None = None) -> dict[str, object]:
    output_root = _ensure_output_dir(output_dir, "store_and_reload")
    store_path = output_root / "sample_set.h5"
    plot_path = output_root / "sample_set.png"

    sample = _make_vibration_sample(suffix="store", values=[0.0, 0.08, -0.02, 0.03, 0.0])
    sample.calc_freqspec(overwrite=True)
    sample.calc_respspec(overwrite=True)
    sample.eval_zvl(overwrite=True, freq_range=(2.0, 60.0))
    sample_set = DefaultSampleSet.from_samples([sample], sample_domain=SampleDomain.VIBRATION_TEST)
    sample_set.save(store_path, storage_scheme=StorageScheme.SET_H5)
    loaded = DefaultSampleSet.from_storage(
        store_path,
        sample_domain=SampleDomain.VIBRATION_TEST,
        storage_scheme=StorageScheme.SET_H5,
    )
    theme = dt_plotting.PlotTheme.from_file(PLOT_THEME_REPORT)
    dataset = dt_plotting.PlotDataset.from_model(
        loaded[sample.uid].accel,  # type: ignore[arg-type]
        name="stored-accel",
        category=dt_plotting.PlotCategory.SAMPLE,
    )
    result = dt_plotting.FramePlotter(theme=theme).plot_dataset(dataset)
    assert result.figure is not None
    result.figure.savefig(plot_path, dpi=120)

    return {
        "loaded_count": len(loaded),
        "store_path": str(store_path),
        "plot_path": str(plot_path),
        "freqspec_restored": loaded[sample.uid].freqspec is not None,
        "respspec_restored": loaded[sample.uid].respspec is not None,
    }


def _scenario_plot_and_export(output_dir: Path | None = None) -> dict[str, object]:
    output_root = _ensure_output_dir(output_dir, "plot_and_export")
    raw_plot = output_root / "raw_time.png"
    model_plot = output_root / "model_time.png"
    box_plot = output_root / "box_zvl.png"

    theme = dt_plotting.PlotTheme.from_file(PLOT_THEME_REPORT)
    accel = AccelSeries.from_data([0.0, 0.12, -0.03, 0.01], dt=0.01)
    raw_dataset = dt_plotting.PlotDataset.from_axis_value(
        axis=accel.get_axis(),
        value=accel.get_value(),
        name="raw-accel",
        category=dt_plotting.PlotCategory.SAMPLE,
        axis_unit=accel.axis_unit,
        value_unit=accel.value_unit,
    )
    raw_result = dt_plotting.FramePlotter(theme=theme).plot_dataset(raw_dataset)
    model_dataset = dt_plotting.PlotDataset.from_model(
        accel,
        name="model-accel",
        category=dt_plotting.PlotCategory.SAMPLE,
    )
    model_result = dt_plotting.FramePlotter(theme=theme).plot_dataset(model_dataset)
    box_dataset = dt_plotting.PlotDataset.from_axis_value(
        axis=[0.0, 1.0, 2.0],
        value=[64.0, 66.0, 65.0],
        name="point-a",
        category=dt_plotting.PlotCategory.SAMPLE,
        value_unit="decibel",
        label="A点",
    )
    box_dataset.add_axis_value(
        axis=[0.0, 1.0, 2.0],
        value=[68.0, 69.0, 70.0],
        name="point-b",
        category=dt_plotting.PlotCategory.SAMPLE,
        value_unit="decibel",
        label="B点",
    )
    box_result = dt_plotting.BoxPlotter().plot_dataset(
        box_dataset,
        stats=[dt_plotting.PlotStatMetric.MEAN, dt_plotting.PlotStatMetric.MEDIAN],
        style_defaults={
            "box.facecolor": "#dddddd",
            "mean.color": "blue",
            "flier.markerfacecolor": "red",
        },
        legend_options={"loc": "upper right"},
    )
    assert raw_result.figure is not None
    assert model_result.figure is not None
    assert box_result.figure is not None
    raw_result.figure.savefig(raw_plot, dpi=120)
    model_result.figure.savefig(model_plot, dpi=120)
    box_result.figure.savefig(box_plot, dpi=120)

    return {
        "plot_kind": "time",
        "raw_plot": str(raw_plot),
        "model_plot": str(model_plot),
        "box_plot": str(box_plot),
        "theme_path": str(PLOT_THEME_REPORT),
    }


def _scenario_logged_run(output_dir: Path | None = None) -> dict[str, object]:
    output_root = _ensure_output_dir(output_dir, "logged_run")
    log_dir = output_root / "logs"
    dt_logging.configure_logging(
        mode=LoggingMode.DIRECTORY,
        log_dir=log_dir,
        level="INFO",
        mirror_to_console=False,
    )

    sample = _make_vibration_sample(suffix="logged", values=[0.0, 0.05, -0.01, 0.02, 0.0])
    sample.eval_zvl(overwrite=True, freq_range=(2.0, 60.0))
    dt_logging.get_logger("evaluation").info("logged run complete")

    return {
        "has_zvl": sample.zvl is not None,
        "evaluation_log_exists": (log_dir / "evaluation.log").exists(),
        "log_dir": str(log_dir),
    }


def _scenario_resource_driven_eval(output_dir: Path | None = None) -> dict[str, object]:
    output_root = _ensure_output_dir(output_dir, "resource_driven_eval")
    summary_path = output_root / "resource_summary.txt"

    freqs, _ = dt_resource.center_freqs((2.0, 80.0))
    city_limit = ZVLLimit.from_standard(
        ZVLLimitStandard.GB_10070_1988,
        scene="特殊住宅区昼间",
    )
    otovl_limit = OTOVLLimit.from_standard(
        OTOVLLimitStandard.GB_T_50355_2018,
        scene="卧室昼间一级",
    )
    sample = _make_vibration_sample(
        suffix="resource",
        values=np.sin(np.linspace(0.0, 2.0 * np.pi, 1024)) * 0.02,
    )
    sample.eval_otovl(freq_range=(2.0, 80.0))
    summary_path.write_text(
        (
            f"freq_start={float(freqs[0])}\n"
            f"freq_end={float(freqs[-1])}\n"
            f"city_limit={float(city_limit.zvl.flat[0])}\n"
            f"otovl_scene={otovl_limit.scene}\n"
        ),
        encoding="utf-8",
    )
    return {
        "freq_start": float(freqs[0]),
        "freq_end": float(freqs[-1]),
        "city_limit": float(city_limit.zvl.flat[0]),
        "otovl_scene": otovl_limit.scene,
        "summary_path": str(summary_path),
    }


def _scenario_custom_extension(output_dir: Path | None = None) -> dict[str, object]:
    output_root = _ensure_output_dir(output_dir, "custom_extension")
    model_path = output_root / "jerk_series.csv"
    sample_path = output_root / "external_sample.h5"
    plot_path = output_root / "external_sample_plot.png"

    metadata_schema_mod = import_module("dyntool.domain.metadata.schema")
    metadata_registry_mod = import_module("dyntool.domain.metadata.registry")
    samples_mod = import_module("dyntool.domain.samples")
    samples_registry_mod = import_module("dyntool.domain.samples.registry")
    samples_schema_mod = import_module("dyntool.domain.samples.schema")
    pydantic_mod = import_module("pydantic")
    vibration_sample_mod = import_module("dyntool.domain.samples.vibration_test")

    MetadataSchema = metadata_schema_mod.MetadataSchema
    SampleSchema = samples_schema_mod.SampleSchema
    sample_from_structured_payload = samples_mod.sample_from_structured_payload
    payload_category_map = metadata_registry_mod._PAYLOAD_CATEGORY_TO_CLS
    payload_domain_map = metadata_registry_mod._PAYLOAD_DOMAIN_TO_CLS
    sample_category_map = samples_registry_mod._SAMPLE_CATEGORY_MAP
    sample_set_category_map = samples_registry_mod._SAMPLE_SET_CATEGORY_MAP
    Field = pydantic_mod.Field
    VibrationTestSample = vibration_sample_mod.VibrationTestSample
    VibrationTestSampleSet = vibration_sample_mod.VibrationTestSampleSet

    class ExternalVibrationMetadata(VibrationTestMetadata):
        """外部 consumer 侧示例元数据。"""

        payload_domain: ClassVar[str] = "external_vibration_test"
        metadata_schema: ClassVar[Any] = MetadataSchema(
            name="external_vibration_test_metadata",
            identity_fields=("case", "point", "instr", "dir", "record", "timestamp"),
        )

    class ExternalVibrationSample(VibrationTestSample):
        """外部 consumer 侧示例样本。"""

        _payload_domain: ClassVar[str] = "external_vibration_test"
        metadata: ExternalVibrationMetadata = Field(..., description="外部样本元数据")
        sample_schema: ClassVar[Any] = SampleSchema(
            name="external_vibration_test_sample",
            metadata_type=ExternalVibrationMetadata,
            slots=VibrationTestSample.sample_schema.slots,
        )

    class ExternalVibrationSampleSet(VibrationTestSampleSet):
        """外部 consumer 侧示例样本集。"""

        _sample_type: ClassVar[type[ExternalVibrationSample]] = ExternalVibrationSample
        _payload_domain: ClassVar[str] = "external_vibration_test"

    ExternalVibrationSample._sample_set_type = ExternalVibrationSampleSet

    class _RegistryBridge:
        """在示例期间注册外部类型，演示 consumer 侧 bridge。"""

        def __enter__(self) -> "_RegistryBridge":
            self._metadata_category = dict(payload_category_map)
            self._metadata_domain = dict(payload_domain_map)
            self._sample_category = dict(sample_category_map)
            self._sample_set_category = dict(sample_set_category_map)
            payload_category_map["ExternalVibrationMetadata"] = ExternalVibrationMetadata
            payload_domain_map["external_vibration_test"] = ExternalVibrationMetadata
            sample_category_map["ExternalVibrationSample"] = ExternalVibrationSample
            sample_set_category_map["ExternalVibrationSampleSet"] = ExternalVibrationSampleSet
            return self

        def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
            payload_category_map.clear()
            payload_category_map.update(self._metadata_category)
            payload_domain_map.clear()
            payload_domain_map.update(self._metadata_domain)
            sample_category_map.clear()
            sample_category_map.update(self._sample_category)
            sample_set_category_map.clear()
            sample_set_category_map.update(self._sample_set_category)

    class JerkSeries(TimeSeries):
        category = "ts_jerk_example"

        @classmethod
        def _base_value_unit(cls) -> str:
            return "meter/second**3"

    jerk = JerkSeries.from_data(
        [0.0, 0.4, -0.2, 0.1],
        dt=0.01,
        axis_unit="second",
        data_unit="meter/second**3",
    )
    jerk.to_csv(model_path)

    values = np.array([0.0, 0.1, -0.03, 0.02, -0.01, 0.04, -0.02, 0.01], dtype=float)
    vib_sample = _make_vibration_sample(suffix="custom-vib", values=values)
    with _RegistryBridge():
        external_sample = ExternalVibrationSample.from_accel_data(
            values,
            dt=0.01,
            metadata_cls=ExternalVibrationMetadata,
            **_make_vibration_kwargs(suffix="custom-ext"),
        )
        external_set = ExternalVibrationSampleSet.from_samples([external_sample])
        compute_result = external_sample.compute.evaluate.zvl(overwrite=True, freq_range=(2.0, 60.0))
        convenience_sample = ExternalVibrationSample.from_accel_data(
            values,
            dt=0.01,
            metadata_cls=ExternalVibrationMetadata,
            **_make_vibration_kwargs(suffix="custom-ext"),
        )
        convenience_result = convenience_sample.eval_zvl(overwrite=True, freq_range=(2.0, 60.0))
        vib_sample.compute.evaluate.zvl(overwrite=True, freq_range=(2.0, 60.0))

        payload_roundtrip = sample_from_structured_payload(external_sample.to_structured_payload())
        external_set.save(sample_path, storage_scheme=StorageScheme.SET_H5)
        loaded_set = ExternalVibrationSampleSet.from_storage(sample_path, storage_scheme=StorageScheme.SET_H5)
        loaded_sample = next(iter(loaded_set.values()))

        assert loaded_sample.accel is not None
        dataset = dt_plotting.PlotDataset.from_axis_value(
            axis=loaded_sample.accel.get_axis(),
            value=loaded_sample.accel.get_value(),
            name="external-accel",
            category=dt_plotting.PlotCategory.SAMPLE,
            axis_unit=loaded_sample.accel.axis_unit,
            value_unit=loaded_sample.accel.value_unit,
        )
        plot_result = dt_plotting.FramePlotter().plot_dataset(dataset)
        assert plot_result.figure is not None
        plot_result.figure.savefig(plot_path, dpi=120)

        external_zvl = float(np.asarray(external_sample.zvl.get_field("zvl")).flat[0])  # type: ignore[union-attr]
        convenience_zvl = float(np.asarray(convenience_sample.zvl.get_field("zvl")).flat[0])  # type: ignore[union-attr]
        vib_zvl = float(np.asarray(vib_sample.zvl.get_field("zvl")).flat[0])  # type: ignore[union-attr]

    return {
        "registered_model_class": TimeSeries.from_category("ts_jerk_example").__name__,
        "external_sample_type": type(external_sample).__name__,
        "external_sample_set_type": type(external_set).__name__,
        "payload_roundtrip_type": type(payload_roundtrip).__name__,
        "storage_roundtrip_type": type(loaded_sample).__name__,
        "sample_count": len(external_set),
        "compute_path_ok": compute_result.success is True,
        "convenience_path_ok": convenience_result.success is True,
        "compute_vs_convenience_match": bool(np.isclose(external_zvl, convenience_zvl, atol=1e-9)),
        "external_vs_vibtest_match": bool(np.isclose(external_zvl, vib_zvl, atol=1e-9)),
        "model_path": str(model_path),
        "sample_set_dir": str(sample_path),
        "plot_path": str(plot_path),
    }


def _recipe_units_and_unit_views(output_dir: Path | None = None) -> dict[str, object]:
    output_root = _ensure_output_dir(output_dir, "units_and_unit_views")
    saved_path = output_root / "units_roundtrip.csv"
    accel = AccelSeries.from_csv(INPUT_DATA_DIR / "simple_accel_with_units.csv")
    converted = accel.convert_units({"time": "second", "value": "meter/second**2"}, replace=False)
    converted.to_csv(saved_path)
    return {
        "saved_path": str(saved_path),
        "saved_units": AccelSeries.inspect_units(saved_path, fmt="csv"),
    }


def _recipe_metadata_patterns(output_dir: Path | None = None) -> dict[str, object]:
    _ = output_dir
    default_meta = Metadata(attributes={"source": "demo"})
    vibration_meta = VibrationTestMetadata(**_make_vibration_kwargs(suffix="meta"))
    return {
        "default_type": type(default_meta).__name__,
        "vibration_type": type(vibration_meta).__name__,
    }


def _recipe_sample_set_filter_parallel_io(output_dir: Path | None = None) -> dict[str, object]:
    output_root = _ensure_output_dir(output_dir, "sample_set_filter_parallel_io")
    store_dir = output_root / "sample_dir"
    source_samples = [
        _make_vibration_sample(suffix="batch-a", values=[0.0, 0.1, -0.02, 0.03]),
        _make_vibration_sample(suffix="batch-b", values=[0.0, -0.04, 0.01, 0.02]),
    ]
    source = DefaultSampleSet.from_samples(source_samples, sample_domain=SampleDomain.VIBRATION_TEST)
    source.eval_zvl(overwrite=True, freq_range=(2.0, 60.0))
    source.save(store_dir, storage_scheme=StorageScheme.SET_DIR, workers=2, chunk_size=1)

    keep_uid = source_samples[0].uid
    loaded = DefaultSampleSet.from_storage(
        store_dir,
        sample_domain=SampleDomain.VIBRATION_TEST,
        storage_scheme=StorageScheme.SET_DIR,
        filter=lambda item: item.uid == keep_uid,
        workers=2,
        chunk_size=1,
    )
    return {
        "source_count": len(source),
        "loaded_count": len(loaded),
        "evaluated_count": sum(1 for sample in loaded.values() if sample.zvl is not None),
    }


def _recipe_plot_dataset_and_plotters(output_dir: Path | None = None) -> dict[str, object]:
    return _scenario_plot_and_export(output_dir)


def _recipe_logging_providers_and_modes(output_dir: Path | None = None) -> dict[str, object]:
    output_root = _ensure_output_dir(output_dir, "logging_providers_and_modes")
    single_file = output_root / "single.log"
    directory_dir = output_root / "logs"

    dt_logging.configure_logging(
        mode=LoggingMode.SINGLE_FILE,
        log_file=single_file,
        mirror_to_console=False,
    )
    default_provider = dt_logging.get_active_provider_name()
    dt_logging.get_logger("storage").info("single file log")

    dt_logging.configure_logging(
        provider="stdlib",
        mode=LoggingMode.DIRECTORY,
        log_dir=directory_dir,
        mirror_to_console=False,
    )
    dt_logging.get_logger("storage").info("directory file log")

    return {
        "single_exists": single_file.exists(),
        "directory_exists": (directory_dir / "storage.log").exists(),
        "single_file": str(single_file),
        "directory_log": str(directory_dir / "storage.log"),
        "default_provider": default_provider,
        "stdlib_provider": dt_logging.get_active_provider_name(),
        "loguru_available": "loguru" in dt_logging.available_providers(),
    }


def _recipe_storage_scheme_selection(output_dir: Path | None = None) -> dict[str, object]:
    output_root = _ensure_output_dir(output_dir, "storage_scheme_selection")
    h5_path = output_root / "sample_set.h5"
    dir_path = output_root / "sample_set_dir"
    model_path = output_root / "accel.csv"

    accel = AccelSeries.from_data([0.0, 0.1, -0.02, 0.04], dt=0.01)
    accel.to_csv(model_path)
    model_units = AccelSeries.inspect_units(model_path, fmt="csv")

    sample = _make_vibration_sample(suffix="scheme", values=[0.0, 0.1, -0.02, 0.04])
    sample_set = DefaultSampleSet.from_samples([sample], sample_domain=SampleDomain.VIBRATION_TEST)
    sample_set.save(h5_path, storage_scheme=StorageScheme.SET_H5)
    sample_set.save(dir_path, storage_scheme=StorageScheme.SET_DIR)

    return {
        "h5_path": str(h5_path),
        "dir_path": str(dir_path),
        "model_path": str(model_path),
        "model_units": model_units,
    }


def _recipe_compute_flow(output_dir: Path | None = None) -> dict[str, object]:
    output_root = _ensure_output_dir(output_dir, "compute_flow")
    sample = _make_vibration_sample(
        suffix="flow",
        values=np.sin(np.linspace(0.0, 6.0 * np.pi, 1024)) * 0.05,
    )
    assert sample.accel is not None
    original_values = sample.accel.get_value().copy()

    flow = sample.compute.flow(source="accel")
    flow.checkpoint("raw")
    flow.truncate(0.2, 1.2).checkpoint("trimmed")
    branch = flow.branch("hp-branch")
    preview = branch.highpass(1.0).commit(replace=False)
    comparison = branch.compare("trimmed")

    flow.restore("trimmed")
    flow.lowpass(30.0).commit(replace=True)
    freq_result = sample.compute.spectrum.freqspec(source="accel", overwrite=True)

    return {
        "preview_type": type(preview).__name__,
        "sample_type": type(sample).__name__,
        "preview_is_detached": bool(preview is not sample.accel),
        "final_length": int(sample.accel.get_value().shape[0]),
        "original_length": int(original_values.shape[0]),
        "branch_history_len": len(branch.history()),
        "flow_history_len": len(flow.history()),
        "compare_same_type": bool(comparison.get("same_type", False)),
        "freqspec_success": bool(freq_result.success),
        "freqspec_type": type(sample.freqspec).__name__,
        "output_dir": str(output_root),
    }


def _recipe_compute_plan(output_dir: Path | None = None) -> dict[str, object]:
    output_root = _ensure_output_dir(output_dir, "compute_plan")
    compute_api = import_module("dyntool.domain.compute_api")
    ComputePlan = getattr(compute_api, "ComputePlan")
    ComputeStep = getattr(compute_api, "ComputeStep")

    sample_a = _make_vibration_sample(
        suffix="plan-a",
        values=np.sin(np.linspace(0.0, 4.0 * np.pi, 512)) * 0.03,
    )
    sample_b = _make_vibration_sample(
        suffix="plan-b",
        values=np.sin(np.linspace(0.0, 4.0 * np.pi, 512) + np.pi / 4.0) * 0.04,
    )
    sample_set = DefaultSampleSet.from_samples([sample_a, sample_b], sample_domain=SampleDomain.VIBRATION_TEST)

    plan = sample_a.compute.plan.create(
        name="demo-flow-plan",
        default_source="accel",
        metadata={"owner": "recipe"},
        steps=[
            ComputeStep(group="process", method="pipeline", params={"highpass": 1.0}),
            ComputeStep(group="spectrum", method="freqspec", params={}),
        ],
    )
    payload = plan.to_dict()
    restored = ComputePlan.from_dict(payload)
    results = [sample.compute.run_plan(restored, overwrite=True) for sample in sample_set.values()]
    payload_path = output_root / "compute_plan.json"
    payload_path.write_text(str(payload), encoding="utf-8")

    return {
        "plan_name": restored.name,
        "schema_version": restored.schema_version,
        "plan_kind": restored.plan_kind,
        "step_count": len(restored.steps),
        "all_success": all(result.success for result in results),
        "freqspec_ready_count": sum(1 for sample in sample_set.values() if sample.freqspec is not None),
        "payload_path": str(payload_path),
    }


def _recipe_scalar_frame_features(output_dir: Path | None = None) -> dict[str, object]:
    output_root = _ensure_output_dir(output_dir, "scalar_frame_features")
    store_path = output_root / "scalar_features.h5"
    sample_a = _make_vibration_sample(suffix="scalar-a", values=[0.0, 0.2, -0.1, 0.05, 0.0])
    sample_b = DefaultSample.from_models(
        sample_domain=SampleDomain.VIBRATION_TEST,
        metadata=VibrationTestMetadata(**_make_vibration_kwargs(suffix="scalar-b")),
    )
    source = DefaultSampleSet.from_samples([sample_a, sample_b], sample_domain=SampleDomain.VIBRATION_TEST)
    source.save(store_path, storage_scheme=StorageScheme.SET_H5)
    loaded = DefaultSampleSet.from_storage(
        store_path,
        sample_domain=SampleDomain.VIBRATION_TEST,
        storage_scheme=StorageScheme.SET_H5,
        load_mode=dt_storage.SampleLoadMode.LAZY,
    )
    subset = loaded.find_many(
        view_options=dt_storage.SampleSetViewOptions(
            load_mode=dt_storage.SampleLoadMode.LAZY,
            access_mode=dt_storage.StorageAccessMode.READ_ONLY,
        )
    )
    strict_error = ""
    try:
        subset.scalar_frame(features=["pga", "rms"], strict=True)
    except Exception as exc:  # pragma: no cover - recipe path summary only
        strict_error = str(exc)
    frame = subset.scalar_frame(features=["pga", "rms"], strict=False)
    return {
        "lazy_load_mode": subset[sample_a.uid].load_mode.value,
        "strict_error": strict_error,
        "row_count": len(frame),
        "pga_nan_count": int(frame["pga"].isna().sum()),
        "rms_nan_count": int(frame["rms"].isna().sum()),
        "columns": frame.columns.tolist(),
    }


def _recipe_series_frame_alignment(output_dir: Path | None = None) -> dict[str, object]:
    output_root = _ensure_output_dir(output_dir, "series_frame_alignment")
    sample_a = DefaultSample(
        metadata=Metadata(attributes={"line": "L1"}),
        accel=AccelSeries.from_data(np.array([0.0, 1.0, 2.0, 3.0]), dt=1.0),
    )
    sample_b = DefaultSample(
        metadata=Metadata(attributes={"line": "L2"}),
        accel=AccelSeries.from_data(np.array([10.0, 20.0, 30.0]), time=np.array([1.0, 2.0, 4.0])),
    )
    sample_c = DefaultSample(metadata=Metadata(attributes={"line": "L3"}))
    sample_set = DefaultSampleSet.from_samples([sample_a, sample_b, sample_c])
    frame = sample_set.series_frame("accel", metadata_fields=["attributes@line"], strict=False)
    return {
        "index_name": frame.index.name,
        "row_count": len(frame),
        "column_levels": frame.columns.nlevels,
        "nan_count": int(frame.isna().sum().sum()),
        "line_labels": sorted({column[2] for column in frame.columns}),
        "output_dir": str(output_root),
    }


def _recipe_peaks_frame(output_dir: Path | None = None) -> dict[str, object]:
    output_root = _ensure_output_dir(output_dir, "peaks_frame")
    sample_a = DefaultSample(
        metadata=Metadata(attributes={"line": "L1"}),
        accel=AccelSeries.from_data(np.array([0.0, 2.0, 0.0, 1.0, 0.0, 3.0, 0.0]), dt=1.0),
    )
    sample_b = DefaultSample(
        metadata=Metadata(attributes={"line": "L2"}),
        accel=AccelSeries.from_data(np.array([0.0, 1.5, 0.0]), dt=1.0),
    )
    sample_set = DefaultSampleSet.from_samples([sample_a, sample_b])
    frame = sample_set.peaks_frame(
        source="accel",
        metadata_fields=["attributes@line"],
        prominence=0.5,
        distance=1,
    )
    return {
        "index_name": frame.index.name,
        "row_count": len(frame),
        "column_levels": frame.columns.nlevels,
        "nan_count": int(frame.isna().sum().sum()),
        "value_columns": sorted({column[-1] for column in frame.columns}),
        "output_dir": str(output_root),
    }


def _recipe_statistics_export(output_dir: Path | None = None) -> dict[str, object]:
    output_root = _ensure_output_dir(output_dir, "statistics_export")
    sample_set = _make_reporting_sample_set(suffix="statistics", with_eval=True)

    scalar_path = sample_set.export_scalar_frame(
        output_root / "scalar_frame.xlsx",
        features=["pga", "rms"],
    )
    series_path = sample_set.export_series_frame(
        output_root / "series_frame.csv",
        data_var="accel",
        format="csv",
    )
    peaks_path = sample_set.export_peaks_frame(
        output_root / "peaks_frame.xlsx",
        source="accel",
    )
    compare_path = dt_reporting.export_compare_report(
        sample_set,
        _make_reporting_sample_set(suffix="statistics-compare", with_eval=True),
        output_root / "compare_report.xlsx",
        features=["pga", "rms"],
    )

    scalar_frame = sample_set.scalar_frame(features=["pga", "rms"], strict=False)
    return {
        "sample_count": len(sample_set),
        "scalar_path": str(scalar_path),
        "series_path": str(series_path),
        "peaks_path": str(peaks_path),
        "compare_path": str(compare_path),
        "scalar_columns": [str(column) for column in scalar_frame.columns],
    }


def _recipe_report_package_export(output_dir: Path | None = None) -> dict[str, object]:
    output_root = _ensure_output_dir(output_dir, "report_package_export")
    sample_set = _make_reporting_sample_set(suffix="report", with_eval=True)
    compare_to = _make_reporting_sample_set(suffix="report-compare", with_eval=True)

    package_dir = sample_set.export_report_package(
        output_root / "report_package",
        compare_to=compare_to,
        features=["pga", "rms"],
        series_vars=["accel"],
        peak_sources=["accel"],
        include_plots=True,
        include_eval_summary=True,
    )

    return {
        "package_dir": str(package_dir),
        "report_workbook": str(package_dir / "report.xlsx"),
        "manifest_path": str(package_dir / "manifest.json"),
        "metadata_summary_path": str(package_dir / "metadata_summary.json"),
        "tables_dir": str(package_dir / "tables"),
        "figures_dir": str(package_dir / "figures"),
    }


__all__ = [
    "_scenario_import_and_normalize",
    "_scenario_build_and_manage_samples",
    "_scenario_evaluate_vibration",
    "_scenario_store_and_reload",
    "_scenario_plot_and_export",
    "_scenario_logged_run",
    "_scenario_resource_driven_eval",
    "_scenario_custom_extension",
    "_recipe_units_and_unit_views",
    "_recipe_metadata_patterns",
    "_recipe_sample_set_filter_parallel_io",
    "_recipe_plot_dataset_and_plotters",
    "_recipe_logging_providers_and_modes",
    "_recipe_storage_scheme_selection",
    "_recipe_compute_flow",
    "_recipe_compute_plan",
    "_recipe_scalar_frame_features",
    "_recipe_series_frame_alignment",
    "_recipe_peaks_frame",
    "_recipe_statistics_export",
    "_recipe_report_package_export",
]
