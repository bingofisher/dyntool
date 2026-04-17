"""Recipe 示例 smoke 测试。"""

from __future__ import annotations

from pathlib import Path

import matplotlib

from .example_runner import PROJECT_ROOT, run_example

matplotlib.use("Agg")


def test_recipe_units_and_unit_views(tmp_path: Path) -> None:
    result = run_example(
        "examples/90_recipes/units_and_unit_views/main.py",
        output_dir=tmp_path / "units_and_unit_views",
    )
    assert Path(result["saved_path"]).exists()
    assert result["saved_units"]["time"] == "second"


def test_recipe_metadata_patterns() -> None:
    result = run_example("examples/90_recipes/metadata_patterns/main.py")
    assert result["default_type"] == "Metadata"
    assert result["vibration_type"] == "VibrationTestMetadata"


def test_recipe_sample_set_filter_parallel_io(tmp_path: Path) -> None:
    result = run_example(
        "examples/90_recipes/sample_set_filter_parallel_io/main.py",
        output_dir=tmp_path / "sample_set_filter_parallel_io",
    )
    assert result["source_count"] == 2
    assert result["loaded_count"] == 1
    assert result["evaluated_count"] == 1


def test_recipe_plot_dataset_and_plotters(tmp_path: Path) -> None:
    result = run_example(
        "examples/90_recipes/plot_dataset_and_plotters/main.py",
        output_dir=tmp_path / "plot_dataset_and_plotters",
    )
    assert result["plot_kind"] == "time"
    assert Path(result["raw_plot"]).exists()
    assert Path(result["model_plot"]).exists()
    assert Path(result["box_plot"]).exists()


def test_recipe_logging_providers_and_modes(tmp_path: Path) -> None:
    result = run_example(
        "examples/90_recipes/logging_providers_and_modes/main.py",
        output_dir=tmp_path / "logging_providers_and_modes",
    )
    assert result["single_exists"] is True
    assert result["directory_exists"] is True
    assert Path(result["single_file"]).exists()
    assert Path(result["directory_log"]).exists()
    expected_default = "loguru" if result["loguru_available"] else "stdlib"
    assert result["default_provider"] == expected_default
    assert result["stdlib_provider"] == "stdlib"
    assert isinstance(result["loguru_available"], bool)


def test_recipe_storage_scheme_selection(tmp_path: Path) -> None:
    result = run_example(
        "examples/90_recipes/storage_scheme_selection/main.py",
        output_dir=tmp_path / "storage_scheme_selection",
    )
    assert Path(result["h5_path"]).exists()
    assert Path(result["dir_path"]).exists()
    assert Path(result["model_path"]).exists()
    assert "time" in result["model_units"]


def test_recipe_compute_flow(tmp_path: Path) -> None:
    result = run_example(
        "examples/90_recipes/compute_flow/main.py",
        output_dir=tmp_path / "compute_flow",
    )
    assert result["preview_type"] == "AccelSeries"
    assert result["freqspec_success"] is True
    assert result["freqspec_type"] == "FreqSpec"
    assert result["compare_same_type"] is True
    assert result["branch_history_len"] >= 2


def test_recipe_compute_plan(tmp_path: Path) -> None:
    result = run_example(
        "examples/90_recipes/compute_plan/main.py",
        output_dir=tmp_path / "compute_plan",
    )
    assert result["plan_kind"] == "compute_plan"
    assert result["schema_version"] == 1
    assert result["step_count"] == 2
    assert result["all_success"] is True
    assert result["freqspec_ready_count"] == 2
    assert Path(result["payload_path"]).exists()


def test_recipe_scalar_frame_features(tmp_path: Path) -> None:
    result = run_example(
        "examples/90_recipes/scalar_frame_features/main.py",
        output_dir=tmp_path / "scalar_frame_features",
    )
    assert result["lazy_load_mode"] == "lazy"
    assert "pga" in result["columns"]
    assert "rms" in result["columns"]
    assert result["pga_nan_count"] >= 1
    assert result["rms_nan_count"] >= 1
    assert result["strict_error"]


def test_recipe_series_frame_alignment(tmp_path: Path) -> None:
    result = run_example(
        "examples/90_recipes/series_frame_alignment/main.py",
        output_dir=tmp_path / "series_frame_alignment",
    )
    assert result["index_name"] == "time"
    assert result["column_levels"] == 4
    assert result["row_count"] >= 4
    assert result["nan_count"] >= 1
    assert result["line_labels"] == ["L1", "L2", "L3"]


def test_recipe_peaks_frame(tmp_path: Path) -> None:
    result = run_example(
        "examples/90_recipes/peaks_frame/main.py",
        output_dir=tmp_path / "peaks_frame",
    )
    assert result["index_name"] == "peak_rank"
    assert result["column_levels"] == 4
    assert result["row_count"] >= 2
    assert result["nan_count"] >= 1
    assert result["value_columns"] == ["peak_index", "peak_value"]


def test_recipe_statistics_export(tmp_path: Path) -> None:
    result = run_example(
        "examples/90_recipes/statistics_export/main.py",
        output_dir=tmp_path / "statistics_export",
    )
    assert result["sample_count"] == 2
    assert Path(result["scalar_path"]).exists()
    assert Path(result["series_path"]).exists()
    assert Path(result["peaks_path"]).exists()
    assert Path(result["compare_path"]).exists()
    assert "pga" in result["scalar_columns"]
    assert "rms" in result["scalar_columns"]


def test_recipe_report_package_export(tmp_path: Path) -> None:
    result = run_example(
        "examples/90_recipes/report_package_export/main.py",
        output_dir=tmp_path / "report_package_export",
    )
    assert Path(result["package_dir"]).exists()
    assert Path(result["report_workbook"]).exists()
    assert Path(result["manifest_path"]).exists()
    assert Path(result["metadata_summary_path"]).exists()
    assert Path(result["tables_dir"]).exists()
    assert Path(result["figures_dir"]).exists()


def test_internal_custom_extension_compare_with_vibtest(tmp_path: Path) -> None:
    result = run_example(
        "examples/10_scenarios/08_custom_extension/main.py",
        output_dir=tmp_path / "custom_extension",
    )

    assert result["external_sample_type"] == "ExternalVibrationSample"
    assert result["external_sample_set_type"] == "ExternalVibrationSampleSet"
    assert result["payload_roundtrip_type"] == "ExternalVibrationSample"
    assert result["storage_roundtrip_type"] == "ExternalVibrationSample"
    assert result["compute_path_ok"] is True
    assert result["convenience_path_ok"] is True
    assert result["compute_vs_convenience_match"] is True
    assert result["external_vs_vibtest_match"] is True
    assert Path(result["plot_path"]).exists()


def test_recipe_docs_exist() -> None:
    for path in [
        "docs/workflow_guide.md",
        "docs/api/internal_api.md",
        "mkdocs.yml",
        "docs/baselines/public_api_baseline.toml",
        "examples/90_recipes/README.md",
    ]:
        assert (PROJECT_ROOT / path).exists()
