"""PySide6 GUI 骨架测试。"""

from __future__ import annotations

import ast
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import QRect, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QFormLayout,
    QGroupBox,
    QLabel,
    QMessageBox,
    QProgressBar,
    QScrollArea,
    QSplitter,
    QTableWidget,
    QTableView,
    QToolBar,
    QTreeView,
    QWidget,
)

from dyntool_gui.facades import GuiImportFacade, ImportPreview, SampleSetImportRequest
from dyntool_gui.layout import LANDSCAPE_1080P_PROFILE, LANDSCAPE_2K_PROFILE, resolve_workbench_layout_profile
from dyntool_gui.main_window import MainWindow
from dyntool_gui.managers import ExportManager, PlotManager, ProcessingManager
from dyntool_gui.managers.processing_manager import ProcessingTaskController
from dyntool_gui.managers.task_manager import TaskManager
from dyntool_gui.models import PanelDataBuilder
from dyntool_gui.session import (
    FilterSpec,
    ImportKind,
    MODULE_LABELS,
    ModuleKey,
    ProcessingRequestSnapshot,
    ProjectSession,
    SubsetDefinition,
)
from dyntool_gui.widgets import (
    ExportWorkspace,
    ImportFilterWorkspace,
    ImportWorkflowWidget,
    ModuleWorkspace,
    PlottingWorkspace,
)
from dyntool_gui.widgets.step_indicator import StepIndicator


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    """提供测试所需的 QApplication。"""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_project_session_demo_switches() -> None:
    """演示会话切换后主集摘要应同步刷新。"""

    session = ProjectSession.build_demo("bridge")
    assert session.primary_sampleset.sample_count == 48
    session.switch_demo("generic")
    assert session.project_name == "通用样本项目骨架"
    assert session.primary_sampleset.sample_domain == "default"


def test_main_window_exposes_required_shell(qapp: QApplication) -> None:
    """主窗口应包含既定的工作台骨架。"""

    del qapp
    window = MainWindow(ProjectSession.build_demo())

    assert window.workspace.count() == 4
    assert [window.workspace.tabText(index) for index in range(window.workspace.count())] == [
        MODULE_LABELS[ModuleKey.PROJECT],
        MODULE_LABELS[ModuleKey.IMPORT],
        MODULE_LABELS[ModuleKey.PROCESSING],
        MODULE_LABELS[ModuleKey.PLOTTING],
    ]
    assert window.left_dock.windowTitle() == "对象树"
    assert window.bottom_dock.windowTitle() == "任务与记录"
    assert not hasattr(window, "right_dock")


def test_main_window_switch_demo_updates_status(qapp: QApplication) -> None:
    """切换演示数据后标题与状态栏应更新。"""

    del qapp
    window = MainWindow(ProjectSession.build_demo())

    window._switch_demo("generic")

    assert "通用样本项目骨架" in window.windowTitle()
    assert "Generic-Set" in window._status_sampleset.text()


def test_main_window_scope_targets_normalize_subset_and_uid_inputs(qapp: QApplication) -> None:
    """主窗口应统一把页面范围选择收敛为会话 scope 载荷。"""

    del qapp
    window = MainWindow(ProjectSession.build_demo())

    assert window._scope_targets("saved_subset", "subset-a") == (("subset-a",), ())
    assert window._scope_targets("multi_subset_union", "a, b ,, c") == (("a", "b", "c"), ())
    assert window._scope_targets("single_sample", "u1, u2") == ((), ("u1", "u2"))
    assert window._scope_targets("all_samples", "") == ((), ())


def test_main_window_adaptive_layout_targets_scale_with_window_size(qapp: QApplication) -> None:
    """主窗口默认布局应按当前分辨率给出较保守的 dock 目标尺寸。"""

    del qapp
    window = MainWindow(ProjectSession.build_demo())

    window.resize(1366, 768)
    left_target, bottom_target = window._recommended_dock_sizes()

    assert window.left_dock.minimumWidth() <= 200
    assert window.bottom_dock.minimumHeight() <= 128
    assert 160 <= left_target <= 220
    assert 72 <= bottom_target <= 112


def test_main_window_recommended_size_scales_to_2560_screen(
    monkeypatch: pytest.MonkeyPatch, qapp: QApplication
) -> None:
    """2560x1440 屏幕下默认窗口应放大到更接近工作台视图。"""

    del qapp
    from dyntool_gui import main_window as main_window_module

    class _FakeScreen:
        def availableGeometry(self) -> QRect:
            return QRect(0, 0, 2560, 1440)

    monkeypatch.setattr(main_window_module.QGuiApplication, "primaryScreen", lambda: _FakeScreen())
    window = MainWindow(ProjectSession.build_demo())

    width, height = window._recommended_window_size()

    assert width >= 2000
    assert height >= 1180


def test_2k_landscape_profile_contract() -> None:
    """2K 横屏布局配置应固定默认目标，同时允许用户继续拖宽侧栏。"""

    profile = resolve_workbench_layout_profile(2560, 1440)

    assert profile.is_landscape is True
    assert 170 <= profile.left_dock_target_min <= profile.left_dock_target_max <= 190
    assert profile.left_dock_max_width >= 360
    assert 96 <= profile.bottom_dock_target_min <= profile.bottom_dock_target_max <= 128
    assert profile.nav_button_height <= 40
    assert profile.page_header_max_height <= 80
    assert profile.import_workflow_max_width <= 580
    assert profile.side_panel_max_width >= 420
    assert profile.result_tabs_max_height <= 136


def test_1080p_landscape_profile_prioritizes_vertical_space() -> None:
    """1080P 横屏布局应进一步压缩 dock 和结果页签，避免挤占主工作区。"""

    profile = resolve_workbench_layout_profile(1920, 1080)

    assert profile is LANDSCAPE_1080P_PROFILE
    assert profile.left_dock_target_max <= 165
    assert profile.bottom_dock_target_max <= 96
    assert profile.result_tabs_max_height <= 112
    assert profile.side_panel_max_width <= 340


def test_2k_landscape_main_window_uses_compact_shell(monkeypatch: pytest.MonkeyPatch, qapp: QApplication) -> None:
    """2K 横屏下主窗口应把对象树、任务区、导航和页头压成工作台密度。"""

    del qapp
    from dyntool_gui import main_window as main_window_module

    class _FakeScreen:
        def availableGeometry(self) -> QRect:
            return QRect(0, 0, 2560, 1440)

    monkeypatch.setattr(main_window_module.QGuiApplication, "primaryScreen", lambda: _FakeScreen())
    window = MainWindow(ProjectSession.build_demo())

    window.resize(2560, 1440)
    window._apply_adaptive_layout(force=True)
    left_target, bottom_target = window._recommended_dock_sizes()
    nav_bar = window.workspace.findChild(QWidget, "ModuleNavigationBar")
    header = window.workspace.findChild(QWidget, "ProjectPageHeader")

    assert left_target <= LANDSCAPE_2K_PROFILE.left_dock_target_max
    assert window.left_dock.maximumWidth() >= 360
    assert bottom_target <= LANDSCAPE_2K_PROFILE.bottom_dock_target_max
    assert window.bottom_dock.minimumHeight() <= LANDSCAPE_2K_PROFILE.bottom_dock_min_height
    assert nav_bar is not None
    assert nav_bar.maximumHeight() <= LANDSCAPE_2K_PROFILE.nav_button_height + 8
    assert header is not None
    assert header.maximumHeight() <= LANDSCAPE_2K_PROFILE.page_header_max_height


def test_main_window_defaults_to_maximized_on_2560_screen(monkeypatch: pytest.MonkeyPatch, qapp: QApplication) -> None:
    """2560x1440 屏幕下主窗口应默认最大化，避免保留大面积黑边。"""

    del qapp
    from dyntool_gui import main_window as main_window_module

    class _FakeScreen:
        def availableGeometry(self) -> QRect:
            return QRect(0, 0, 2560, 1440)

    monkeypatch.setattr(main_window_module.QGuiApplication, "primaryScreen", lambda: _FakeScreen())
    window = MainWindow(ProjectSession.build_demo())

    assert bool(window.windowState() & Qt.WindowState.WindowMaximized)


