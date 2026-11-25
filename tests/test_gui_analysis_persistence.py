"""GUI 分析数据另存、恢复与未保存保护，故障仅注入临时仓库。"""

from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
from threading import Event
from time import monotonic, sleep

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtCore import QThread
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

from dyntool import AccelSeries, DefaultSample, DefaultSampleSet, SampleDomain, VelSeries, VibrationTestMetadata
from dyntool.infrastructure.sample_storage_context import StorageContext
from dyntool.storage import SampleLoadMode, StorageScheme, inspect_storage_repository
import dyntool.storage as dt_storage
from dyntool_gui.main_window import MainWindow
from dyntool_gui.managers import AnalysisSaveManager
from dyntool_gui.managers.analysis_save_manager import AnalysisSaveResult
from dyntool_gui.persistence import AppSettingsStore, ProjectFileStore
from dyntool_gui.session import ImportKind, ProcessingRequestSnapshot, ProjectSession


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    """提供离屏 Qt 应用。"""

    return QApplication.instance() or QApplication([])


@pytest.fixture()
def session(qapp: QApplication, tmp_path: Path) -> ProjectSession:
    """构造三个真实样本，保存位置限定于测试目录。"""

    del qapp
    samples = [
        DefaultSample.from_models(
            sample_domain=SampleDomain.VIBRATION_TEST,
            metadata_cls=VibrationTestMetadata,
            case=f"case_{index}",
            point=f"P{index}",
            instr="ACC",
            dir="Z",
            record=f"R{index}",
            timestamp=f"2026-10-04 12:0{index}:00",
            accel=AccelSeries.from_data(np.sin(np.arange(64) * 0.3) + index, dt=0.01),
            vel=VelSeries.from_data(np.arange(64) * 0.01, dt=0.01),
        )
        for index in range(3)
    ]
    project = ProjectSession.build_empty()
    project.workdir = tmp_path
    project.bind_primary_runtime(DefaultSampleSet.from_samples(samples, sample_domain=SampleDomain.VIBRATION_TEST))
    return project


def wait_for_manager(manager: AnalysisSaveManager) -> None:
    """等待真实线程安全收尾，超时明确失败。"""

    deadline = monotonic() + 15
    while manager.busy and monotonic() < deadline:
        QApplication.processEvents()
        sleep(0.01)
    assert not manager.busy


@pytest.mark.parametrize(
    "source_scheme",
    [StorageScheme.SET_H5, StorageScheme.SET_SQLITE_H5, StorageScheme.SET_DIR, StorageScheme.SET_ATTR_TABLE],
)
def test_save_separate_repository_preserves_lazy_source_and_derived_results(
    session: ProjectSession, tmp_path: Path, qapp: QApplication, source_scheme: StorageScheme
) -> None:
    """懒源的未加载槽位和派生频谱都另存，源仓库内容保持不变。"""

    source = tmp_path / "source"
    dt_storage.save_sample_set(session.primary_runtime, source, scheme=source_scheme)
    before = {
        path.relative_to(source): sha256(path.read_bytes()).digest() for path in source.rglob("*") if path.is_file()
    }
    runtime = DefaultSampleSet.from_samples(None, sample_domain=SampleDomain.VIBRATION_TEST).load(
        source, storage_scheme=source_scheme, load_mode=SampleLoadMode.LAZY
    )
    first = next(iter(runtime.values()))
    first.calc_freqspec()
    session.bind_primary_runtime(runtime)
    assert all(not sample.is_loaded("vel") for sample in runtime.values())
    assert session.primary_sampleset.loaded_count == 1
    session.import_state.source_path = source
    manager = AnalysisSaveManager(session)
    results: list[AnalysisSaveResult] = []
    threads: list[bool] = []
    manager.completed.connect(results.append)
    manager.completed.connect(lambda _: threads.append(QThread.currentThread() == qapp.thread()))
    target = tmp_path / "analysis_data"
    manager.start(target)
    wait_for_manager(manager)

    assert results[0].complete
    assert results[0].report.stats.succeeded == 3
    assert threads == [True]
    assert session.analysis_data.path == target
    assert not session.analysis_dirty
    assert session.dirty
    after = {
        path.relative_to(source): sha256(path.read_bytes()).digest() for path in source.rglob("*") if path.is_file()
    }
    assert after == before
    saved = DefaultSampleSet.from_samples(None, sample_domain=SampleDomain.VIBRATION_TEST).load(
        target, storage_scheme=StorageScheme.SET_SQLITE_H5, load_mode=SampleLoadMode.EAGER
    )
    np.testing.assert_allclose(saved[first.uid].freqspec.get_value(), first.freqspec.get_value())
    assert all(sample.vel is not None for sample in saved.values())
    original = DefaultSampleSet.from_samples(None, sample_domain=SampleDomain.VIBRATION_TEST).load(
        source, storage_scheme=source_scheme, load_mode=SampleLoadMode.EAGER
    )
    assert all(sample.freqspec is None for sample in original.values())
    assert inspect_storage_repository(target, level="deep").is_valid


