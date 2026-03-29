"""1.0.0 收口验收测试。"""

from __future__ import annotations

from pathlib import Path
import shutil
import uuid

import matplotlib
import pytest

import dyntool.logging as dt_logging
import dyntool.plotting as dt_plotting
from dyntool import (
    AccelSeries,
    LoggingMode,
    DefaultSample,
    SampleDomain,
    DefaultSampleSet,
    StorageScheme,
)

matplotlib.use("Agg")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
INPUT_DATA_DIR = PROJECT_ROOT / "tests" / "input_data"


@pytest.fixture
def workspace_tmp_dir() -> Path:
    """Return a writable repository-local temp directory."""

    base = Path("tmp") / "test_phase7_acceptance" / uuid.uuid4().hex
    base.mkdir(parents=True, exist_ok=True)
    try:
        yield base
    finally:
        shutil.rmtree(base, ignore_errors=True)


def test_phase7_minimal_closed_loop_covers_log_storage_and_plot(
    workspace_tmp_dir: Path,
) -> None:
    """最小闭环应覆盖日志、评价、存储、回读和绘图。"""

    log_dir = workspace_tmp_dir / "logs"
    store_path = workspace_tmp_dir / "workflow_roundtrip.h5"
    plot_path = workspace_tmp_dir / "workflow_roundtrip.png"

    dt_logging.configure_logging(
        mode=LoggingMode.DIRECTORY,
        log_dir=log_dir,
        level="INFO",
        mirror_to_console=False,
    )

    sample = DefaultSample.from_accel_data(
        [0.0, 0.08, -0.02, 0.03, 0.0],
        dt=0.01,
        sample_domain=SampleDomain.VIBRATION_TEST,
        case="phase7-closed-loop",
        point="P1",
        instr="ACC-01",
        dir="Z",
        record="R1",
        timestamp="2026-03-13 12:00:00",
    )
    sample_set = DefaultSampleSet.from_samples(
        [sample],
        sample_domain=SampleDomain.VIBRATION_TEST,
    )

    sample_set.eval_zvl(overwrite=True, freq_range=(2.0, 60.0))
    sample_set.save(store_path, storage_scheme=StorageScheme.SET_H5)
    loaded = DefaultSampleSet.from_storage(
        store_path,
        sample_domain=SampleDomain.VIBRATION_TEST,
        storage_scheme=StorageScheme.SET_H5,
    )
    plotter = dt_plotting.FramePlotter()
    plotter.add(
        loaded[sample.uid].accel,  # type: ignore[arg-type]
        name="workflow-accel",
        category=dt_plotting.PlotCategory.SAMPLE,
    )
    result = plotter.plot()
    assert result.figure is not None
    result.figure.savefig(plot_path, dpi=120)
    dt_logging.get_logger("evaluation").info("phase7 closed loop complete")

    assert store_path.exists()
    assert plot_path.exists()
    assert sample.uid in loaded
    assert loaded[sample.uid].zvl is not None
    assert (log_dir / "storage.log").exists()
    assert (log_dir / "evaluation.log").exists()


def test_phase7_real_input_file_roundtrip_uses_class_first_api(
    workspace_tmp_dir: Path,
) -> None:
    """真实输入文件应通过类 API 完成读取、评价、保存和回读。"""

    source = INPUT_DATA_DIR / "加速度单条带时间ms单位cm.txt"
    normalized_csv = workspace_tmp_dir / "real_input_normalized.csv"
    store_path = workspace_tmp_dir / "real_input_roundtrip.h5"

    accel = AccelSeries.from_csv(
        source,
        axis_unit="millisecond",
        data_unit="centimeter/second**2",
        sep=r"\s+",
        header=None,
        names=["time", "value"],
        index_col=0,
    )
    normalized = accel.convert_units(
        {"time": "second", "value": "meter/second**2"},
        replace=False,
    )
    normalized.to_csv(normalized_csv)
    inspected = AccelSeries.inspect_units(normalized_csv, fmt="csv")

    sample = DefaultSample.from_models(
        sample_domain=SampleDomain.VIBRATION_TEST,
        accel=normalized,
        case="phase7-real-file",
        point="P1",
        instr="ACC-REAL",
        dir="Z",
        record="R1",
        timestamp="2026-03-13 12:00:00",
    )
    sample.eval_zvl(overwrite=True, freq_range=(2.0, 60.0))
    sample_set = DefaultSampleSet.from_samples(
        [sample],
        sample_domain=SampleDomain.VIBRATION_TEST,
    )
    sample_set.save(store_path, storage_scheme=StorageScheme.SET_H5)
    loaded = DefaultSampleSet.from_storage(
        store_path,
        sample_domain=SampleDomain.VIBRATION_TEST,
        storage_scheme=StorageScheme.SET_H5,
    )

    assert source.exists()
    assert normalized_csv.exists()
    assert store_path.exists()
    assert inspected["time"] == "second"
    assert "value" in inspected
    assert loaded[sample.uid].zvl is not None


def test_phase7_workflow_examples_use_class_first_paths() -> None:
    """工作流示例应优先展示类与独立模块入口。"""

    workflow_path = PROJECT_ROOT / "examples" / "10_scenarios" / "01_import_and_normalize" / "main.py"
    text = workflow_path.read_text(encoding="utf-8")

    assert "AccelSeries.from_csv" in text
    assert "DefaultSample.from_models" in text
    assert "tool.models.accel.from_csv" not in text
