"""旧示例路径到当前场景实现的过渡运行器。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

import matplotlib
import numpy as np

import dyntool.logging as dt_logging
import dyntool.plotting as dt_plotting
from dyntool import (
    AccelSeries,
    DataModelBase,
    DynTool,
    LoggingMode,
    Metadata,
    PlotKind,
    Sample,
    SampleDomain,
    SampleSet,
    StorageScheme,
    TimeSeries,
    VibrationTestMetadata,
)

matplotlib.use("Agg")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
INPUT_DATA_DIR = PROJECT_ROOT / "examples" / "input_data"


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
    return Sample.from_accel_data(
        values,
        dt=0.01,
        sample_domain=SampleDomain.VIBRATION_TEST,
        metadata_cls=VibrationTestMetadata,
        **_make_vibration_kwargs(suffix=suffix),
    )


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

    sample = Sample.from_models(
        sample_domain=SampleDomain.VIBRATION_TEST,
        accel=normalized,
        **_make_vibration_kwargs(suffix="import"),
    )
    sample.eval_zvl(overwrite=True, freq_range=(2.0, 60.0))
    sample_set = SampleSet.from_samples([sample], sample_domain=SampleDomain.VIBRATION_TEST)
    sample_set.save(store_path, storage_scheme=StorageScheme.SET_H5)
    loaded = SampleSet.from_storage(
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
    sample_set = SampleSet.from_samples(samples, sample_domain=SampleDomain.VIBRATION_TEST)
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
    sample.calc_respspec(force=True)
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
    sample.eval_zvl(overwrite=True, freq_range=(2.0, 60.0))
    sample_set = SampleSet.from_samples([sample], sample_domain=SampleDomain.VIBRATION_TEST)
    sample_set.save(store_path, storage_scheme=StorageScheme.SET_H5)
    loaded = SampleSet.from_storage(
        store_path,
        sample_domain=SampleDomain.VIBRATION_TEST,
        storage_scheme=StorageScheme.SET_H5,
    )
    payload = loaded[sample.uid].accel.to_plot_payload(kind=PlotKind.TIME)  # type: ignore[union-attr]
    result = dt_plotting.render_payload(payload)
    assert result.figure is not None
    result.figure.savefig(plot_path, dpi=120)

    return {
        "loaded_count": len(loaded),
        "store_path": str(store_path),
        "plot_path": str(plot_path),
    }


def _scenario_plot_and_export(output_dir: Path | None = None) -> dict[str, object]:
    output_root = _ensure_output_dir(output_dir, "plot_and_export")
    raw_plot = output_root / "raw_time.png"
    model_plot = output_root / "model_time.png"

    accel = AccelSeries.from_data([0.0, 0.12, -0.03, 0.01], dt=0.01)
    payload = accel.to_plot_payload(kind=PlotKind.TIME)
    raw_result = dt_plotting.render_payload(payload)
    model_result = dt_plotting.render_payload(accel.to_plot_payload(kind=PlotKind.TIME))
    assert raw_result.figure is not None
    assert model_result.figure is not None
    raw_result.figure.savefig(raw_plot, dpi=120)
    model_result.figure.savefig(model_plot, dpi=120)

    return {
        "plot_kind": "time",
        "raw_plot": str(raw_plot),
        "model_plot": str(model_plot),
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

    tool = DynTool()
    freqs, _ = tool.resource.center_freqs(freq_range=(2.0, 80.0))
    sample = _make_vibration_sample(
        suffix="resource",
        values=np.sin(np.linspace(0.0, 2.0 * np.pi, 1024)) * 0.02,
    )
    sample.eval_otovl(freq_range=(2.0, 80.0))
    summary_path.write_text(
        f"freq_start={float(freqs[0])}\nfreq_end={float(freqs[-1])}\n",
        encoding="utf-8",
    )
    return {
        "freq_start": float(freqs[0]),
        "freq_end": float(freqs[-1]),
        "summary_path": str(summary_path),
    }


def _scenario_custom_extension(output_dir: Path | None = None) -> dict[str, object]:
    output_root = _ensure_output_dir(output_dir, "custom_extension")
    model_path = output_root / "jerk_series.csv"
    sample_set_dir = output_root / "custom_sample_set"

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

    sample = _make_vibration_sample(suffix="custom", values=[0.0, 0.1, -0.03, 0.02])
    sample_set = SampleSet.from_samples([sample], sample_domain=SampleDomain.VIBRATION_TEST)
    sample_set.save(sample_set_dir, storage_scheme=StorageScheme.SAMPLE_DIR)

    return {
        "registered_model_class": DataModelBase.from_category("ts_jerk_example").__name__,
        "sample_count": len(sample_set),
        "model_path": str(model_path),
        "sample_set_dir": str(sample_set_dir),
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
    source = SampleSet.from_samples(source_samples, sample_domain=SampleDomain.VIBRATION_TEST)
    source.eval_zvl(overwrite=True, freq_range=(2.0, 60.0))
    source.save(store_dir, storage_scheme=StorageScheme.SAMPLE_DIR, workers=2, chunk_size=1)

    keep_uid = source_samples[0].uid
    loaded = SampleSet.from_storage(
        store_dir,
        sample_domain=SampleDomain.VIBRATION_TEST,
        storage_scheme=StorageScheme.SAMPLE_DIR,
        filter=lambda item: item.uid == keep_uid,
        workers=2,
        chunk_size=1,
    )
    return {
        "source_count": len(source),
        "loaded_count": len(loaded),
        "evaluated_count": sum(1 for sample in loaded.values() if sample.zvl is not None),
    }


def _recipe_plot_payload_and_plotters(output_dir: Path | None = None) -> dict[str, object]:
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
    sample_set = SampleSet.from_samples([sample], sample_domain=SampleDomain.VIBRATION_TEST)
    sample_set.save(h5_path, storage_scheme=StorageScheme.SET_H5)
    sample_set.save(dir_path, storage_scheme=StorageScheme.SAMPLE_DIR)

    return {
        "h5_path": str(h5_path),
        "dir_path": str(dir_path),
        "model_path": str(model_path),
        "model_units": model_units,
    }


_LEGACY_EXAMPLE_DISPATCH: dict[str, Callable[[Path | None], dict[str, object]]] = {
    "examples/90_workflows/workflow_real_file_import.py": _scenario_import_and_normalize,
    "examples/05_sample_sets/sample_set_ops.py": _scenario_build_and_manage_samples,
    "examples/06_processing_evaluation/processing_eval.py": _scenario_evaluate_vibration,
    "examples/90_workflows/workflow_minimal_roundtrip.py": _scenario_store_and_reload,
    "examples/08_visualization/plotting_demo.py": _scenario_plot_and_export,
    "examples/90_workflows/workflow_logged_run.py": _scenario_logged_run,
    "examples/90_workflows/workflow_resource_driven_eval.py": _scenario_resource_driven_eval,
    "examples/11_custom_extension/custom_domain_extension.py": _scenario_custom_extension,
    "examples/02_units/unit_views.py": _recipe_units_and_unit_views,
    "examples/03_metadata/metadata_domains.py": _recipe_metadata_patterns,
    "examples/90_workflows/workflow_sample_set_batch.py": _recipe_sample_set_filter_parallel_io,
    "examples/09_logging_config/logging_modes.py": _recipe_logging_providers_and_modes,
    "examples/07_storage_io/storage_schemes.py": _recipe_storage_scheme_selection,
}


def run_legacy_example(relative_path: str, output_dir: Path | None = None) -> dict[str, object]:
    """执行旧示例路径对应的当前实现。"""

    try:
        runner = _LEGACY_EXAMPLE_DISPATCH[relative_path]
    except KeyError as exc:
        raise FileNotFoundError(f"未注册的旧示例路径: {relative_path}") from exc
    return runner(output_dir)