def test_status_bar_exposes_global_progress_for_busy_tasks(qapp: QApplication) -> None:
    """长任务忙碌时状态栏应显示全局进度条，避免加载阶段没有反馈。"""

    del qapp
    window = MainWindow(ProjectSession.build_demo())

    window.session.import_state.busy = True
    window.session.import_state.progress_prefix = "导入样本集"
    window.session.import_state.progress_current = 3
    window.session.import_state.progress_total = 10
    window._refresh_window_context()

    progress = window.statusBar().findChild(QProgressBar, "GlobalTaskProgressBar")
    assert progress is not None
    assert not progress.isHidden()
    assert progress.maximum() == 10
    assert progress.value() == 3

    window.session.finish_import_activity()
    window.processing_manager._thread = object()  # type: ignore[assignment]
    window._refresh_window_context()
    assert not progress.isHidden()
    assert progress.minimum() == 0
    assert progress.maximum() == 0
    window.processing_manager._thread = None


def test_import_execute_success_enters_visible_finalizing_phase(
    monkeypatch: pytest.MonkeyPatch, qapp: QApplication
) -> None:
    """导入 worker 完成后应先进入可见收尾阶段，再写回会话。"""

    del qapp
    from dyntool_gui import main_window as main_window_module

    window = MainWindow(ProjectSession.build_demo())
    window.import_manager._mode = "execute"  # type: ignore[attr-defined]
    scheduled_callbacks: list[tuple[int, object]] = []
    applied_payloads: list[object] = []
    payload = object()

    monkeypatch.setattr(
        main_window_module.QTimer,
        "singleShot",
        lambda interval, callback: scheduled_callbacks.append((interval, callback)),
    )
    monkeypatch.setattr(window.session, "apply_import_result", lambda value: applied_payloads.append(value))

    window._handle_import_success(payload)

    assert applied_payloads == []
    assert scheduled_callbacks
    assert scheduled_callbacks[0][0] == 0
    assert window.session.import_state.busy is True
    assert window.session.import_state.phase_code == "finalize_import"
    assert window.session.import_state.cancellable is False
    assert "暂不可中止" in window.session.import_state.busy_detail
    assert window.actions_map["中止当前任务"].isEnabled() is False

    callback = scheduled_callbacks[0][1]
    assert callable(callback)
    callback()

    assert applied_payloads == [payload]


def test_sample_set_execute_reuses_light_preview_runtime(
    monkeypatch: pytest.MonkeyPatch, qapp: QApplication, tmp_path: Path
) -> None:
    """样本集轻量预览后参数未变化时，绑定主集应复用预览运行态而不是重新全量检查。"""

    del qapp
    source_dir = tmp_path / "repo"
    source_dir.mkdir()
    cached_runtime = object()
    window = MainWindow(ProjectSession.build_demo())
    window.session.import_state.project_directory_selected = True
    window.session.import_state.import_kind = ImportKind.SAMPLE_SET
    window.session.import_state.source_path = source_dir
    preview = ImportPreview(
        source_path=source_dir,
        preview_lines=("检查通过",),
        unit_lines=(),
        parameter_lines=(),
        detected_scheme="SET_DIR",
        allow_execute=True,
        prepared_runtime=cached_runtime,
    )
    window._cached_import_preview = preview
    window._cached_import_fingerprint = window._current_import_fingerprint()
    calls: list[str] = []

    monkeypatch.setattr(
        window.import_facade,
        "execute_sample_set_repository_from_preview",
        lambda request, preview, controller=None: calls.append("from_preview") or object(),
    )
    monkeypatch.setattr(
        window.import_facade,
        "execute_sample_set_repository",
        lambda request, controller=None: calls.append("full_execute") or object(),
    )

    result = window._build_execute_operation()(None)

    assert result is not None
    assert calls == ["from_preview"]


def test_sample_set_execute_accepts_domain_specific_preview_runtime(tmp_path: Path) -> None:
    """轻量预览复用应接受领域专属样本集运行态，而不是只接受 DefaultSampleSet。"""

    class _DomainSampleSet:
        supported_categories: tuple[str, ...] = ("accel",)
        storable_categories: tuple[str, ...] = ("accel",)
        supported_fields: tuple[str, ...] = ("uid",)
        sample_domain = "vibration_test"
        strict = True
        storage_dirty = False

        def __len__(self) -> int:
            return 0

        def values(self) -> tuple[object, ...]:
            return ()

        def items(self) -> tuple[tuple[str, object], ...]:
            return ()

    source_dir = tmp_path / "repo"
    source_dir.mkdir()
    runtime = _DomainSampleSet()
    preview = ImportPreview(
        source_path=source_dir,
        preview_lines=("检查通过",),
        unit_lines=(),
        parameter_lines=(),
        detected_scheme="SET_SQLITE_H5",
        allow_execute=True,
        prepared_runtime=runtime,
    )

    result = GuiImportFacade().execute_sample_set_repository_from_preview(
        SampleSetImportRequest(source_path=source_dir),
        preview,
    )

    assert result.primary_runtime is runtime
    assert result.primary_summary.class_name == "_DomainSampleSet"


def test_main_window_disables_session_replacement_actions_while_busy(qapp: QApplication) -> None:
    """后台任务运行时不应允许替换或保存当前会话。"""

    del qapp
    window = MainWindow(ProjectSession.build_demo())

    window.session.import_state.busy = True
    window._update_action_states()

    for action_name in ("新建项目", "打开项目", "保存项目", "切换桥梁演示数据", "切换通用演示数据", "校验", "执行"):
        assert not window.actions_map[action_name].isEnabled()

    window.session.finish_import_activity()
    window._update_action_states()

    for action_name in ("新建项目", "打开项目", "保存项目", "切换桥梁演示数据", "切换通用演示数据", "校验", "执行"):
        assert window.actions_map[action_name].isEnabled()


def test_background_managers_register_running_task_before_worker_finishes(
    monkeypatch: pytest.MonkeyPatch, qapp: QApplication
) -> None:
    """处理、绘图和导出任务启动后应立即进入底部任务队列。"""

    session = ProjectSession.build_demo()
    processing = ProcessingManager(session)
    plot = PlotManager(session)
    export = ExportManager(session)

    monkeypatch.setattr(processing, "execute_sync", lambda **_: object())
    monkeypatch.setattr(plot, "render_sync", lambda **_: object())
    monkeypatch.setattr(export, "execute_sync", lambda **_: object())

    processing.start_action(action_name="calc_freqspec")
    assert any(item.title == "处理当前主样本集" and item.status == "进行中" for item in session.tasks)

    plot.start(source_kind="sample_model", source_name="accel")
    assert any(item.title == "绘制当前主样本集" and item.status == "进行中" for item in session.tasks)

    export.start(
        export_kind="scalar_frame",
        output_path="demo.xlsx",
        format_name="xlsx",
        metadata_fields=(),
        features=(),
        data_var="freqspec",
        source="accel",
        include_plots=False,
        include_eval_summary=True,
    )
    assert any(item.title == "导出当前主样本集" and item.status == "进行中" for item in session.tasks)

    for _ in range(50):
        qapp.processEvents()
        if not processing.busy and not plot.busy and not export.busy:
            break
        QTest.qWait(10)

    assert not processing.busy
    assert not plot.busy
    assert not export.busy


def test_processing_execute_reports_per_sample_progress() -> None:
    """执行分析应按样本上报进度，避免长时间只显示 0/1。"""

    class _Runtime:
        def __init__(self) -> None:
            self.calls: list[tuple[str, ...]] = []

        def __len__(self) -> int:
            return 2

        def keys(self) -> tuple[str, str]:
            return ("u1", "u2")

        def calc_freqspec(self, *, uids: tuple[str, ...], strict: bool, overwrite: bool) -> None:
            del strict, overwrite
            self.calls.append(uids)

    session = ProjectSession.build_empty()
    runtime = _Runtime()
    session.primary_runtime = runtime  # type: ignore[assignment]
    controller = ProcessingTaskController()
    updates: list[object] = []
    controller.set_progress_reporter(updates.append)

    result = ProcessingManager(session).execute_sync(action_name="calc_freqspec", controller=controller)

    assert result.affected_count == 2
    assert runtime.calls == [("u1",), ("u2",)]
    assert len(updates) == 3
    assert getattr(updates[-1], "current") == 2
    assert getattr(updates[-1], "total") == 2


