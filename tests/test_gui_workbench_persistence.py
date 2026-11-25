"""GUI 工作台持久化与 Qt 状态测试。"""

from __future__ import annotations

import os
from pathlib import Path
import json

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QMessageBox

from dyntool_gui.main_window import MainWindow
from dyntool_gui.persistence.project_store import ProjectFileStore
from dyntool_gui.persistence.settings_store import AppSettingsStore
from dyntool_gui.session import (
    FilterGroup,
    FilterPredicate,
    FilterSpec,
    ImportKind,
    ImportStep,
    ProjectSession,
    SampleSetSummary,
)
from dyntool_gui.widgets import ProcessingWorkspace
from dyntool_gui.widgets.step_indicator import StepIndicator


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    """提供测试所需的 QApplication。"""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_project_session_emits_qt_signals_for_project_and_import_updates(qapp: QApplication, tmp_path: Path) -> None:
    """ProjectSession 应通过 Qt 信号发出项目与导入状态变化。"""

    del qapp
    session = ProjectSession.build_demo()
    captured: list[str] = []

    session.project_changed.connect(lambda: captured.append("project"))
    session.import_state_changed.connect(lambda: captured.append("import"))
    session.resource_tree_changed.connect(lambda: captured.append("tree"))

    session.set_project_directory(tmp_path / "signal_project")
    session.reset_for_import(ImportKind.SAMPLE_SET)
    session.set_import_source(tmp_path / "signal_project" / "repo")

    assert "project" in captured
    assert captured.count("import") >= 2
    assert "tree" in captured


def test_project_file_store_round_trip_preserves_gui_project_state(tmp_path: Path) -> None:
    """JSON 项目文件应保留 GUI 项目态与最近导入摘要。"""

    session = ProjectSession.build_demo()
    session.set_project_directory(tmp_path / "saved_project")
    session.reset_for_import(ImportKind.SAMPLE)
    session.set_import_source(tmp_path / "csv_batch")
    session.recent_import_lines = ("最近导入：样本集 repo_a", "样本数量：12")
    session.import_state.current_step = ImportStep.EXECUTE_IMPORT
    session.current_scope.scope_kind = "saved_subset"
    session.current_scope.subset_ids = ("subset.bridge.a",)

    store = ProjectFileStore()
    project_file = tmp_path / "demo_project.dyntool.json"

    store.save(session, project_file)
    restored = store.load(project_file)

    assert restored.workdir == session.workdir
    assert restored.export_dir == session.export_dir
    assert restored.primary_sampleset.name == session.primary_sampleset.name
    assert restored.recent_import_lines == session.recent_import_lines
    assert restored.import_state.import_kind is ImportKind.SAMPLE
    assert restored.import_state.current_step is ImportStep.EXECUTE_IMPORT
    assert restored.capability_snapshot.data_slots == session.primary_sampleset.supported_categories
    assert restored.capability_snapshot.eval_results == ("zvl", "otovl")
    assert restored.current_scope.scope_kind == "saved_subset"
    assert restored.current_scope.subset_ids == ("subset.bridge.a",)
    assert restored.subset_state.subsets


@pytest.mark.parametrize("failure_stage", ["serialization", "write", "replace"])
def test_project_save_failure_preserves_existing_file_and_dirty_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure_stage: str
) -> None:
    """序列化、暂存写入或替换失败不能破坏已有项目文件。"""

    session = ProjectSession.build_demo()
    store = ProjectFileStore()
    target = tmp_path / "project.dyntool.json"
    store.save(session, target)
    previous = target.read_bytes()
    session.note = "尚未保存的中文修改"
    session.dirty = True
    previous_saved = session.last_saved

    def fail_serialization(*args: object, **kwargs: object) -> str:
        raise ValueError("注入序列化失败")

    def fail_write(path: Path, *args: object, **kwargs: object) -> int:
        path.write_bytes(b"incomplete")
        raise OSError("注入写入失败")

    def fail_replace(path: Path, destination: str | Path) -> Path:
        raise OSError("注入替换失败")

    if failure_stage == "serialization":
        monkeypatch.setattr(json, "dumps", fail_serialization)
    elif failure_stage == "write":
        monkeypatch.setattr(Path, "write_text", fail_write)
    else:
        monkeypatch.setattr(Path, "replace", fail_replace)

    with pytest.raises((ValueError, OSError), match="注入"):
        store.save(session, target)

    assert target.read_bytes() == previous
    assert list(tmp_path.iterdir()) == [target]
    assert session.dirty
    assert session.last_saved == previous_saved
    assert store.load(target).note != session.note


