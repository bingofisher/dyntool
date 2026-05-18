"""P-R1-3 真实工程库 GUI 集成测试。"""

from __future__ import annotations

import os
from pathlib import Path
from time import perf_counter
from itertools import islice

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

import dyntool.storage as dt_storage
from dyntool import StorageScheme
from dyntool.storage import SampleLoadMode
from dyntool_gui.facades import GuiImportFacade, SampleSetImportRequest
from dyntool_gui.managers import ExportManager, PlotManager, ProcessingManager
from dyntool_gui.session import ProjectSession

from .gui_real_data_support import record_stage_timing, resolve_pr13_data_dir, resolve_pr13_subset_uids


pytestmark = pytest.mark.skipif(
    os.environ.get("ADVDYNTOOL_RUN_REAL_GUI_INTEGRATION") != "1",
    reason="未启用真实工程库 GUI 集成测试。",
)


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    """提供真实 GUI 集成测试所需的 QApplication。"""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture(scope="module")
def pr13_data_dir() -> Path:
    """返回 P-R1-3 真实工程库 data 目录。"""

    data_dir = resolve_pr13_data_dir()
    if data_dir is None:
        pytest.skip("未找到 P-R1-3 真实工程库 data 目录。")
    return data_dir


@pytest.fixture()
def pr13_import_request(pr13_data_dir: Path) -> SampleSetImportRequest:
    """返回真实工程库导入请求。"""

    return SampleSetImportRequest(
        source_path=pr13_data_dir,
        requested_scheme=StorageScheme.SET_SQLITE_H5,
        load_mode=SampleLoadMode.LAZY,
        workers=1,
        strict=True,
    )


def test_pr13_real_repository_full_pipeline(tmp_path: Path, pr13_import_request: SampleSetImportRequest) -> None:
    """真实工程库全量链路应能完成检查、导入与全量处理。"""

    timings: list[dict[str, object]] = []
    stage_started = perf_counter()
    report = dt_storage.inspect_storage_repository(
        pr13_import_request.source_path,
        storage_scheme=StorageScheme.SET_SQLITE_H5,
        level="quick",
    )
    inspect_ms = record_stage_timing(
        timings,
        "inspect_storage_repository(level=quick)",
        stage_started,
        sample_count=report.sample_count,
    )
    assert inspect_ms <= 30_000
    assert report.is_valid
    assert report.sample_count == 840

    facade = GuiImportFacade()

    stage_started = perf_counter()
    preview = facade.preview_sample_set_repository(pr13_import_request)
    preview_ms = record_stage_timing(
        timings,
        "gui_light_preview",
        stage_started,
        sample_count=840,
        category_count=len(preview.available_series_categories),
    )
    assert preview_ms <= 30_000
    assert preview.allow_execute
    assert preview.metadata_mode_text == "vibration_test_metadata"
    assert preview.available_series_categories == ("accel",)

    stage_started = perf_counter()
    deep_preview = facade.preview_sample_set_repository_deep_units(pr13_import_request)
    deep_ms = record_stage_timing(
        timings,
        "gui_deep_units",
        stage_started,
        sample_count=840,
        category_count=len(deep_preview.available_series_categories),
    )
    assert deep_ms <= 60_000
    joined_units = "\n".join(deep_preview.unit_lines)
    assert "加速度 状态：一致" in joined_units
    assert "速度：未检测到该类原始数据" in joined_units
    assert "位移：未检测到该类原始数据" in joined_units
    assert "力：未检测到该类原始数据" in joined_units

    session = ProjectSession.build_demo("generic")
    session.set_project_directory(tmp_path / "pr13_gui_project")

    stage_started = perf_counter()
    result = facade.execute_sample_set_repository(pr13_import_request)
    import_ms = record_stage_timing(
        timings,
        "execute_sample_set_repository(load_mode=LAZY)",
        stage_started,
        sample_count=result.primary_summary.sample_count,
        category_count=len(preview.available_series_categories),
    )
    assert import_ms <= 60_000

    session.apply_import_result(result)
    assert session.primary_runtime is not None
    assert session.primary_sampleset.sample_count == 840
    assert session.primary_sampleset.class_name == "VibrationTestSampleSet"
    assert session.primary_sampleset.metadata_type == "VibrationTestMetadata"

    processing = ProcessingManager(session)

    stage_started = perf_counter()
    freqspec_result = processing.execute_sync(
        action_name="calc_freqspec",
        uids_text="",
        strict=True,
        overwrite=True,
    )
    freqspec_ms = record_stage_timing(
        timings,
        "calc_freqspec(full)",
        stage_started,
        sample_count=freqspec_result.affected_count,
        category_count=len(session.capability_snapshot.data_slots),
    )
    assert freqspec_ms <= 300_000
    assert freqspec_result.affected_count == 840
    assert "freqspec" in session.capability_snapshot.data_slots

    stage_started = perf_counter()
    zvl_result = processing.execute_sync(
        action_name="eval_zvl",
        uids_text="",
        strict=True,
        overwrite=True,
    )
    zvl_ms = record_stage_timing(
        timings,
        "eval_zvl(full)",
        stage_started,
        sample_count=zvl_result.affected_count,
        category_count=len(session.capability_snapshot.data_slots),
    )
    assert zvl_ms <= 300_000
    assert zvl_result.affected_count == 840
    assert "zvl" in session.capability_snapshot.data_slots

    session.real_data_diagnostics = tuple(
        f"{record['stage']}: {record['duration_ms']} ms, samples={record['sample_count']}, categories={record['category_count']}"
        for record in timings
    )
    assert len(session.real_data_diagnostics) >= 6