def test_module_workspace_emits_processing_request(qapp: QApplication) -> None:
    """处理页按钮应发出真实处理请求。"""

    del qapp
    workspace = ModuleWorkspace()
    captured: list[object] = []

    workspace.processing_workspace.process_requested.connect(captured.append)
    workspace.processing_workspace._run_button.click()

    assert captured
    assert captured[0].action_name == "calc_freqspec"
    assert captured[0].strict is True
    assert captured[0].overwrite is True


def test_processing_workspace_shows_cancel_button_while_busy(qapp: QApplication) -> None:
    """分析任务运行时页面内应提供可见中止入口。"""

    del qapp
    workspace = ModuleWorkspace()
    session = ProjectSession.build_demo()
    session.processing_state.busy = True

    workspace.processing_workspace.load_session(session)

    button = workspace.processing_workspace.findChild(QWidget, "ProcessingCancelButton")
    assert button is not None
    assert not button.isHidden()
    assert button.isEnabled()


def test_module_workspace_uses_import_filter_composite_page(qapp: QApplication) -> None:
    """主导航只保留四页，导入与筛选应合并到同一个工作台。"""

    del qapp
    workspace = ModuleWorkspace()

    assert workspace.count() == 4
    assert workspace.tabText(1) == "导入与筛选"
    assert isinstance(workspace.import_filter_workspace, ImportFilterWorkspace)
    assert isinstance(workspace.import_workflow, ImportWorkflowWidget)
    assert workspace.subset_workspace is workspace.import_filter_workspace.subset_workspace


def test_demo_session_no_longer_seeds_processing_placeholder_task_and_log() -> None:
    """演示会话不应再默认塞入与导入无关的 ZVL 占位任务或处理日志。"""

    session = ProjectSession.build_demo()

    assert all("ZVL" not in item.title for item in session.tasks)
    assert all(item.logger_name != "gui.processing" for item in session.logs)


def test_demo_session_no_longer_uses_placeholder_contract_wording() -> None:
    """演示会话文案不应再把已接入链路描述成占位合同。"""

    session = ProjectSession.build_demo()
    joined_text = "\n".join(
        [
            session.note,
            *(item.detail for item in session.issues),
            *(item.name for item in session.exports),
            *(item.title for item in session.plot_records),
        ]
    )

    assert "当前仅保留" not in joined_text
    assert "占位" not in joined_text


def test_import_workflow_shows_busy_progress_and_chinese_titles(qapp: QApplication) -> None:
    """导入页忙碌时应显示进度提示，且主要分区标题使用中文。"""

    del qapp
    widget = ImportWorkflowWidget()
    session = ProjectSession.build_demo()
    session.reset_for_import(session.import_state.import_kind)
    session.import_state.project_directory_selected = True
    session.import_state.cancellable = True
    session.import_state.busy = True
    session.import_state.busy_title = "正在预览样本集"
    session.import_state.busy_detail = "正在检查仓库结构与单位"

    widget.load_session(session)

    assert widget._sample_set_group.title() == "样本集来源参数"
    assert widget._preview_group.title() == "检查结果"
    assert not widget._busy_progress.isHidden()
    assert widget._busy_status.text() == "正在预览样本集：正在检查仓库结构与单位"
    assert not widget._preview_button.isEnabled()
    assert not widget._deep_check_button.isHidden()
    assert not widget._cancel_button.isHidden()
    assert widget._advanced_toggle.isHidden()


def test_import_workflow_uses_task_cards_not_step_indicator(qapp: QApplication) -> None:
    """数据接入页应去向导化，改为命名任务卡片。"""

    del qapp
    widget = ImportWorkflowWidget()

    titles = [box.title() for box in widget.findChildren(QGroupBox)]

    assert not widget.findChildren(StepIndicator)
    assert "项目上下文" in titles
    assert "接入来源" in titles
    assert "检查结果" in titles
    assert "绑定结果" in titles
    assert "当前项目上下文" not in titles
    assert "接入模式与来源" not in titles
    assert "绑定与执行" not in titles


def test_project_overview_exposes_next_step_actions(qapp: QApplication) -> None:
    """总览页应直接暴露下一步快捷动作。"""

    del qapp
    window = MainWindow(ProjectSession.build_demo())

    action_texts = [button.text() for button in window.workspace.project_overview._next_step_buttons]

    assert action_texts == ["接入主样本集", "管理子样本集", "开始分析", "快速出图", "去交付"]


def test_button_matrix_page_switch_action_routes_to_processing_page(qapp: QApplication) -> None:
    """页面切换类动作应只切页，不直接执行业务。"""

    del qapp
    window = MainWindow(ProjectSession.build_demo())

    window._trigger_action("开始分析")

    assert window.workspace.current_module() is ModuleKey.PROCESSING


def test_button_matrix_preview_action_opens_import_preview_dialog(
    monkeypatch: pytest.MonkeyPatch, qapp: QApplication
) -> None:
    """预览查看类动作应打开真实预览容器。"""

    del qapp
    from dyntool_gui import main_window as main_window_module

    window = MainWindow(ProjectSession.build_demo())
    preview_calls: list[str] = []

    monkeypatch.setattr(
        main_window_module.ImportPreviewDialog,
        "exec",
        lambda self: preview_calls.append(self.windowTitle()),
    )

    window._trigger_action("导入预览")

    assert preview_calls == ["导入文件预览"]


def test_button_matrix_precheck_action_opens_export_precheck_dialog(
    monkeypatch: pytest.MonkeyPatch, qapp: QApplication
) -> None:
    """预检校验类动作应落到真实预检对话框。"""

    del qapp
    from dyntool_gui import main_window as main_window_module

    window = MainWindow(ProjectSession.build_demo())
    precheck_calls: list[str] = []

    monkeypatch.setattr(
        main_window_module.ExportPrecheckDialog,
        "exec",
        lambda self: precheck_calls.append(self.windowTitle()),
    )

    window._trigger_action("去交付")

    assert precheck_calls == ["导出预检"]


def test_button_matrix_info_action_opens_metadata_table_dialog(
    monkeypatch: pytest.MonkeyPatch, qapp: QApplication
) -> None:
    """信息查看类动作应打开只读表格容器。"""

    del qapp
    from dyntool_gui import main_window as main_window_module

    window = MainWindow(ProjectSession.build_demo())
    table_calls: list[str] = []

    monkeypatch.setattr(
        main_window_module.TableDialog,
        "exec",
        lambda self: table_calls.append(self.windowTitle()),
    )

    window._trigger_action("查看 metadata 字段")

    assert table_calls == ["metadata 字段"]


def test_main_window_visible_actions_no_longer_fall_back_to_placeholder(
    monkeypatch: pytest.MonkeyPatch, qapp: QApplication
) -> None:
    """设置、帮助、构建子集和执行导出不应再落回纯占位说明。"""

    del qapp
    from dyntool_gui import main_window as main_window_module

    window = MainWindow(ProjectSession.build_demo())
    settings_calls: list[str] = []
    help_calls: list[str] = []
    export_calls: list[str] = []

    assert not hasattr(main_window_module, "PlaceholderDialog")
    monkeypatch.setattr(
        main_window_module.SettingsDialog,
        "exec",
        lambda self: settings_calls.append(self.windowTitle()),
    )
    monkeypatch.setattr(
        main_window_module.HelpDialog,
        "exec",
        lambda self: help_calls.append(self.windowTitle()),
    )
    monkeypatch.setattr(
        main_window_module.ExportPrecheckDialog,
        "exec",
        lambda self: export_calls.append(self.windowTitle()),
    )

    window._trigger_action("设置")
    window._trigger_action("帮助")
    window._trigger_action("构建子集")
    window._trigger_action("执行工程导出")

    assert settings_calls == ["设置"]
    assert help_calls == ["帮助"]
    assert export_calls == ["导出预检"]


def test_internal_legacy_actions_no_longer_show_placeholder_dialog(
    monkeypatch: pytest.MonkeyPatch, qapp: QApplication
) -> None:
    """内部遗留说明动作不应再通过占位弹窗暴露给用户。"""

    del qapp
    from dyntool_gui import main_window as main_window_module

    window = MainWindow(ProjectSession.build_demo())

    assert not hasattr(main_window_module, "PlaceholderDialog")

    window._trigger_action("设置主集")
    window._trigger_action("设置对比集")
    window._trigger_action("运行处理")