def test_project_save_replaces_complete_utf8_lf_document(tmp_path: Path) -> None:
    """成功保存替换完整 JSON，并保持中文、UTF-8 无 BOM 与 LF。"""

    session = ProjectSession.build_demo()
    store = ProjectFileStore()
    target = tmp_path / "项目.dyntool.json"
    store.save(session, target)
    session.note = "更新后的项目说明"
    store.save(session, target)

    raw = target.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf")
    assert b"\r\n" not in raw
    assert store.load(target).note == session.note
    assert list(tmp_path.iterdir()) == [target]


@pytest.mark.parametrize("existing_target", [False, True])
def test_main_window_reports_project_save_failure_without_marking_saved(
    qapp: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, existing_target: bool
) -> None:
    """首次保存及覆盖保存失败均提示原因，并保留脏状态和项目引用。"""

    del qapp
    session = ProjectSession.build_demo()
    store = ProjectFileStore()
    window = MainWindow(session, settings_store=AppSettingsStore(tmp_path / "settings.ini"), project_store=store)
    session.workdir = tmp_path
    session.dirty = True
    previous_saved = session.last_saved
    previous_target = tmp_path / "existing.dyntool.json" if existing_target else None
    window._current_project_file = previous_target
    warnings: list[tuple[str, str]] = []
    settings_updates: list[bool] = []

    def fail_save(session: ProjectSession, path: str | Path) -> Path:
        raise OSError("目标目录不可写")

    monkeypatch.setattr(store, "save", fail_save)
    monkeypatch.setattr(QMessageBox, "warning", lambda parent, title, message: warnings.append((title, message)))
    monkeypatch.setattr(window, "_save_settings_from_session", lambda: settings_updates.append(True))
    try:
        window.actions_map["保存项目"].trigger()
        assert warnings == [("项目保存失败", "项目文件未保存：目标目录不可写")]
        assert session.dirty
        assert session.last_saved == previous_saved
        assert window._current_project_file == previous_target
        assert settings_updates == []
        assert window.statusBar().currentMessage() == "项目文件保存失败。"
    finally:
        window.deleteLater()


def test_project_file_store_round_trip_preserves_filter_sorting_and_paging(tmp_path: Path) -> None:
    """GUI 项目文件往返不应丢失筛选排序与分页条件。"""

    session = ProjectSession.build_demo()
    session.subset_state.filter_spec = FilterSpec(
        keyword="桥中点",
        sort_by="point",
        sort_desc=True,
        limit=50,
        offset=100,
    )

    store = ProjectFileStore()
    project_file = tmp_path / "filter_project.dyntool.json"

    store.save(session, project_file)
    restored = store.load(project_file)

    assert restored.subset_state.filter_spec.sort_by == "point"
    assert restored.subset_state.filter_spec.sort_desc is True
    assert restored.subset_state.filter_spec.limit == 50
    assert restored.subset_state.filter_spec.offset == 100


def test_project_file_store_round_trip_preserves_filter_query_tree(tmp_path: Path) -> None:
    """GUI 项目文件应显式保存 query_version/query 并恢复查询树。"""

    session = ProjectSession.build_demo()
    session.subset_state.filter_spec = FilterSpec(
        query=FilterGroup(
            operator="or",
            children=(
                FilterPredicate("metadata.point", "=", "桥中点"),
                FilterPredicate("result.zvl", "exists"),
            ),
        )
    )

    store = ProjectFileStore()
    project_file = tmp_path / "filter_query_project.dyntool.json"

    store.save(session, project_file)
    raw_text = project_file.read_text(encoding="utf-8")
    restored = store.load(project_file)

    assert '"query_version": 2' in raw_text
    assert '"query"' in raw_text
    assert isinstance(restored.subset_state.filter_spec.query, FilterGroup)
    assert restored.subset_state.filter_spec.query.operator == "or"
    assert restored.subset_state.filter_spec.query.children[0] == FilterPredicate("metadata.point", "=", "桥中点")


def test_project_file_store_loads_legacy_metadata_filters_as_queryless_filter_spec(tmp_path: Path) -> None:
    """旧 metadata_filters 项目文件仍应加载为兼容 metadata_clauses，且 query 为空。"""

    session = ProjectSession.build_demo()
    store = ProjectFileStore()
    project_file = tmp_path / "legacy_metadata_filters.dyntool.json"
    store.save(session, project_file)
    payload = project_file.read_text(encoding="utf-8")
    payload = payload.replace('"metadata_clauses": []', '"metadata_filters": [["point", ["桥中点"]]]')
    payload = payload.replace('"query_version": 2,\n      "query": null,\n      ', "")
    project_file.write_text(payload, encoding="utf-8")

    restored = store.load(project_file)

    assert restored.subset_state.filter_spec.query is None
    assert restored.subset_state.filter_spec.metadata_filters == (("point", ("桥中点",)),)


