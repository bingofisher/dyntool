"""正式场景示例 smoke 测试。"""

from __future__ import annotations

from pathlib import Path

import matplotlib
import pytest

from .example_runner import PROJECT_ROOT, run_example

matplotlib.use("Agg")


def test_scenario_import_and_normalize(tmp_path: Path) -> None:
    result = run_example(
        "examples/10_scenarios/01_import_and_normalize/main.py",
        output_dir=tmp_path / "import_and_normalize",
    )
    assert Path(result["source"]).exists()
    assert Path(result["normalized_csv"]).exists()
    assert Path(result["store_path"]).exists()
    assert result["inspected_units"]["time"] == "second"
    assert result["has_zvl"] is True


def test_scenario_build_and_manage_samples() -> None:
    result = run_example("examples/10_scenarios/02_build_and_manage_samples/main.py")
    assert result["sample_count"] == 2
    assert result["evaluated_count"] == 2
    assert result["mechanical_stress_unit"] == "megapascal"
    assert result["mechanical_strain_si"] == pytest.approx(0.0003)


def test_scenario_evaluate_vibration() -> None:
    result = run_example("examples/10_scenarios/03_evaluate_vibration/main.py")
    assert result["sample_count"] == 2
    assert result["freqspec_ok_count"] == 2
    assert result["respspec_ok_count"] == 2
    assert result["freqspec_type"] == "FreqSpec"
    assert result["respspec_type"] == "RespSpec"
    assert result["has_zvl"] is True


def test_scenario_store_and_reload(tmp_path: Path) -> None:
    result = run_example(
        "examples/10_scenarios/04_store_and_reload/main.py",
        output_dir=tmp_path / "store_and_reload",
    )
    assert result["loaded_count"] == 1
    assert Path(result["store_path"]).exists()
    assert Path(result["plot_path"]).exists()
    assert result["freqspec_restored"] is True
    assert result["respspec_restored"] is True


def test_scenario_plot_and_export(tmp_path: Path) -> None:
    result = run_example(
        "examples/10_scenarios/05_plot_and_export/main.py",
        output_dir=tmp_path / "plot_and_export",
    )
    assert result["plot_kind"] == "time"
    assert Path(result["raw_plot"]).exists()
    assert Path(result["model_plot"]).exists()
    assert Path(result["box_plot"]).exists()
    assert Path(result["subplot_plot"]).exists()


def test_scenario_logged_run(tmp_path: Path) -> None:
    result = run_example(
        "examples/10_scenarios/06_logged_run/main.py",
        output_dir=tmp_path / "logged_run",
    )
    assert result["has_zvl"] is True
    assert result["evaluation_log_exists"] is True
    assert (Path(result["log_dir"]) / "evaluation.log").exists()


def test_scenario_resource_driven_eval(tmp_path: Path) -> None:
    result = run_example(
        "examples/10_scenarios/07_resource_driven_eval/main.py",
        output_dir=tmp_path / "resource_driven_eval",
    )
    assert result["freq_start"] < result["freq_end"]
    assert result["city_limit"] == 65.0
    assert result["city_standard"] == "GB 10070-1988"
    assert result["fdmvl_standard"] == "JGJ/T 170-2009"
    assert result["fdmvl_limit"] == 62.0
    # 1e-3 m/s² 正弦的 RMS 振级约 56.99 dB，16 Hz Z 计权为 -2 dB。
    assert abs(result["fdmvl_value"] - 54.9897) < 0.01
    assert result["fdmvl_freq_range"] == (4.0, 200.0)
    assert Path(result["fdmvl_limit_path"]).exists()
    assert Path(result["fdmvl_plot_path"]).exists()
    assert Path(result["summary_path"]).exists()


def test_scenario_docs_exist() -> None:
    for path in [
        "docs/examples_overview.md",
        "docs/api/public_api.md",
        "mkdocs.yml",
        "docs/baselines/public_api_baseline.toml",
        "examples/README.md",
        "examples/10_scenarios/README.md",
        "examples/90_recipes/README.md",
    ]:
        assert (PROJECT_ROOT / path).exists()