def test_main_window_trigger_action_does_not_keep_internal_noop_routes() -> None:
    """主窗口动作路由不应保留内部 no-op 假动作。"""

    repo_root = Path(__file__).resolve().parents[1]
    source = (repo_root / "src" / "dyntool_gui" / "main_window.py").read_text(encoding="utf-8")

    assert "lambda: None" not in source
    assert '"设置主集"' not in source
    assert '"设置对比集"' not in source
    assert '"运行处理"' not in source


def test_button_matrix_main_execution_action_emits_processing_request(qapp: QApplication) -> None:
    """主链执行类动作应发出真实处理请求。"""

    del qapp
    workspace = ModuleWorkspace()
    captured: list[object] = []

    workspace.processing_workspace.process_requested.connect(captured.append)
    workspace.processing_workspace._run_button.click()

    assert len(captured) == 1
    assert captured[0].action_name == "calc_freqspec"


def test_button_matrix_compute_guidance_action_emits_required_processing(qapp: QApplication) -> None:
    """补算引导类动作应给出明确的待补算动作名。"""

    del qapp
    workspace = ModuleWorkspace()
    captured: list[str] = []

    workspace.plotting_workspace.compute_required.connect(captured.append)
    workspace.plotting_workspace._compute_button.setProperty("action_name", "calc_freqspec")
    workspace.plotting_workspace._compute_button.show()
    workspace.plotting_workspace._compute_button.click()

    assert captured == ["calc_freqspec"]


def test_demo_session_seeds_subset_state_and_scope_defaults() -> None:
    """演示会话应初始化子样本集状态与当前范围。"""

    session = ProjectSession.build_demo()

    assert session.current_scope.scope_kind == "all_samples"
    assert session.subset_state.subsets
    assert session.subset_state.subsets[0].sample_count >= 1


def test_filter_spec_exposes_sorting_and_paging_fields() -> None:
    """筛选规格应覆盖排序与分页，支撑统一数据预览。"""

    spec = FilterSpec(keyword="P1", sort_by="point", sort_desc=True, limit=50, offset=100)

    assert spec.sort_by == "point"
    assert spec.sort_desc is True
    assert spec.limit == 50
    assert spec.offset == 100


def test_subset_definition_exposes_dynamic_or_frozen_mode() -> None:
    """命名子集应显式区分动态规则与冻结快照。"""

    dynamic = SubsetDefinition(
        id="subset.dynamic",
        name="动态子集",
        filter_spec=FilterSpec(keyword="A"),
        resolved_uids=("S1",),
        sample_count=1,
        created_at="2026-04-23 10:00:00",
        updated_at="2026-04-23 10:00:00",
        mode="dynamic",
    )
    frozen = SubsetDefinition(
        id="subset.frozen",
        name="冻结快照",
        filter_spec=FilterSpec(keyword="A"),
        resolved_uids=("S1",),
        sample_count=1,
        created_at="2026-04-23 10:00:00",
        updated_at="2026-04-23 10:00:00",
        mode="frozen",
    )

    assert dynamic.frozen is False
    assert frozen.frozen is True


def test_subset_workspace_refresh_does_not_emit_selection_request(qapp: QApplication) -> None:
    """刷新子集表格并恢复选中行时不应触发用户选择信号，避免递归刷新。"""

    del qapp
    session = ProjectSession.build_demo()
    selected_subset_id = session.subset_state.subsets[0].id
    session.subset_state.selected_subset_id = selected_subset_id
    widget = ModuleWorkspace().subset_workspace
    captured: list[str] = []

    widget.selection_requested.connect(captured.append)
    widget.load_session(session)

    assert widget.selected_subset_id() == selected_subset_id
    assert captured == []


def test_import_mode_bottom_rows_focus_on_import_context() -> None:
    """导入模块的底部任务区应优先显示导入上下文，而不是处理占位记录。"""

    session = ProjectSession.build_demo()
    session.current_module = ModuleKey.IMPORT

    rows = PanelDataBuilder().build_bottom_rows(session)

    assert all("ZVL" not in row[0] for row in rows["任务队列"])
    assert all(row[2] != "gui.processing" for row in rows["运行日志"])


def test_main_window_removes_right_info_dock(qapp: QApplication) -> None:
    """主窗口应移除右侧事实栏，中央工作区优先。"""

    del qapp
    window = MainWindow(ProjectSession.build_demo())

    dock_titles = {dock.windowTitle() for dock in window.findChildren(type(window.left_dock))}

    assert "当前页事实" not in dock_titles
    assert len(dock_titles) == 2


def test_task_manager_filters_import_rows_consistently() -> None:
    """TaskManager 在导入页应收口为导入相关记录。"""

    session = ProjectSession.build_demo()
    manager = TaskManager()

    all_rows = manager.build_bottom_rows(session)
    session.current_module = ModuleKey.IMPORT
    import_rows = manager.build_bottom_rows(session)

    assert len(import_rows["任务队列"]) <= len(all_rows["任务队列"])
    assert all("ZVL" not in row[0] for row in import_rows["任务队列"])


def test_main_views_use_model_view_widgets(qapp: QApplication) -> None:
    """主视图资源树与底部表格应切换到 Model/View。"""

    del qapp
    window = MainWindow(ProjectSession.build_demo())

    tree_views = window.resource_tree.findChildren(QTreeView)
    table_views = window.bottom_panel.findChildren(QTableView)

    assert tree_views
    assert window.resource_tree.model() is not None
    assert window.resource_tree.model().__class__.__name__ == "ResourceTreeModel"
    assert table_views
    assert all(view.model() is not None for view in table_views)
    assert all(view.model().__class__.__name__.endswith("TableModel") for view in table_views)


def test_subset_workspace_builds_metadata_hook_fields_from_session(qapp: QApplication) -> None:
    """子集页应按 metadata 字段动态生成 hook 控件。"""

    del qapp
    session = ProjectSession.build_demo()
    widget = ModuleWorkspace().subset_workspace

    widget.load_session(session)

    field_names = tuple(spec.field_name for spec in widget.metadata_hook_specs())

    assert "case" in field_names
    assert "point" in field_names
    assert len(field_names) == len(session.primary_sampleset.metadata_fields)


def test_subset_workspace_uses_metadata_table_preview(qapp: QApplication) -> None:
    """子集页预览主表应展示 metadata_df 风格列。"""

    del qapp
    session = ProjectSession.build_demo()
    session.subset_state.preview_rows = (("SMP_001", "sample_1", "工况A", "桥中点", "ACC-1", "Z"),)
    session.subset_state.preview_columns = ("UID", "Alias", "case", "point", "instr", "dir")
    widget = ModuleWorkspace().subset_workspace

    widget.load_session(session)

    headers = [
        widget._preview_table.horizontalHeaderItem(index).text() for index in range(widget._preview_table.columnCount())
    ]

    assert headers[:2] == ["UID", "Alias"]
    assert "point" in headers
    assert "instr" in headers


def test_processing_workspace_shows_action_specific_parameter_group(qapp: QApplication) -> None:
    """分析页应按动作切换专属参数区。"""

    del qapp
    widget = ModuleWorkspace().processing_workspace

    def field_names() -> list[str]:
        names: list[str] = []
        for index in range(widget._specific_form.rowCount()):
            label_item = widget._specific_form.itemAt(index, QFormLayout.ItemRole.LabelRole)
            if label_item is None:
                continue
            label_widget = label_item.widget()
            if label_widget is not None:
                names.append(label_widget.text().rstrip(":"))
        return names

    widget._set_action_value("calc_freqspec")
    assert field_names() == ["额外参数"]

    widget._set_action_value("calc_respspec")
    assert {"method", "calc_unit_system", "output_unit_system", "periods"}.issubset(set(field_names()))

    widget._set_action_value("eval_zvl")
    assert {"freq_range_min", "freq_range_max", "weight_type", "time_windows"}.issubset(set(field_names()))


