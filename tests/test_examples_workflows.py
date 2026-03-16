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


def test_recipe_plot_payload_and_plotters(tmp_path: Path) -> None:
    result = run_example(
        "examples/90_recipes/plot_payload_and_plotters/main.py",
        output_dir=tmp_path / "plot_payload_and_plotters",
    )
    assert result["plot_kind"] == "time"
    assert Path(result["raw_plot"]).exists()
    assert Path(result["model_plot"]).exists()


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


def test_recipe_structured_payload_roundtrip() -> None:
    result = run_example("examples/90_recipes/structured_payload_roundtrip/main.py")
    assert result["original_type"] == "AccelSeries"
    assert result["restored_type"] == "AccelSeries"
    assert result["axis_unit"] == "second"


def test_recipe_docs_exist() -> None:
    for path in [
        "docs/workflow_guide.md",
        "docs/api/internal_api.md",
        "mkdocs.yml",
        "docs/baselines/public_api_baseline.toml",
        "examples/90_recipes/README.md",
    ]:
        assert (PROJECT_ROOT / path).exists()