@pytest.mark.parametrize("strict", [True, False])
def test_partial_save_reports_commits_and_can_retry(
    session: ProjectSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, strict: bool
) -> None:
    """中间序列化失败保留前序提交，非严格继续，重试成功后才更新引用。"""

    second = list(session.primary_runtime.values())[1]
    original = StorageContext.serialize_container

    def fail_second(context: StorageContext, data: object) -> dict[str, object]:
        if data is second.accel:
            raise ValueError("注入中间样本序列化失败")
        return original(context, data)

    manager = AnalysisSaveManager(session)
    results: list[AnalysisSaveResult] = []
    manager.completed.connect(results.append)
    target = tmp_path / "partial"
    with monkeypatch.context() as patch:
        patch.setattr(StorageContext, "serialize_container", fail_second)
        manager.start(target, strict=strict)
        wait_for_manager(manager)

    result = results[0]
    assert not result.complete
    assert result.report.stats.succeeded == (1 if strict else 2)
    assert result.report.stats.failed == 1
    assert "注入中间样本序列化失败" in result.detail
    assert "未执行 1" in result.detail if strict else "未执行 0" in result.detail
    assert session.analysis_data.path is None
    assert session.analysis_data.retry_path == target
    assert session.analysis_dirty
    reopened = DefaultSampleSet.from_samples(None, sample_domain=SampleDomain.VIBRATION_TEST).load(
        target, storage_scheme=StorageScheme.SET_SQLITE_H5, load_mode=SampleLoadMode.EAGER
    )
    assert len(reopened) == (1 if strict else 2)
    assert inspect_storage_repository(target, level="deep").is_valid

    manager.start(target, strict=strict)
    wait_for_manager(manager)
    assert results[-1].complete
    assert session.analysis_data.path == target
    assert session.analysis_data.retry_path is None
    assert not session.analysis_dirty