def test_resource_tree_has_fixed_structure_across_modules(qapp: QApplication) -> None:
    """对象树在非总览页应保持固定结构，切换到导入页不应隐藏图形记录和导出记录节点。"""

    del qapp
    session = ProjectSession.build_demo()
    window = MainWindow(session)
    model = window.resource_tree.model()

    initial_titles = [model.data(model.index(row, 0)) for row in range(model.rowCount())]
    assert "当前主样本集" in initial_titles
    assert "子集集合" in initial_titles
    assert "其他集合" in initial_titles
    assert "图形记录" in initial_titles
    assert "导出记录" in initial_titles

    session.set_current_module(ModuleKey.IMPORT)
    window._refresh_resource_tree()

    import_titles = [model.data(model.index(row, 0)) for row in range(model.rowCount())]

    assert "图形记录" in import_titles
    assert "导出记录" in import_titles


def test_resource_tree_keeps_default_snapshot_compact(qapp: QApplication) -> None:
    """对象树默认只展开顶层与当前路径，避免整树摊开。"""

    del qapp
    window = MainWindow(ProjectSession.build_demo())
    tree_view = window.resource_tree._tree_view
    model = window.resource_tree.model()

    primary_index = model.index_for_key("sampleset.primary")
    child_index = model.index(0, 0, primary_index)

    assert primary_index.isValid()
    assert tree_view.isExpanded(primary_index) is True
    assert child_index.isValid()
    assert tree_view.isExpanded(child_index) is False


def test_resource_tree_uses_compact_row_metrics(qapp: QApplication) -> None:
    """对象树应使用紧凑缩进和行高，避免左侧导航留白过宽。"""

    del qapp
    window = MainWindow(ProjectSession.build_demo())
    tree_view = window.resource_tree._tree_view

    assert tree_view.indentation() <= 12
    assert tree_view.iconSize().width() <= 14
    assert tree_view.uniformRowHeights() is True


def test_subset_workspace_prioritizes_center_preview_width(qapp: QApplication) -> None:
    """横屏下子集页默认优先给中间预览表，但左右栏允许用户拖宽。"""

    del qapp
    widget = ModuleWorkspace().subset_workspace
    scroll_areas = widget.findChildren(QScrollArea, "SubsetFilterScrollArea")
    preview_table = widget.findChild(QTableWidget, "SubsetMetadataPreviewTable")
    saved_panel = widget.findChild(QWidget, "SubsetSavedPanel")
    splitter = widget.findChild(QSplitter, "SubsetWorkspaceSplitter")

    assert scroll_areas
    assert preview_table is not None
    assert saved_panel is not None
    assert splitter is not None
    assert splitter.childrenCollapsible() is False
    assert scroll_areas[0].maximumWidth() <= LANDSCAPE_1080P_PROFILE.side_panel_max_width
    assert preview_table.minimumWidth() >= 560
    assert splitter.sizes()[1] > splitter.sizes()[0]
    assert splitter.sizes()[1] > splitter.sizes()[2]
    assert saved_panel.maximumWidth() <= LANDSCAPE_1080P_PROFILE.saved_panel_max_width


def test_import_filter_workspace_keeps_import_panel_narrow(qapp: QApplication) -> None:
    """导入与筛选页外层也应优先保留右侧表格/子集工作区宽度。"""

    del qapp
    widget = ImportFilterWorkspace()
    widget.resize(1600, 900)
    widget.show()
    splitter = widget.findChild(QSplitter, "ImportFilterWorkspaceSplitter")

    assert splitter is not None
    assert splitter.childrenCollapsible() is False
    assert splitter.sizes()[0] <= LANDSCAPE_1080P_PROFILE.import_workflow_max_width
    assert splitter.sizes()[1] > splitter.sizes()[0]


def test_export_workspace_removes_report_package_entry(qapp: QApplication) -> None:
    """导出工作区首版不再暴露报告包入口。"""

    del qapp
    widget = ExportWorkspace()

    export_kinds = [widget._kind_combo.itemData(index) for index in range(widget._kind_combo.count())]

    assert export_kinds == ["scalar_frame", "series_frame", "peaks_frame", "current_plot_image"]


def test_bottom_panel_filters_rows_by_current_module(qapp: QApplication) -> None:
    """切到导入页后底部区应保留导入上下文记录。"""

    del qapp
    session = ProjectSession.build_demo()
    window = MainWindow(session)

    task_model = window.bottom_panel.table_model("任务队列")
    log_model = window.bottom_panel.table_model("运行日志")
    assert task_model.rowCount() >= 1
    assert log_model.rowCount() >= 1

    session.set_current_module(ModuleKey.IMPORT)
    window._refresh_bottom_panel()

    import_task_model = window.bottom_panel.table_model("任务队列")
    import_log_model = window.bottom_panel.table_model("运行日志")
    import_task_titles = [
        import_task_model.data(import_task_model.index(row, 0)) for row in range(import_task_model.rowCount())
    ]
    import_log_sources = [
        import_log_model.data(import_log_model.index(row, 2)) for row in range(import_log_model.rowCount())
    ]

    assert all("ZVL" not in str(title) for title in import_task_titles)
    assert all(source in {"gui.import", "gui.project", "gui.session"} for source in import_log_sources)


def test_main_window_uses_menu_and_task_navigation_without_main_toolbar(qapp: QApplication) -> None:
    """顶部应收口为菜单栏加任务导航，不再保留主图标工具栏。"""

    del qapp
    window = MainWindow(ProjectSession.build_demo())

    assert window.findChild(QToolBar, "MainToolbar") is None
    assert window.findChild(QToolBar, "MainToolBar") is None
    assert window.menuBar().actions()
    assert {"新建项目", "打开项目", "保存项目", "校验", "执行"}.issubset(set(window.actions_map))
    bad_mojibake_prefixes = tuple(chr(codepoint) for codepoint in (0x93C2, 0x93B5))
    assert all(not action_name.startswith(bad_mojibake_prefixes) for action_name in window.actions_map)


def test_module_workspace_uses_custom_top_navigation(qapp: QApplication) -> None:
    """中央工作区应使用自定义顶部任务导航。"""

    del qapp
    workspace = ModuleWorkspace()

    assert hasattr(workspace, "_nav_buttons")
    assert len(workspace._nav_buttons) == 4
    assert [button.text() for button in workspace._nav_buttons] == [
        MODULE_LABELS[ModuleKey.PROJECT],
        MODULE_LABELS[ModuleKey.IMPORT],
        MODULE_LABELS[ModuleKey.PROCESSING],
        MODULE_LABELS[ModuleKey.PLOTTING],
    ]


def test_module_workspace_pages_expose_consistent_page_headers(qapp: QApplication) -> None:
    """四个正式页面应统一暴露页面头部，固定标题语气。"""

    del qapp
    workspace = ModuleWorkspace()
    session = ProjectSession.build_demo()
    workspace.load_session(session)

    expected = {
        "Project": "总览",
        "ImportFilter": "导入与筛选",
        "Processing": "数据处理",
        "Plotting": "图形绘制",
    }

    for prefix, title in expected.items():
        header = workspace.findChild(QWidget, f"{prefix}PageHeader")
        title_label = workspace.findChild(QLabel, f"{prefix}PageHeaderTitle")
        subtitle_label = workspace.findChild(QLabel, f"{prefix}PageHeaderSubtitle")
        summary_label = workspace.findChild(QLabel, f"{prefix}PageHeaderSummary")

        assert header is not None
        assert title_label is not None
        assert subtitle_label is not None
        assert summary_label is not None
        assert title_label.text() == title
        assert subtitle_label.text()
        assert summary_label.text()


def test_formal_pages_expose_stable_action_and_result_regions(qapp: QApplication) -> None:
    """正式页面应暴露稳定的动作区与结果区结构锚点。"""

    del qapp
    workspace = ModuleWorkspace()

    expected_regions = (
        ("ImportActionRegion", "ImportResultRegion"),
        ("ProcessingActionRegion", "ProcessingResultRegion"),
        ("PlottingActionRegion", "PlottingResultRegion"),
    )
    for action_name, result_name in expected_regions:
        action_region = workspace.findChild(QWidget, action_name)
        result_region = workspace.findChild(QWidget, result_name)

        assert action_region is not None
        assert result_region is not None
        assert action_region.property("surfaceRole")
        assert result_region.property("surfaceRole")