def test_project_file_store_repairs_loaded_runtime_restore_context(tmp_path: Path) -> None:
    """旧项目只有主集摘要和 workdir/data 时，加载后应允许恢复运行态。"""

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    session = ProjectSession.build_demo()
    session.workdir = tmp_path
    session.primary_runtime = None
    session.primary_sampleset = SampleSetSummary(
        name="主样本集 / data",
        class_name="DefaultSampleSet",
        sample_type="VibrationTestSample",
        sample_domain="vibration_test",
        metadata_type="VibrationTestMetadata",
        metadata_fields=("case",),
        supported_categories=(),
        storable_categories=(),
        supported_fields=(),
        sample_count=840,
        loaded_count=0,
        unloaded_count=840,
        storage_binding="SET_SQLITE_H5 / read_write",
        strict=True,
        storage_dirty=False,
    )
    session.import_state.source_path = None
    session.import_state.import_kind = ImportKind.SAMPLE_SET
    session.import_state.available_series_categories = ("accel", "freqspec")

    project_file = tmp_path / "legacy_project.dyntool.json"
    store = ProjectFileStore()
    store.save(session, project_file)
    restored = store.load(project_file)

    assert restored.import_state.source_path == data_dir
    assert restored.capability_snapshot.data_slots == ("accel", "freqspec")


def test_processing_workspace_enables_restore_after_legacy_project_load(qapp: QApplication, tmp_path: Path) -> None:
    """旧项目加载后数据处理页应能引导恢复运行态并继续分析。"""

    del qapp
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    session = ProjectSession.build_demo()
    session.workdir = tmp_path
    session.primary_runtime = None
    session.import_state.source_path = None
    session.import_state.import_kind = ImportKind.SAMPLE_SET
    session.import_state.available_series_categories = ("accel", "freqspec")
    session.primary_sampleset = SampleSetSummary(
        name="主样本集 / data",
        class_name="DefaultSampleSet",
        sample_type="VibrationTestSample",
        sample_domain="vibration_test",
        metadata_type="VibrationTestMetadata",
        metadata_fields=("case",),
        supported_categories=(),
        storable_categories=(),
        supported_fields=(),
        sample_count=840,
        loaded_count=0,
        unloaded_count=840,
        storage_binding="SET_SQLITE_H5 / read_write",
        strict=True,
        storage_dirty=False,
    )
    project_file = tmp_path / "legacy_project.dyntool.json"
    store = ProjectFileStore()
    store.save(session, project_file)
    restored = store.load(project_file)
    widget = ProcessingWorkspace()

    widget.load_session(restored)

    assert widget._run_button.isEnabled()
    assert widget._run_button.text() == "执行分析"
    assert "accel" in widget._summary.text()


def test_app_settings_store_round_trip_preserves_recent_paths_and_theme(tmp_path: Path) -> None:
    """QSettings 存储应保留最近来源目录、最近项目和主题偏好。"""

    settings_file = tmp_path / "gui_settings.ini"
    store = AppSettingsStore(settings_file)

    payload = {
        "theme_name": "light",
        "recent_projects": [str(tmp_path / "a.dyntool.json"), str(tmp_path / "b.dyntool.json")],
        "recent_sample_dir": str(tmp_path / "sample_csv"),
        "recent_sampleset_dir": str(tmp_path / "sampleset_repo"),
    }

    store.save_preferences(payload)
    restored = store.load_preferences()

    assert restored["theme_name"] == "light"
    assert restored["recent_projects"] == payload["recent_projects"]
    assert restored["recent_sample_dir"] == payload["recent_sample_dir"]
    assert restored["recent_sampleset_dir"] == payload["recent_sampleset_dir"]


def test_step_indicator_tracks_current_and_completed_steps(qapp: QApplication) -> None:
    """步骤指示器应能反映当前步骤和已完成步骤。"""

    del qapp
    indicator = StepIndicator(("项目上下文", "接入模式与来源", "检查结果", "绑定与执行"))

    indicator.set_current_step(2)
    indicator.set_completed_steps(2)

    assert indicator.current_step() == 2
    assert indicator.completed_steps() == 2
    assert indicator.step_count() == 4


def test_main_window_registers_core_actions(qapp: QApplication, tmp_path: Path) -> None:
    """主窗口应注册核心动作并接入项目文件与设置存储。"""

    del qapp
    settings_store = AppSettingsStore(tmp_path / "window.ini")
    project_store = ProjectFileStore()
    window = MainWindow(
        ProjectSession.build_demo(),
        settings_store=settings_store,
        project_store=project_store,
    )

    expected_actions = {
        "新建项目",
        "打开项目",
        "保存项目",
        "导入与筛选",
        "中止当前任务",
        "切换到总览页",
        "切换到导入与筛选页",
    }

    assert expected_actions.issubset(set(window.actions_map))