def test_failure_before_commit_does_not_reuse_previous_processing_report(
    session: ProjectSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """连接前失败不能把上一次处理报告解释为本次保存成功。"""

    session.primary_runtime.calc_freqspec()
    old_report = session.primary_runtime.last_operation_report

    def fail_connect(*args: object, **kwargs: object) -> None:
        raise OSError("注入连接失败")

    monkeypatch.setattr(dt_storage, "save_sample_set", fail_connect)
    manager = AnalysisSaveManager(session)
    results: list[AnalysisSaveResult] = []
    manager.completed.connect(results.append)
    manager.start(tmp_path / "unavailable")
    wait_for_manager(manager)
    assert old_report.stats.succeeded == 3
    assert results[0].report is None
    assert "未执行 3" in results[0].detail
    assert session.analysis_data.path is None
    assert session.analysis_dirty


@pytest.mark.parametrize("target_kind", ["source", "bound_source", "unrelated"])
def test_first_save_rejects_source_and_unrelated_repository(
    session: ProjectSession, tmp_path: Path, target_kind: str
) -> None:
    """首次另存不能覆盖原始来源或合并无关项目的数据。"""

    target = tmp_path / target_kind
    target.mkdir()
    if target_kind == "source":
        session.import_state.source_path = target
    elif target_kind == "bound_source":
        dt_storage.save_sample_set(session.primary_runtime, target, scheme=StorageScheme.SET_SQLITE_H5)
    else:
        (target / "user.txt").write_text("保留用户文件", encoding="utf-8")
    manager = AnalysisSaveManager(session)
    with pytest.raises(ValueError, match="原始|其他项目"):
        manager.start(target)
    assert not manager.busy


def test_project_round_trip_keeps_saved_data_reference_and_original_source(
    session: ProjectSession, tmp_path: Path
) -> None:
    """项目新增引用兼容旧 JSON，重试中的部分仓库不写为成功目标。"""

    session.import_state.import_kind = ImportKind.SAMPLE
    session.import_state.source_path = tmp_path / "original.csv"
    manager = AnalysisSaveManager(session)
    manager.start(tmp_path / "analysis_data")
    wait_for_manager(manager)
    session.analysis_data.retry_path = tmp_path / "failed_copy"
    store = ProjectFileStore()
    project_file = tmp_path / "project.dyntool.json"
    store.save(session, project_file)
    loaded = store.load(project_file)
    assert loaded.analysis_data.path == session.analysis_data.path
    assert loaded.analysis_data.retry_path is None
    assert loaded.import_state.source_path == session.import_state.source_path
    assert loaded.primary_runtime is None
    assert not loaded.analysis_dirty
    payload = json.loads(project_file.read_text(encoding="utf-8"))
    payload.pop("analysis_data")
    project_file.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    assert store.load(project_file).analysis_data.path is None


@pytest.mark.parametrize("resume_action", ["processing", "save"])
def test_cold_project_restores_saved_results_even_when_csv_source_is_missing(
    session: ProjectSession, tmp_path: Path, qapp: QApplication, resume_action: str
) -> None:
    """已保存项目优先恢复分析仓库，无需重新读取原 CSV。"""

    del qapp
    session.primary_runtime.calc_freqspec()
    session.import_state.import_kind = ImportKind.SAMPLE
    session.import_state.source_path = tmp_path / "missing.csv"
    manager = AnalysisSaveManager(session)
    manager.start(tmp_path / "analysis_data")
    wait_for_manager(manager)
    file = tmp_path / "project.dyntool.json"
    ProjectFileStore().save(session, file)
    window = MainWindow(ProjectFileStore().load(file), settings_store=AppSettingsStore(tmp_path / "settings.ini"))
    try:
        if resume_action == "processing":
            window._run_processing(ProcessingRequestSnapshot(action_name="calc_freqspec", overwrite=False))
        else:
            assert window._save_analysis_data()
        deadline = monotonic() + 15
        while (window._is_busy() or window.session.primary_runtime is None) and monotonic() < deadline:
            QApplication.processEvents()
            sleep(0.01)
        assert not window._is_busy()
        assert window.session.primary_runtime is not None
        assert all(sample.freqspec is not None for sample in window.session.primary_runtime.values())
        if resume_action == "processing":
            assert window.session.processing_state.last_skipped_count == 3
        else:
            assert window.session.analysis_data.last_report.stats.succeeded == 3
        assert window.session.import_state.source_path == tmp_path / "missing.csv"
        assert window.session.analysis_data.path == tmp_path / "analysis_data"
    finally:
        window.deleteLater()


@pytest.mark.parametrize("action", ["close", "new", "open", "demo", "import"])
def test_cancel_unsaved_prompt_preserves_current_project(
    session: ProjectSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, action: str
) -> None:
    """取消未保存提醒后，关闭及各类主集替换入口均保留当前数据。"""

    window = MainWindow(session, settings_store=AppSettingsStore(tmp_path / "settings.ini"))
    session.primary_runtime.storage_dirty = True
    prompts: list[str] = []

    def cancel(parent: object, title: str, *args: object) -> QMessageBox.StandardButton:
        prompts.append(title)
        return QMessageBox.StandardButton.Cancel

    monkeypatch.setattr(QMessageBox, "question", cancel)
    monkeypatch.setattr(window, "_ensure_import_ready", lambda **kwargs: None)
    try:
        if action == "close":
            event = QCloseEvent()
            window._allow_close = True
            window.closeEvent(event)
            assert not event.isAccepted()
        elif action == "new":
            window._new_project()
        elif action == "demo":
            window._switch_demo("generic")
        elif action == "import":
            window._execute_import()
        else:
            other = tmp_path / "other.json"
            ProjectFileStore().save(ProjectSession.build_empty(), other)
            window._load_project_from_file(other)
        assert window.session is session
        assert session.primary_runtime is not None
        assert session.analysis_dirty
        assert prompts == ["分析数据尚未保存"]
        assert not window._is_busy()
    finally:
        window.deleteLater()


def test_close_saves_analysis_then_project_and_waits_for_thread_cleanup(
    session: ProjectSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """关闭时分两步保存，线程结束且项目引用落盘后才真正退出。"""

    window = MainWindow(session, settings_store=AppSettingsStore(tmp_path / "settings.ini"))
    window.show()
    session.primary_runtime.storage_dirty = True
    prompts: list[str] = []

    def save(parent: object, title: str, *args: object) -> QMessageBox.StandardButton:
        prompts.append(title)
        return QMessageBox.StandardButton.Save

    monkeypatch.setattr(QMessageBox, "question", save)
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *args, **kwargs: str(tmp_path))
    event = QCloseEvent()
    try:
        window.closeEvent(event)
        assert not event.isAccepted()
        wait_for_manager(window.analysis_save_manager)
        assert prompts == ["分析数据尚未保存", "项目状态尚未保存"]
        assert not window.isVisible()
        assert not session.analysis_dirty
        assert not session.dirty
        restored = ProjectFileStore().load(window._current_project_file)
        assert restored.analysis_data.path == tmp_path / "analysis_data"
    finally:
        window.deleteLater()


def test_project_save_does_not_clear_unsaved_analysis_data(session: ProjectSession, tmp_path: Path) -> None:
    """保存工作区描述不能清除模型数据脏状态。"""

    window = MainWindow(session, settings_store=AppSettingsStore(tmp_path / "settings.ini"))
    session.primary_runtime.storage_dirty = True
    session.dirty = True
    try:
        assert window._save_project()
        assert not session.dirty
        assert session.analysis_dirty
        assert "分析数据仍未保存" in window.statusBar().currentMessage()
    finally:
        window.deleteLater()


@pytest.mark.parametrize("failure", ["cancel_target", "data", "project"])
def test_failed_or_cancelled_save_prevents_close(
    session: ProjectSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    """目标选择取消、数据保存失败或项目写入失败均保持窗口打开。"""

    window = MainWindow(session, settings_store=AppSettingsStore(tmp_path / "settings.ini"))
    window.show()
    session.dirty = True
    session.primary_runtime.storage_dirty = failure != "project"
    warnings: list[str] = []

    def fail_save(*args: object, **kwargs: object) -> None:
        raise OSError("注入保存失败")

    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Save)
    monkeypatch.setattr(QMessageBox, "warning", lambda parent, title, message: warnings.append(message))
    monkeypatch.setattr(
        QFileDialog, "getExistingDirectory", lambda *args: "" if failure == "cancel_target" else str(tmp_path)
    )
    if failure == "data":
        monkeypatch.setattr(dt_storage, "save_sample_set", fail_save)
    elif failure == "project":
        monkeypatch.setattr(window.project_store, "save", fail_save)
    try:
        event = QCloseEvent()
        window.closeEvent(event)
        wait_for_manager(window.analysis_save_manager)
        assert not event.isAccepted()
        assert window.isVisible()
        assert window._after_analysis_save is None
        assert window._current_project_file is None
        assert session.dirty
        if failure != "project":
            assert session.analysis_dirty
        assert len(warnings) == (0 if failure == "cancel_target" else 1)
    finally:
        window.deleteLater()


def test_discard_data_then_cancel_project_preserves_both_dirty_states(
    session: ProjectSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """第二个提醒取消后，第一个放弃选择不应清除任何脏状态。"""

    window = MainWindow(session, settings_store=AppSettingsStore(tmp_path / "settings.ini"))
    session.primary_runtime.storage_dirty = True
    session.dirty = True
    answers = iter([QMessageBox.StandardButton.Discard, QMessageBox.StandardButton.Cancel])
    monkeypatch.setattr(QMessageBox, "question", lambda *args: next(answers))
    try:
        event = QCloseEvent()
        window.closeEvent(event)
        assert not event.isAccepted()
        assert session.dirty
        assert session.analysis_dirty
        assert window._current_project_file is None
    finally:
        window.deleteLater()


def test_analysis_save_holds_global_busy_and_terminal_progress(
    session: ProjectSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """保存期间阻止重复及并行写入，排队旧进度不能覆盖终态。"""

    started = Event()
    release = Event()
    original = StorageContext.serialize_container

    def block(context: StorageContext, data: object) -> dict[str, object]:
        started.set()
        assert release.wait(10)
        return original(context, data)

    monkeypatch.setattr(StorageContext, "serialize_container", block)
    window = MainWindow(session, settings_store=AppSettingsStore(tmp_path / "settings.ini"))
    manager = window.analysis_save_manager
    try:
        manager.start(tmp_path / "analysis_data")
        assert started.wait(3)
        assert window._is_busy()
        for name in ("保存分析数据", "保存项目", "新建项目", "打开项目", "执行"):
            assert not window.actions_map[name].isEnabled()
        assert not window.actions_map["中止当前任务"].isEnabled()
        with pytest.raises(ValueError, match="正在进行或收尾"):
            manager.start(tmp_path / "another")
        with pytest.raises(ValueError, match="后台任务"):
            window._ensure_write_task_available()
    finally:
        release.set()
        wait_for_manager(manager)
        window.deleteLater()
    assert session.tasks[0].status == "已完成"
    manager._handle_progress(1, 3)
    assert session.tasks[0].status == "已完成"


def test_missing_saved_repository_does_not_fall_back_to_original_source(
    session: ProjectSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """成功引用遗失时明确失败，不能用源数据悄悄替代派生结果。"""

    source = tmp_path / "source"
    dt_storage.save_sample_set(session.primary_runtime, source, scheme=StorageScheme.SET_SQLITE_H5)
    session.primary_runtime = None
    session.import_state.source_path = source
    session.analysis_data.path = tmp_path / "missing_analysis_data"
    window = MainWindow(session, settings_store=AppSettingsStore(tmp_path / "settings.ini"))
    warnings: list[str] = []
    monkeypatch.setattr(QMessageBox, "warning", lambda parent, title, message: warnings.append(message))
    try:
        assert window._save_analysis_data()
        deadline = monotonic() + 15
        while window._is_busy() and monotonic() < deadline:
            QApplication.processEvents()
            sleep(0.01)
        assert not window._is_busy()
        assert warnings
        assert session.primary_runtime is None
        assert session.analysis_data.path == tmp_path / "missing_analysis_data"
        assert not window._pending_analysis_save
    finally:
        window.deleteLater()


def test_import_cleanup_close_still_checks_unsaved_analysis(
    session: ProjectSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """请求中止导入后，资源收尾不能绕过旧主集的未保存保护。"""

    window = MainWindow(session, settings_store=AppSettingsStore(tmp_path / "settings.ini"))
    window.show()
    session.primary_runtime.storage_dirty = True
    session.import_state.busy = True
    window.import_manager._thread = object()
    prompts: list[str] = []
    answers = iter([QMessageBox.StandardButton.Yes, QMessageBox.StandardButton.Cancel])

    def answer(parent: object, title: str, *args: object) -> QMessageBox.StandardButton:
        prompts.append(title)
        return next(answers)

    monkeypatch.setattr(QMessageBox, "question", answer)
    monkeypatch.setattr(window, "_cancel_import_operation", lambda: None)
    try:
        event = QCloseEvent()
        window.closeEvent(event)
        assert not event.isAccepted()
        assert window._close_after_cleanup
        session.finish_import_activity()
        window.import_manager._thread = None
        window._resume_persistence_actions()
        assert window.isVisible()
        assert session.analysis_dirty
        assert prompts == ["导入仍在进行", "分析数据尚未保存"]
        assert not window._close_after_cleanup
    finally:
        window.import_manager._thread = None
        window.deleteLater()


@pytest.mark.parametrize("load_mode", [SampleLoadMode.LAZY, SampleLoadMode.METADATA_ONLY])
def test_summary_projection_does_not_load_arrays(
    session: ProjectSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, load_mode: SampleLoadMode
) -> None:
    """GUI 摘要按存在索引判定真实能力，不能读取数组或扩大已加载数量。"""

    source = tmp_path / "source"
    session.primary_runtime.calc_freqspec(uid=next(iter(session.primary_runtime)))
    dt_storage.save_sample_set(session.primary_runtime, source, scheme=StorageScheme.SET_SQLITE_H5)
    runtime = DefaultSampleSet.from_samples(None, sample_domain=SampleDomain.VIBRATION_TEST).load(
        source, storage_scheme=StorageScheme.SET_SQLITE_H5, load_mode=load_mode
    )

    def fail_array_read(*args: object, **kwargs: object) -> None:
        pytest.fail("摘要查询不应读取 payload")

    monkeypatch.setattr(runtime.storage, "load_fields", fail_array_read)
    session.bind_primary_runtime(runtime)
    assert session.primary_sampleset.loaded_count == 0
    assert session.primary_sampleset.unloaded_count == 3
    assert set(session.capability_snapshot.data_slots) == {"accel", "vel", "freqspec"}
    assert session.capability_snapshot.eval_results == ()
    assert all(sample.loaded_categories == () for sample in runtime.values())


def test_manual_save_uses_current_strict_setting(
    session: ProjectSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """手动保存读取当前接入严格开关，并冻结为真实后台任务参数。"""

    second = list(session.primary_runtime.values())[1]
    original = StorageContext.serialize_container

    def fail_second(context: StorageContext, data: object) -> dict[str, object]:
        if data is second.accel:
            raise ValueError("注入中间样本失败")
        return original(context, data)

    monkeypatch.setattr(StorageContext, "serialize_container", fail_second)
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: None)
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *args: str(tmp_path))
    window = MainWindow(session, settings_store=AppSettingsStore(tmp_path / "settings.ini"))
    window.workspace.import_workflow._strict_check.setChecked(False)
    try:
        assert window._save_analysis_data()
        wait_for_manager(window.analysis_save_manager)
        report = session.analysis_data.last_report
        assert not report.strict
        assert report.stats.succeeded == 2
        assert report.stats.failed == 1
        assert session.analysis_data.path is None
        assert session.analysis_dirty
    finally:
        window.deleteLater()