def test_navigation_and_page_headers_use_compact_visual_contract(qapp: QApplication) -> None:
    """页面导航和头部应使用更紧凑的正式视觉合同。"""

    del qapp
    workspace = ModuleWorkspace()
    header = workspace.findChild(QWidget, "ProjectPageHeader")

    assert workspace._nav_buttons
    assert all(button.minimumHeight() <= LANDSCAPE_2K_PROFILE.nav_button_height for button in workspace._nav_buttons)
    assert all(button.maximumHeight() <= LANDSCAPE_2K_PROFILE.nav_button_height for button in workspace._nav_buttons)
    assert header is not None
    assert header.property("surfaceRole") == "pageHeader"
    assert header.maximumHeight() <= LANDSCAPE_2K_PROFILE.page_header_max_height


def test_context_bar_uses_high_contrast_title_strip(qapp: QApplication) -> None:
    """顶部项目上下文条必须是深色标题条，避免浅底白字不可读。"""

    del qapp
    workspace = ModuleWorkspace()

    assert workspace._context_bar.property("surfaceRole") == "contextBar"
    assert workspace._context_label.objectName() == "ContextBarTitleLabel"
    assert "#1E3A8A" in workspace._context_bar.styleSheet()
    assert "#FFFFFF" in workspace._context_label.styleSheet()


def test_formal_pages_keep_landscape_page_header_height(qapp: QApplication) -> None:
    """四个正式页面页头应保持低高度横屏合同。"""

    del qapp
    workspace = ModuleWorkspace()

    for page_key in ("Project", "ImportFilter", "Processing", "Plotting"):
        header = workspace.findChild(QWidget, f"{page_key}PageHeader")
        assert header is not None
        assert header.maximumHeight() <= LANDSCAPE_2K_PROFILE.page_header_max_height


def test_project_overview_uses_two_column_dashboard_grid(qapp: QApplication) -> None:
    """总览页应使用两列网格仪表盘布局，包含主集卡片和快速操作按钮。"""

    del qapp
    widget = ModuleWorkspace().project_overview

    assert hasattr(widget, "_primary_card")
    assert hasattr(widget, "_capability_card")
    assert hasattr(widget, "_action_card")
    assert hasattr(widget, "_next_step_buttons")
    assert len(widget._next_step_buttons) >= 4


def test_plotting_workspace_uses_three_pane_workbench_layout(qapp: QApplication) -> None:
    """图形页应收口为左配置、中预览，并带底部结果页签。"""

    del qapp
    widget = PlottingWorkspace()

    assert hasattr(widget, "_control_panel")
    assert hasattr(widget, "_preview_panel")
    assert hasattr(widget, "_result_tabs")
    assert widget.findChild(QWidget, "PlottingFactsPanel") is None
    assert widget._result_tabs.count() >= 2


def test_import_workflow_uses_compact_stage_summary(qapp: QApplication) -> None:
    """数据接入页顶部应压成单行状态摘要。"""

    del qapp
    widget = ImportWorkflowWidget()
    session = ProjectSession.build_demo()

    widget.load_session(session)

    assert hasattr(widget, "_stage_summary")
    assert "项目" in widget._stage_summary.text()
    assert not hasattr(widget, "_stage_labels")
    assert widget._stage_summary.property("cardRole") == "heroSummary"
    assert widget._preview_text.maximumHeight() <= 120
    assert widget._units_text.maximumHeight() <= 120
    assert widget._parameter_text.maximumHeight() <= 88
    assert widget.maximumWidth() <= LANDSCAPE_2K_PROFILE.import_workflow_max_width


def test_import_filter_workspace_keeps_import_panel_within_width_limit(qapp: QApplication) -> None:
    """导入页左侧配置面板应有最大宽度约束，内容通过垂直滚动展开。"""

    del qapp
    workspace = ImportFilterWorkspace()

    assert workspace.import_workflow.maximumWidth() <= LANDSCAPE_2K_PROFILE.import_workflow_max_width
    assert workspace.import_workflow.findChild(QScrollArea, "ImportSourceScrollArea") is not None


def test_import_filter_workspace_avoids_duplicate_scope_banner(qapp: QApplication) -> None:
    """导入与筛选页顶部不应重复渲染独立范围横条。"""

    del qapp
    workspace = ImportFilterWorkspace()

    assert not hasattr(workspace, "_scope_label")
    summary_label = workspace.findChild(QLabel, "ImportFilterPageHeaderSummary")
    assert summary_label is not None
    assert "\n" not in summary_label.text()


def test_processing_workspace_uses_narrow_scrollable_action_rail(qapp: QApplication) -> None:
    """数据处理页左侧参数栏默认收窄，但 splitter 允许用户继续拖宽。"""

    del qapp
    widget = ModuleWorkspace().processing_workspace
    action_region = widget.findChild(QScrollArea, "ProcessingActionRegion")
    result_region = widget.findChild(QWidget, "ProcessingResultRegion")
    splitter = widget.findChild(QSplitter, "ProcessingWorkspaceSplitter")

    assert action_region is not None
    assert result_region is not None
    assert splitter is not None
    assert splitter.sizes()[0] <= 340
    assert action_region.maximumWidth() >= LANDSCAPE_2K_PROFILE.side_panel_max_width


def test_processing_workspace_keeps_primary_actions_above_preview_group(qapp: QApplication) -> None:
    """1080P 下处理页主按钮应靠近动作配置区，不应被推到滚动栏底部。"""

    del qapp
    widget = ModuleWorkspace().processing_workspace
    action_region = widget.findChild(QScrollArea, "ProcessingActionRegion")

    assert action_region is not None
    panel = action_region.widget()
    assert panel is not None
    layout = panel.layout()
    assert layout is not None
    assert layout.indexOf(widget._run_button) < layout.indexOf(widget._preview_button)
    assert layout.indexOf(widget._run_button) < layout.indexOf(widget._summary)


def test_processing_workspace_uses_compact_status_summary_without_large_numbers(qapp: QApplication) -> None:
    """数据处理页不应使用大号数字指标卡抢占主工作区视觉中心。"""

    del qapp
    widget = ModuleWorkspace().processing_workspace
    metrics_frame = widget.findChild(QFrame, "ProcessingMetricsFrame")
    summary_label = widget.findChild(QLabel, "ProcessingMetricsSummaryLabel")

    assert metrics_frame is not None
    assert metrics_frame.maximumHeight() <= 34
    assert summary_label is not None
    assert "完成结果" in summary_label.text()
    assert not hasattr(widget, "_metric_done")
    assert not hasattr(widget, "_metric_gap")
    assert not hasattr(widget, "_metric_time")


def test_processing_workspace_can_restore_runtime_before_execute(qapp: QApplication, tmp_path: Path) -> None:
    """项目有可恢复导入来源时，执行分析仍保持固定主入口。"""

    del qapp
    source_dir = tmp_path / "data"
    source_dir.mkdir()
    session = ProjectSession.build_demo()
    session.primary_runtime = None
    session.import_state.import_kind = ImportKind.SAMPLE_SET
    session.import_state.source_path = source_dir
    widget = ModuleWorkspace().processing_workspace

    widget.load_session(session)

    assert widget._run_button.isEnabled()
    assert widget._run_button.text() == "执行分析"
    assert "恢复运行态" in widget._phase_label.text()


def test_processing_workspace_keeps_execute_button_available_for_precheck_errors(qapp: QApplication) -> None:
    """缺少运行态时仍应保留执行分析入口，由点击后的校验负责报错。"""

    del qapp
    session = ProjectSession.build_demo()
    session.primary_runtime = None
    session.import_state.source_path = None
    widget = ModuleWorkspace().processing_workspace

    widget.load_session(session)

    assert widget._run_button.isEnabled()
    assert widget._run_button.text() == "执行分析"


def test_processing_workspace_uses_current_saved_subset_scope(qapp: QApplication) -> None:
    """子集设为当前范围后，数据处理页应预填当前子集而不是停留在默认全部样本。"""

    del qapp
    session = ProjectSession.build_demo()
    subset_id = session.subset_state.subsets[0].id
    session.set_current_scope("saved_subset", subset_ids=(subset_id,), note="当前子样本集")
    widget = ModuleWorkspace().processing_workspace

    widget.load_session(session)
    request = widget.processing_request_values()

    assert request.scope_kind == "saved_subset"
    assert request.scope_target == subset_id