def test_pr13_real_repository_page_subset_pipeline(
    qapp: QApplication,
    tmp_path: Path,
    pr13_import_request: SampleSetImportRequest,
) -> None:
    """真实工程库 3 个 UID 子集应能完成页面级预览、绘图与导出。"""

    del qapp
    subset_uids = resolve_pr13_subset_uids(limit=3)
    assert len(subset_uids) == 3

    facade = GuiImportFacade()
    session = ProjectSession.build_demo("generic")
    session.set_project_directory(tmp_path / "pr13_gui_subset_project")
    session.apply_import_result(facade.execute_sample_set_repository(pr13_import_request))

    runtime = session.primary_runtime
    assert runtime is not None
    subset_entries = dict(islice(runtime.items(), 3))
    subset = type(runtime)(subset_entries)
    session.bind_primary_runtime(
        subset,
        name="真实工程库子集",
        storage_binding="P-R1-3 / 3 个 UID 子集",
    )

    processing = ProcessingManager(session)
    processing.execute_sync(action_name="calc_freqspec", uids_text="", strict=True, overwrite=True)
    processing.execute_sync(action_name="eval_zvl", uids_text="", strict=True, overwrite=True)

    scalar_preview = processing.build_preview_sync(
        preview_kind="scalar_frame",
        preview_scope="all",
        uids_text="",
        metadata_fields=("alias",),
        features=("max", "rms"),
        data_var="freqspec",
        peak_source="accel",
    )
    assert scalar_preview.scalar_rows
    assert len(scalar_preview.scalar_rows) <= 200

    series_preview = processing.build_preview_sync(
        preview_kind="series_frame",
        preview_scope="all",
        uids_text="",
        metadata_fields=("alias",),
        features=("max",),
        data_var="freqspec",
        peak_source="accel",
    )
    assert series_preview.series_rows
    assert len(series_preview.series_rows) <= 200

    plot_manager = PlotManager(session)
    accel_plot = plot_manager.render_sync(
        source_kind="sample_model",
        source_name="accel",
        selected_uid=subset_uids[0],
        point_limit=20_000,
        save_mode="preview",
    )
    freqspec_plot = plot_manager.render_sync(
        source_kind="sample_model",
        source_name="freqspec",
        selected_uid=subset_uids[0],
        point_limit=20_000,
        save_mode="preview",
    )
    assert accel_plot.figure is not None
    assert freqspec_plot.figure is not None

    plots_dir = tmp_path / "plots"
    assert plot_manager.save_figure(accel_plot.figure, plots_dir / "accel.png").suffix == ".png"
    assert plot_manager.save_figure(freqspec_plot.figure, plots_dir / "freqspec.svg").suffix == ".svg"
    assert plot_manager.save_figure(freqspec_plot.figure, plots_dir / "freqspec.pdf").suffix == ".pdf"

    export_manager = ExportManager(session)
    validation = export_manager.validate_sync(
        export_kind="report_package",
        output_path=tmp_path / "exports" / "package",
        data_var="respspec",
        source="accel",
    )
    assert not validation.valid
    assert validation.pending_generation_action == "calc_respspec"

    scalar_export = export_manager.execute_sync(
        export_kind="scalar_frame",
        output_path=tmp_path / "exports" / "scalar.csv",
        format_name="csv",
        metadata_fields=("alias",),
        features=("max", "rms"),
        data_var="freqspec",
        source="accel",
        include_plots=False,
        include_eval_summary=False,
    )
    report_export = export_manager.execute_sync(
        export_kind="report_package",
        output_path=tmp_path / "exports" / "package",
        format_name="xlsx",
        metadata_fields=("alias",),
        features=("max",),
        data_var="freqspec",
        source="accel",
        include_plots=False,
        include_eval_summary=True,
    )
    assert scalar_export.output_path.exists()
    assert report_export.output_path.exists()