def test_main_window_routes_processing_through_runtime_restore(
    monkeypatch: pytest.MonkeyPatch, qapp: QApplication, tmp_path: Path
) -> None:
    """处理动作在运行态缺失但来源可恢复时，应先启动恢复任务而不是直接失败。"""

    del qapp
    source_dir = tmp_path / "data"
    source_dir.mkdir()
    session = ProjectSession.build_demo()
    session.primary_runtime = None
    session.import_state.import_kind = ImportKind.SAMPLE_SET
    session.import_state.source_path = source_dir
    window = MainWindow(session)
    started: list[dict[str, object]] = []
    warnings: list[str] = []

    monkeypatch.setattr(window.import_manager, "start_operation", lambda **kwargs: started.append(kwargs))
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: warnings.append(str(args[2])))

    request = ProcessingRequestSnapshot(action_name="calc_freqspec")
    window._run_processing(request)

    assert warnings == []
    assert window._pending_processing_request == request
    assert started
    assert started[0]["mode"] == "restore_runtime"
    assert started[0]["task_title"] == "恢复主样本集运行态"


def test_main_window_reports_processing_precheck_failure_to_issues(
    monkeypatch: pytest.MonkeyPatch, qapp: QApplication
) -> None:
    """执行分析缺少前置条件时，应同时弹错并写入底部问题列表。"""

    del qapp
    window = MainWindow(ProjectSession.build_demo())
    window.session.primary_runtime = None
    window.session.import_state.source_path = None
    warnings: list[str] = []

    monkeypatch.setattr(QMessageBox, "warning", lambda *args: warnings.append(str(args[2])))

    window._run_processing(ProcessingRequestSnapshot(action_name="calc_freqspec"))

    assert warnings
    assert window.session.issues
    assert window.session.issues[0].status == "失败"
    assert window.session.issues[0].title == "处理前置校验"


def test_main_window_use_subset_scope_routes_to_processing_page(qapp: QApplication) -> None:
    """从子集管理设为当前范围后，应直接进入数据处理页并同步处理范围。"""

    del qapp
    window = MainWindow(ProjectSession.build_demo())
    subset_id = window.session.subset_state.subsets[0].id

    window._use_subset_scope(subset_id)

    assert window.workspace.current_module() is ModuleKey.PROCESSING
    request = window.workspace.processing_workspace.processing_request_values()
    assert request.scope_kind == "saved_subset"
    assert request.scope_target == subset_id


def test_plotting_workspace_can_restore_runtime_before_render(qapp: QApplication, tmp_path: Path) -> None:
    """项目有可恢复导入来源时，图形页应允许恢复运行态后渲染。"""

    del qapp
    source_dir = tmp_path / "data"
    source_dir.mkdir()
    session = ProjectSession.build_demo()
    session.primary_runtime = None
    session.import_state.import_kind = ImportKind.SAMPLE_SET
    session.import_state.source_path = source_dir
    widget = ModuleWorkspace().plotting_workspace

    widget.load_session(session)

    assert widget._render_button.isEnabled()
    assert widget._render_button.text() == "恢复并渲染"
    assert "恢复运行态" in widget._empty_state_label.text()


def test_plotting_workspace_uses_narrow_control_rail_and_limited_result_tabs(qapp: QApplication) -> None:
    """图形页左侧配置栏默认收窄但可拉伸，底部结果页签不挤压画布。"""

    del qapp
    widget = PlottingWorkspace()
    action_region = widget.findChild(QScrollArea, "PlottingActionRegion")
    splitter = widget.findChild(QSplitter, "PlottingWorkspaceSplitter")

    assert action_region is not None
    assert splitter is not None
    assert splitter.sizes()[0] <= 340
    assert action_region.maximumWidth() >= LANDSCAPE_2K_PROFILE.side_panel_max_width
    assert widget._result_tabs.maximumHeight() <= LANDSCAPE_2K_PROFILE.result_tabs_max_height


def test_plotting_workspace_exposes_canvas_center_empty_hint(qapp: QApplication) -> None:
    """1080P 下绘图空画布应有中心提示，避免大片白区被误判为未渲染。"""

    del qapp
    widget = PlottingWorkspace()
    hint = widget.findChild(QLabel, "PlottingCanvasHintLabel")

    assert hint is not None
    assert hint.property("cardRole") == "emptyState"
    assert "恢复并渲染" in hint.text() or "渲染" in hint.text()


def test_plotting_workspace_supports_single_and_multi_sample_modes(qapp: QApplication) -> None:
    """图形页应提供单样本图和多样本图双模式，并包含样本列表页签。"""

    del qapp
    widget = PlottingWorkspace()

    assert hasattr(widget, "_plot_mode_combo")
    modes = [widget._plot_mode_combo.itemData(index) for index in range(widget._plot_mode_combo.count())]
    assert modes == ["single_sample", "multi_sample"]
    assert widget._result_tabs.count() >= 3


def test_plotting_sample_candidates_do_not_rescan_runtime_per_uid(qapp: QApplication) -> None:
    """图形页样本候选刷新不应按 UID 反复扫描大型运行态。"""

    del qapp

    class _Sample:
        def __init__(self, alias: str) -> None:
            self.alias = alias

    class _Runtime:
        def __init__(self) -> None:
            self.items_calls = 0
            self._items = tuple((f"uid-{index}", _Sample(f"alias-{index}")) for index in range(8))

        def keys(self) -> tuple[str, ...]:
            return tuple(uid for uid, _ in self._items)

        def items(self) -> tuple[tuple[str, _Sample], ...]:
            self.items_calls += 1
            return self._items

    session = ProjectSession.build_demo()
    runtime = _Runtime()
    session.primary_runtime = runtime  # type: ignore[assignment]
    session.current_scope = session.current_scope.__class__(scope_kind="all_samples")
    widget = PlottingWorkspace()

    widget._rebuild_sample_candidates(session)

    assert runtime.items_calls <= 1
    assert widget._single_sample_combo.count() == 8


def test_gui_contract_source_files_do_not_reintroduce_facts_panel_or_placeholder_copy() -> None:
    """关键源码不应把旧三栏结构或主流程占位文案带回正式实现。"""

    repo_root = Path(__file__).resolve().parents[1]
    plotting_source = (repo_root / "src" / "dyntool_gui" / "widgets" / "plotting_workspace.py").read_text(
        encoding="utf-8"
    )
    dialogs_source = (repo_root / "src" / "dyntool_gui" / "widgets" / "dialogs.py").read_text(encoding="utf-8")

    assert "PlottingFactsPanel" not in plotting_source
    assert "后续轮次接入" not in dialogs_source
    assert "SettingsDialog" in dialogs_source
    assert "HelpDialog" in dialogs_source
    assert "ImportPreviewDialog" in dialogs_source
    assert "ExportPrecheckDialog" in dialogs_source


def test_gui_classes_do_not_define_duplicate_methods() -> None:
    """GUI 类中不应保留同名方法死代码，避免信号路由和维护口径失真。"""

    repo_root = Path(__file__).resolve().parents[1]
    duplicate_methods: list[str] = []
    for path in sorted((repo_root / "src" / "dyntool_gui").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            seen: dict[str, int] = {}
            for item in node.body:
                if not isinstance(item, ast.FunctionDef):
                    continue
                if item.name in seen:
                    duplicate_methods.append(
                        f"{path.relative_to(repo_root)}:{item.lineno} {node.name}.{item.name} "
                        f"duplicates line {seen[item.name]}"
                    )
                else:
                    seen[item.name] = item.lineno

    assert duplicate_methods == []


def test_gui_architecture_assets_keep_current_four_page_contract() -> None:
    """开发资产源文件应统一保持 4 页与导出能力口径。"""

    repo_root = Path(__file__).resolve().parents[1]
    asset_root = repo_root / "docs" / "developer" / "assets" / "gui_architecture"
    source_files = (
        asset_root / "advdyntool-gui-overall-architecture.spec.yaml",
        asset_root / "advdyntool-gui-overall-architecture.arch.json",
        asset_root / "advdyntool-gui-business-swimlane.spec.yaml",
        asset_root / "advdyntool-gui-business-swimlane.arch.json",
        asset_root / "advdyntool-gui-plot-delivery-swimlane.spec.yaml",
        asset_root / "advdyntool-gui-plot-delivery-swimlane.arch.json",
    )
    removed_generated_files = (
        asset_root / "advdyntool-gui-overall-architecture.drawio",
        asset_root / "advdyntool-gui-overall-architecture.svg",
        asset_root / "advdyntool-gui-business-swimlane.drawio",
        asset_root / "advdyntool-gui-business-swimlane.svg",
        asset_root / "advdyntool-gui-plot-delivery-swimlane.drawio",
        asset_root / "advdyntool-gui-plot-delivery-swimlane.svg",
    )

    merged_text = "\n".join(file.read_text(encoding="utf-8") for file in source_files)

    assert "交付页" not in merged_text
    assert "6 页主导航" not in merged_text
    assert "导出预检 / 导出工作区" in merged_text
    assert "导出记录" in merged_text
    for path in removed_generated_files:
        assert not path.exists()


def test_overview_next_step_actions_drive_smoke_flow(monkeypatch: pytest.MonkeyPatch, qapp: QApplication) -> None:
    """总览页快捷动作应形成可执行闭环，而不是说明型按钮。"""

    del qapp
    from dyntool_gui import main_window as main_window_module

    window = MainWindow(ProjectSession.build_demo())
    export_calls: list[str] = []
    action_buttons = {button.text(): button for button in window.workspace.project_overview._next_step_buttons}

    monkeypatch.setattr(
        main_window_module.ExportPrecheckDialog,
        "exec",
        lambda self: export_calls.append(self.windowTitle()),
    )

    action_buttons["接入主样本集"].click()
    assert window.workspace.current_module() is ModuleKey.IMPORT

    action_buttons["管理子样本集"].click()
    assert window.workspace.current_module() is ModuleKey.IMPORT

    action_buttons["开始分析"].click()
    assert window.workspace.current_module() is ModuleKey.PROCESSING

    action_buttons["快速出图"].click()
    assert window.workspace.current_module() is ModuleKey.PLOTTING

    action_buttons["去交付"].click()
    assert export_calls == ["导出预检"]


def test_main_window_user_visible_dialog_actions_use_real_containers(
    monkeypatch: pytest.MonkeyPatch, qapp: QApplication
) -> None:
    """主流程查看与预检入口应路由到真实对话框容器，而不是占位弹窗。"""

    del qapp
    from dyntool_gui import main_window as main_window_module

    window = MainWindow(ProjectSession.build_demo())
    dialog_calls: list[str] = []

    assert not hasattr(main_window_module, "PlaceholderDialog")
    monkeypatch.setattr(
        main_window_module.SettingsDialog,
        "exec",
        lambda self: dialog_calls.append(self.windowTitle()),
    )
    monkeypatch.setattr(
        main_window_module.HelpDialog,
        "exec",
        lambda self: dialog_calls.append(self.windowTitle()),
    )
    monkeypatch.setattr(
        main_window_module.ImportPreviewDialog,
        "exec",
        lambda self: dialog_calls.append(self.windowTitle()),
    )
    monkeypatch.setattr(
        main_window_module.ResultPreviewDialog,
        "exec",
        lambda self: dialog_calls.append(self.windowTitle()),
    )
    monkeypatch.setattr(
        main_window_module.FigurePreviewDialog,
        "exec",
        lambda self: dialog_calls.append(self.windowTitle()),
    )
    monkeypatch.setattr(
        main_window_module.ExportPrecheckDialog,
        "exec",
        lambda self: dialog_calls.append(self.windowTitle()),
    )
    monkeypatch.setattr(
        main_window_module.CodeReviewResultDialog,
        "exec",
        lambda self: dialog_calls.append(self.windowTitle()),
    )

    for action_name in (
        "设置",
        "帮助",
        "导入预览",
        "查看结果预览",
        "打开大图预览",
        "刷新预览",
        "交付预检",
        "代码审查结果",
    ):
        window._trigger_action(action_name)

    assert dialog_calls == [
        "设置",
        "帮助",
        "导入文件预览",
        "处理结果预览",
        "大图预览",
        "大图预览",
        "导出预检",
        "代码审查结果",
    ]


def test_workbench_smoke_keeps_four_page_shell_and_export_capability_available(qapp: QApplication) -> None:
    """工作台闭环 smoke 应保持 4 页壳层，并能从正式页面进入导出能力。"""

    del qapp
    session = ProjectSession.build_demo()
    workspace = ModuleWorkspace()

    workspace.load_session(session)
    workspace.set_current_module(ModuleKey.PROJECT)
    assert workspace.current_module() is ModuleKey.PROJECT

    workspace.set_current_module(ModuleKey.IMPORT)
    workspace.import_filter_workspace.focus_import_workspace()
    assert workspace.current_module() is ModuleKey.IMPORT

    workspace.import_filter_workspace.focus_subset_workspace()
    assert workspace.current_module() is ModuleKey.IMPORT

    workspace.set_current_module(ModuleKey.PROCESSING)
    assert workspace.current_module() is ModuleKey.PROCESSING
    assert workspace.processing_workspace.processing_request_values().action_name == "calc_freqspec"

    workspace.set_current_module(ModuleKey.PLOTTING)
    assert workspace.current_module() is ModuleKey.PLOTTING
    assert workspace.plotting_workspace.findChild(QWidget, "PlottingFactsPanel") is None

    workspace.export_workspace.load_session(session)
    export_values = workspace.export_workspace.export_request_values()
    assert export_values[0] == session.export_state.export_kind
    validation_values = workspace.export_workspace.validation_request_values()
    assert workspace.count() == 4
    assert validation_values[0] == session.export_state.export_kind


def test_project_session_build_empty_uses_non_demo_defaults() -> None:
    """默认正式入口应构造空项目会话，而不是自动进入演示项目。"""

    session = ProjectSession.build_empty()

    assert session.demo_key == ""
    assert session.project_name == "未命名 GUI 项目"
    assert session.primary_sampleset.sample_count == 0
    assert session.note == "当前未加载主样本集，请先选择项目目录并导入数据。"


def test_main_window_defaults_to_empty_project_session(qapp: QApplication) -> None:
    """未显式传入会话时，主窗口默认应进入空项目会话。"""

    del qapp
    window = MainWindow()

    assert window.session.demo_key == ""
    assert window.session.project_name == "未命名 GUI 项目"
    assert "未命名 GUI 项目" in window.windowTitle()


def test_app_main_uses_empty_session_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """应用默认启动应使用空项目会话，而不是 demo 会话。"""

    from dyntool_gui import app as app_module

    class _FakeApp:
        @staticmethod
        def instance() -> None:
            return None

        def __init__(self, _args: object) -> None:
            pass

        def exec(self) -> int:
            return 0

    captured_window: list[MainWindow] = []

    class _FakeWindow:
        def __init__(self, session: ProjectSession) -> None:
            self.session = session
            captured_window.append(self)

        def show(self) -> None:
            return None

    monkeypatch.setattr(app_module, "ProjectSession", ProjectSession)
    monkeypatch.setattr("PySide6.QtWidgets.QApplication", _FakeApp)
    monkeypatch.setattr("dyntool_gui.main_window.MainWindow", _FakeWindow)

    result = app_module.main([])

    assert result == 0
    assert captured_window
    assert captured_window[0].session.demo_key == ""
    assert captured_window[0].session.project_name == "未命名 GUI 项目"


def test_app_main_supports_explicit_demo_argument(monkeypatch: pytest.MonkeyPatch) -> None:
    """显式 demo 参数仍应进入对应演示会话。"""

    from dyntool_gui import app as app_module

    class _FakeApp:
        @staticmethod
        def instance() -> None:
            return None

        def __init__(self, _args: object) -> None:
            pass

        def exec(self) -> int:
            return 0

    captured_window: list[MainWindow] = []

    class _FakeWindow:
        def __init__(self, session: ProjectSession) -> None:
            self.session = session
            captured_window.append(self)

        def show(self) -> None:
            return None

    monkeypatch.setattr(app_module, "ProjectSession", ProjectSession)
    monkeypatch.setattr("PySide6.QtWidgets.QApplication", _FakeApp)
    monkeypatch.setattr("dyntool_gui.main_window.MainWindow", _FakeWindow)

    result = app_module.main(["--demo", "generic"])

    assert result == 0
    assert captured_window
    assert captured_window[0].session.demo_key == "generic"
    assert captured_window[0].session.project_name == "通用样本项目骨架"
