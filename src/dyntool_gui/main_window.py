"""GUI 主窗口。"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QSize, QTimer, Qt, Slot
from PySide6.QtGui import QAction, QCloseEvent, QGuiApplication, QResizeEvent, QShowEvent
from PySide6.QtWidgets import (
    QFileDialog,
    QDockWidget,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QStatusBar,
    QStyle,
    QToolBar,
    QWidget,
)

from .facades import GuiImportFacade, ImportKind, ImportPreview, SampleBatchImportRequest, SampleSetImportRequest
from .import_runtime import ImportProgressUpdate
from .layout import WorkbenchLayoutProfile, resolve_workbench_layout_profile
from .managers import ExportManager, ImportManager, PlotManager, ProcessingManager
from .persistence import AppSettingsStore, ProjectFileStore
from .session import (
    ExportRecord,
    FilterSpec,
    ModuleKey,
    ProcessingPreviewRequestSnapshot,
    ProcessingRequestSnapshot,
    ProjectSession,
)
from .theme import ThemeManager
from .widgets import (
    BottomPanel,
    CodeReviewResultDialog,
    ExportPrecheckDialog,
    FigurePreviewDialog,
    HelpDialog,
    ImportPreviewDialog,
    LogDetailDialog,
    LongTaskProgressDialog,
    ModuleWorkspace,
    ResourceTreeWidget,
    ResultPreviewDialog,
    SettingsDialog,
    TableDialog,
)


class MainWindow(QMainWindow):
    """主窗口工作台。"""

    def __init__(
        self,
        session: ProjectSession | None = None,
        *,
        settings_store: AppSettingsStore | None = None,
        project_store: ProjectFileStore | None = None,
        theme_manager: ThemeManager | None = None,
    ) -> None:
        super().__init__()
        self.session = session or ProjectSession.build_empty()
        self.settings_store = settings_store or AppSettingsStore()
        self.project_store = project_store or ProjectFileStore()
        self.theme_manager = theme_manager or ThemeManager()
        self.import_facade = GuiImportFacade()
        self.import_manager = ImportManager(self.session, self)
        self.processing_manager = ProcessingManager(self.session, self)
        self.plot_manager = PlotManager(self.session, self)
        self.export_manager = ExportManager(self.session, self)
        self.actions_map: dict[str, QAction] = {}
        self._close_after_cleanup = False
        self._allow_close = False
        self._current_project_file: Path | None = None
        self._current_plot_figure = None
        self._pending_processing_request: ProcessingRequestSnapshot | None = None
        self._pending_plot_kwargs: dict[str, object] | None = None
        self._cached_import_preview: ImportPreview | None = None
        self._cached_import_fingerprint: tuple[object, ...] | None = None

        self.resize(*self._recommended_window_size())
        self.theme_manager.apply(self)
        self._build_actions()
        self._build_central_workspace()
        self._build_docks()
        self._build_menus()
        self._build_status_bar()
        self._connect_signals()
        self.settings_store.restore_main_window(self)
        self._apply_default_screen_mode()
        self._load_settings_into_session()
        self._reload_view()
        self._apply_adaptive_layout(force=True)

    def _build_central_workspace(self) -> None:
        self.workspace = ModuleWorkspace(self)
        self.workspace.currentChanged.connect(self._on_module_changed)

        self._connect_overview_workspace()
        self._connect_import_workspace()
        self._connect_processing_workspace()
        self._connect_plotting_workspace()
        self._connect_export_workspace()

        self.setCentralWidget(self.workspace)

    def _connect_overview_workspace(self) -> None:
        self.workspace.project_overview.action_requested.connect(self._trigger_action)

    def _connect_import_workspace(self) -> None:
        workspace = self.workspace.import_filter_workspace
        workspace.import_kind_changed.connect(self._on_import_kind_changed)
        workspace.project_directory_requested.connect(self._select_project_directory)
        workspace.source_file_requested.connect(self._select_import_source_file)
        workspace.source_directory_requested.connect(self._select_import_source_directory)
        workspace.import_preview_requested.connect(self._preview_import)
        workspace.import_deep_check_requested.connect(self._deep_check_units)
        workspace.import_execute_requested.connect(self._execute_import)
        workspace.import_cancel_requested.connect(self._cancel_import_operation)
        workspace.subset_preview_requested.connect(self._preview_subset)
        workspace.subset_save_requested.connect(self._save_subset)
        workspace.subset_delete_requested.connect(self._delete_subset)
        workspace.subset_recalculate_requested.connect(self._recalculate_subset)
        workspace.subset_use_scope_requested.connect(self._use_subset_scope)
        workspace.subset_selection_requested.connect(self._select_subset)
        workspace.reset_scope_requested.connect(lambda: self._trigger_action("回到全部样本"))

    def _connect_processing_workspace(self) -> None:
        workspace = self.workspace.processing_workspace
        workspace.process_requested.connect(self._run_processing)
        workspace.preview_requested.connect(self._run_processing_preview)
        workspace.cancel_requested.connect(self._cancel_import_operation)

    def _connect_plotting_workspace(self) -> None:
        workspace = self.workspace.plotting_workspace
        workspace.plot_requested.connect(self._render_plot)
        workspace.save_requested.connect(self._save_plot)
        workspace.compute_required.connect(self._run_required_processing)

    def _connect_export_workspace(self) -> None:
        workspace = self.workspace.export_workspace
        workspace.export_requested.connect(self._run_export)
        workspace.compute_required.connect(self._run_required_processing)

    def _build_docks(self) -> None:
        self.resource_tree = ResourceTreeWidget(self)
        self.resource_tree.selection_changed.connect(self._on_selection_changed)
        self.bottom_panel = BottomPanel(self)

        self.left_dock = self._build_dock("对象树", self.resource_tree, Qt.DockWidgetArea.LeftDockWidgetArea)
        self.bottom_dock = self._build_dock("任务与记录", self.bottom_panel, Qt.DockWidgetArea.BottomDockWidgetArea)
        profile = self._current_layout_profile()
        self.left_dock.setMinimumWidth(profile.left_dock_min_width)
        self.left_dock.setMaximumWidth(profile.left_dock_max_width)
        self.bottom_dock.setMinimumHeight(profile.bottom_dock_min_height)

    def _build_dock(self, title: str, widget: QWidget, area: Qt.DockWidgetArea) -> QDockWidget:
        dock = QDockWidget(title, self)
        dock.setObjectName(title)
        dock.setWidget(widget)
        self.addDockWidget(area, dock)
        return dock

    def _build_actions(self) -> None:
        action_specs: tuple[tuple[str, Callable[[], None], str | None], ...] = (
            ("新建项目", self._new_project, "Ctrl+N"),
            ("打开项目", self._open_project_dialog, "Ctrl+O"),
            ("保存项目", self._save_project, "Ctrl+S"),
            ("导入与筛选", lambda: self._open_import_workflow(ImportKind.SAMPLE_SET), "Ctrl+I"),
            ("校验", self._validate_current_module, "F5"),
            ("执行", self._execute_current_module, "F6"),
            ("设置", self._open_settings_dialog, None),
            ("帮助", self._open_help_dialog, "F1"),
            ("关于", self._open_about_dialog, None),
            ("中止当前任务", self._cancel_import_operation, "Esc"),
            ("切换桥梁演示数据", lambda: self._switch_demo("bridge"), None),
            ("切换通用演示数据", lambda: self._switch_demo("generic"), None),
            ("切换到总览页", lambda: self._set_current_module(ModuleKey.PROJECT), None),
            ("切换到导入与筛选页", lambda: self._set_current_module(ModuleKey.IMPORT), None),
            ("切换到数据处理页", lambda: self._set_current_module(ModuleKey.PROCESSING), None),
            ("切换到图形绘制页", lambda: self._set_current_module(ModuleKey.PLOTTING), None),
        )
        for name, handler, shortcut in action_specs:
            action = QAction(name, self)
            if shortcut:
                action.setShortcut(shortcut)
            action.triggered.connect(handler)
            icon = self._action_icon(name)
            if icon is not None:
                action.setIcon(icon)
            self.actions_map[name] = action
        self._update_action_states()

    def _action_icon(self, action_name: str):
        style = self.style()
        icon_map = {
            "新建项目": style.standardIcon(QStyle.StandardPixmap.SP_FileIcon),
            "打开项目": style.standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton),
            "保存项目": style.standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton),
            "导入与筛选": style.standardIcon(QStyle.StandardPixmap.SP_ArrowDown),
            "校验": style.standardIcon(QStyle.StandardPixmap.SP_DialogApplyButton),
            "执行": style.standardIcon(QStyle.StandardPixmap.SP_MediaPlay),
            "设置": style.standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView),
            "帮助": style.standardIcon(QStyle.StandardPixmap.SP_MessageBoxQuestion),
            "关于": style.standardIcon(QStyle.StandardPixmap.SP_TitleBarMenuButton),
            "中止当前任务": style.standardIcon(QStyle.StandardPixmap.SP_BrowserStop),
            "切换桥梁演示数据": style.standardIcon(QStyle.StandardPixmap.SP_DirIcon),
            "切换通用演示数据": style.standardIcon(QStyle.StandardPixmap.SP_DirIcon),
            "切换到总览页": style.standardIcon(QStyle.StandardPixmap.SP_DirHomeIcon),
            "切换到导入与筛选页": style.standardIcon(QStyle.StandardPixmap.SP_DirOpenIcon),
            "切换到数据处理页": style.standardIcon(QStyle.StandardPixmap.SP_CommandLink),
            "切换到图形绘制页": style.standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView),
        }
        return icon_map.get(action_name)

    def _build_menus(self) -> None:
        file_menu = self.menuBar().addMenu("文件")
        for name in ("新建项目", "打开项目", "保存项目"):
            file_menu.addAction(self.actions_map[name])
        file_menu.addSeparator()
        exit_action = QAction("退出", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        view_menu = self.menuBar().addMenu("视图")
        for dock in (self.left_dock, self.bottom_dock):
            view_menu.addAction(dock.toggleViewAction())
        restore_action = QAction("恢复默认布局", self)
        restore_action.triggered.connect(self._restore_default_layout)
        view_menu.addAction(restore_action)

        data_menu = self.menuBar().addMenu("数据")
        data_menu.addAction(self.actions_map["导入与筛选"])
        data_menu.addAction(self.actions_map["切换桥梁演示数据"])
        data_menu.addAction(self.actions_map["切换通用演示数据"])

        page_menu = self.menuBar().addMenu("页面")
        for name in (
            "切换到总览页",
            "切换到导入与筛选页",
            "切换到数据处理页",
            "切换到图形绘制页",
        ):
            page_menu.addAction(self.actions_map[name])

        tools_menu = self.menuBar().addMenu("工具")
        tools_menu.addAction(self.actions_map["校验"])
        tools_menu.addAction(self.actions_map["执行"])
        tools_menu.addAction(self.actions_map["中止当前任务"])
        log_action = QAction("查看日志详情", self)
        log_action.triggered.connect(lambda: LogDetailDialog(self.session, self).exec())
        tools_menu.addAction(log_action)
        progress_action = QAction("打开长任务进度", self)
        progress_action.triggered.connect(
            lambda: LongTaskProgressDialog(self.session, self._cancel_import_operation, self).exec()
        )
        tools_menu.addAction(progress_action)

        help_menu = self.menuBar().addMenu("帮助")
        help_menu.addAction(self.actions_map["帮助"])
        help_menu.addAction(self.actions_map["关于"])

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("主工具栏", self)
        toolbar.setObjectName("MainToolBar")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(20, 20))
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)

        for action_name in ("新建项目", "打开项目", "保存项目"):
            act = self.actions_map.get(action_name)
            if act is not None:
                toolbar.addAction(act)

        toolbar.addSeparator()

        for action_name in ("设置", "帮助", "关于"):
            act = self.actions_map.get(action_name)
            if act is not None:
                toolbar.addAction(act)

        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar)

    def _build_status_bar(self) -> None:
        status = QStatusBar(self)
        self.setStatusBar(status)
        self._status_project = QLabel()
        self._status_sampleset = QLabel()
        self._status_dirty = QLabel()
        self._status_task = QLabel()
        self._status_progress = QProgressBar()
        self._status_progress.setObjectName("GlobalTaskProgressBar")
        self._status_progress.setTextVisible(False)
        self._status_progress.setFixedWidth(140)
        self._status_progress.hide()
        status.addWidget(self._status_project, 1)
        status.addWidget(self._status_sampleset, 1)
        status.addPermanentWidget(self._status_task)
        status.addPermanentWidget(self._status_progress)
        status.addPermanentWidget(self._status_dirty)

    def _connect_signals(self) -> None:
        bus = self.session.bus
        bus.project_changed.connect(self._refresh_window_context)
        bus.primary_changed.connect(self._refresh_primary_summary)
        bus.import_state_changed.connect(self._refresh_import_views)
        bus.resource_tree_changed.connect(self._refresh_resource_tree)
        bus.task_changed.connect(self._refresh_bottom_tasks)
        bus.logs_changed.connect(self._refresh_bottom_logs)
        bus.issues_changed.connect(self._refresh_bottom_issues)
        bus.subset_state_changed.connect(self._refresh_subset_views)
        bus.processing_state_changed.connect(self._refresh_processing_views)
        bus.plot_state_changed.connect(self._refresh_plot_views)
        bus.export_state_changed.connect(self._refresh_export_views)
        self.import_manager.progress.connect(self._handle_import_progress)
        self.import_manager.succeeded.connect(self._handle_import_success)
        self.import_manager.failed.connect(self._handle_import_failure)
        self.import_manager.state_changed.connect(self._update_action_states)
        self.processing_manager.succeeded.connect(self._handle_processing_success)
        self.processing_manager.failed.connect(self._handle_processing_failure)
        self.processing_manager.state_changed.connect(self._update_action_states)
        self.plot_manager.succeeded.connect(self._handle_plot_success)
        self.plot_manager.failed.connect(self._handle_plot_failure)
        self.plot_manager.state_changed.connect(self._update_action_states)
        self.export_manager.succeeded.connect(self._handle_export_success)
        self.export_manager.failed.connect(self._handle_export_failure)
        self.export_manager.state_changed.connect(self._update_action_states)

    def _load_settings_into_session(self) -> None:
        preferences = self.settings_store.load_preferences()
        if preferences["recent_sample_dir"]:
            self.session.import_state.recent_sample_source_dir = Path(preferences["recent_sample_dir"]).resolve()
        if preferences["recent_sampleset_dir"]:
            self.session.import_state.recent_sampleset_source_dir = Path(preferences["recent_sampleset_dir"]).resolve()

    def _save_settings_from_session(self) -> None:
        preferences = self.settings_store.load_preferences()
        recent_projects = preferences.get("recent_projects", [])
        if self._current_project_file is not None:
            project_path = str(self._current_project_file)
            recent_projects = [project_path] + [item for item in recent_projects if item != project_path]
        self.settings_store.save_preferences(
            {
                "theme_name": self.theme_manager.theme_name,
                "recent_projects": recent_projects[:5],
                "recent_sample_dir": ""
                if self.session.import_state.recent_sample_source_dir is None
                else str(self.session.import_state.recent_sample_source_dir),
                "recent_sampleset_dir": ""
                if self.session.import_state.recent_sampleset_source_dir is None
                else str(self.session.import_state.recent_sampleset_source_dir),
            }
        )

    def _reload_view(self) -> None:
        self._refresh_window_context()
        self._refresh_workspace()
        self._refresh_resource_tree()
        self._refresh_bottom_panel()

    @Slot()
    def _refresh_window_context(self) -> None:
        self.setWindowTitle(f"AdvDynTool GUI - {self.session.project_name}")
        self.workspace.set_current_module(self.session.current_module)
        self._sync_import_focus()
        self._status_project.setText(f"项目：{self.session.project_name}")
        self._status_sampleset.setText(f"主样本集：{self.session.primary_sampleset.name}")
        self._status_task.setText(f"当前任务：{self._active_status_text()}")
        self._status_dirty.setText("未保存修改" if self.session.dirty else "已保存")
        self._sync_status_progress()
        self.workspace.update_context(
            self.session.project_name,
            self.session.primary_sampleset.name,
            self.session.dirty,
        )

    def _active_status_text(self) -> str:
        if self.session.import_state.busy:
            return self.session.import_state.progress_text
        if self.processing_manager.busy:
            return "处理进行中…"
        if self.plot_manager.busy:
            return "绘图进行中…"
        if self.export_manager.busy:
            return "导出进行中…"
        if self.session.tasks:
            return self.session.tasks[0].status
        return "就绪"

    def _sync_status_progress(self) -> None:
        """同步状态栏中的全局长任务进度。"""

        if self.session.import_state.busy:
            state = self.session.import_state
            if state.progress_total not in {None, 0}:
                self._status_progress.setRange(0, state.progress_total or 0)
                self._status_progress.setValue(state.progress_current or 0)
            else:
                self._status_progress.setRange(0, 0)
            self._status_progress.show()
            return
        if self.processing_manager.busy or self.plot_manager.busy or self.export_manager.busy:
            self._status_progress.setRange(0, 0)
            self._status_progress.show()
            return
        self._status_progress.hide()

    @Slot()
    def _refresh_primary_summary(self) -> None:
        self.workspace.project_overview.load_session(self.session)
        self._refresh_window_context()
        self._refresh_resource_tree()

    @Slot()
    def _refresh_workspace(self) -> None:
        self.workspace.load_session(self.session)

    @Slot()
    def _refresh_import_views(self) -> None:
        self.workspace.import_workflow.load_session(self.session)
        if self.session.current_module is ModuleKey.IMPORT:
            self._refresh_bottom_panel()
        else:
            self._refresh_bottom_tasks()
        self._refresh_window_context()

    @Slot()
    def _refresh_subset_views(self) -> None:
        self.workspace.subset_workspace.load_session(self.session)
        if self.session.current_module is ModuleKey.SUBSET:
            self._refresh_bottom_panel()
        self._refresh_window_context()

    @Slot()
    def _refresh_processing_views(self) -> None:
        self.workspace.processing_workspace.load_session(self.session)
        if self.session.current_module is ModuleKey.PROCESSING:
            self._refresh_bottom_panel()
        self._refresh_window_context()

    @Slot()
    def _refresh_plot_views(self) -> None:
        self.workspace.plotting_workspace.load_session(self.session)
        if self.session.current_module is ModuleKey.PLOTTING:
            self._refresh_bottom_panel()
        self._refresh_window_context()

    @Slot()
    def _refresh_export_views(self) -> None:
        self.workspace.export_workspace.load_session(self.session)
        if self.session.current_module is ModuleKey.EXPORT:
            self._refresh_bottom_panel()
        self._refresh_window_context()

    @Slot()
    def _refresh_resource_tree(self) -> None:
        self.resource_tree.load_session(self.session)

    @Slot()
    def _refresh_bottom_panel(self) -> None:
        self.bottom_panel.load_session(self.session)

    @Slot()
    def _refresh_bottom_tasks(self) -> None:
        self.bottom_panel.load_task_rows(self.session)

    @Slot()
    def _refresh_bottom_logs(self) -> None:
        self.bottom_panel.load_log_rows(self.session)

    @Slot()
    def _refresh_bottom_issues(self) -> None:
        self.bottom_panel.load_issue_rows(self.session)

    def _sync_import_focus(self) -> None:
        show_left = self.session.current_module is not ModuleKey.PROJECT
        self.left_dock.setVisible(show_left)
        self.bottom_dock.setVisible(True)
        self._apply_adaptive_layout()

    def _set_current_module(self, module: ModuleKey) -> None:
        self.session.set_current_module(module)
        self.workspace.set_current_module(module)

    def _open_import_workflow(self, import_kind: ImportKind) -> None:
        self.session.reset_for_import(import_kind)
        self.workspace.set_import_kind(import_kind)
        self.workspace.set_current_module(ModuleKey.IMPORT)
        self._refresh_workspace()
        self._refresh_window_context()
        if not self.isVisible():
            self.show()

    def _new_project(self) -> None:
        if self._is_busy():
            QMessageBox.warning(self, "无法新建项目", "当前有任务正在运行，请等待完成或先中止任务。")
            return
        self.session.switch_demo("generic")
        self._current_project_file = None
        self.session.mark_saved()

    def _open_project_dialog(self) -> None:
        if self._is_busy():
            QMessageBox.warning(self, "无法打开项目", "当前有任务正在运行，请等待完成或先中止任务。")
            return
        path, _ = QFileDialog.getOpenFileName(
            self,
            "打开项目文件",
            str(self.session.workdir),
            "AdvDynTool 项目文件 (*.dyntool.json *.json)",
        )
        if path:
            self._load_project_from_file(path)

    def _load_project_from_file(self, path: str | Path) -> None:
        if self._is_busy():
            QMessageBox.warning(self, "无法加载项目", "当前有任务正在运行，请等待完成或先中止任务。")
            return
        self.session = self.project_store.load(path)
        self._current_project_file = Path(path).resolve()
        self.import_manager.deleteLater()
        self.processing_manager.deleteLater()
        self.plot_manager.deleteLater()
        self.export_manager.deleteLater()
        self.import_manager = ImportManager(self.session, self)
        self.processing_manager = ProcessingManager(self.session, self)
        self.plot_manager = PlotManager(self.session, self)
        self.export_manager = ExportManager(self.session, self)
        self._connect_signals()
        self._reload_view()

    def _save_project(self) -> None:
        if self._is_busy():
            QMessageBox.warning(self, "无法保存项目", "当前有任务正在运行，请等待完成或先中止任务。")
            return
        if self._current_project_file is None:
            default_path = self.session.workdir / f"{self.session.workdir.name}.dyntool.json"
            self._current_project_file = self.project_store.save(self.session, default_path)
        else:
            self.project_store.save(self.session, self._current_project_file)
        self.session.mark_saved()
        self._save_settings_from_session()
        self.statusBar().showMessage("项目文件已保存。", 3000)

    def _on_module_changed(self, _: int) -> None:
        self.session.set_current_module(self.workspace.current_module())
        self._refresh_resource_tree()
        self._refresh_bottom_panel()

    def _on_selection_changed(self, text: str) -> None:
        self.session.set_current_selection(text)

    def _on_import_kind_changed(self, kind_value: str) -> None:
        self.session.reset_for_import(ImportKind(kind_value))

    def _validate_current_module(self) -> None:
        module = self.workspace.current_module()
        try:
            if module is ModuleKey.IMPORT:
                self._preview_import()
                return
            if module is ModuleKey.SUBSET:
                self._preview_subset(self.workspace.subset_workspace.scope_editor_values())
                return
            if module is ModuleKey.PROCESSING:
                self._run_processing_preview(self.workspace.processing_workspace.preview_request_values())
                return
            if module is ModuleKey.PLOTTING:
                QMessageBox.information(
                    self, "图形校验", "图形页采用显式渲染模式，请确认来源、范围和样本选择后执行“渲染”。"
                )
                return
            if module is ModuleKey.EXPORT:
                export_kind, output_path, data_var, source = self.workspace.export_workspace.validation_request_values()
                self._ensure_primary_runtime()
                self._sync_scope_from_widgets(ModuleKey.EXPORT)
                self.export_manager.validate_sync(
                    export_kind=export_kind,
                    output_path=output_path,
                    data_var=data_var,
                    source=source,
                )
                self._refresh_export_views()
                return
            QMessageBox.information(
                self, "总览校验", "当前项目上下文已加载，可直接进入导入与筛选、数据处理或图形绘制页执行任务。"
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "校验失败", str(exc))

    def _execute_current_module(self) -> None:
        module = self.workspace.current_module()
        try:
            if module is ModuleKey.IMPORT:
                self._execute_import()
                return
            if module is ModuleKey.SUBSET:
                subset_widget = self.workspace.subset_workspace
                subset_id = subset_widget.selected_subset_id()
                if subset_id:
                    self._use_subset_scope(subset_id)
                    return
                self._preview_subset(subset_widget.scope_editor_values())
                subset_name, note = subset_widget.save_editor_values()
                self._save_subset(subset_name, note, False)
                return
            if module is ModuleKey.PROCESSING:
                self._run_processing(self.workspace.processing_workspace.processing_request_values())
                return
            if module is ModuleKey.PLOTTING:
                self._render_plot()
                return
            if module is ModuleKey.EXPORT:
                self._run_export(*self.workspace.export_workspace.export_request_values())
                return
            self._open_import_workflow(ImportKind.SAMPLE_SET)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "执行失败", str(exc))

    def _open_settings_dialog(self) -> None:
        SettingsDialog(self.session, self.settings_store, self.theme_manager.theme_name, self).exec()

    def _open_help_dialog(self) -> None:
        HelpDialog(self).exec()

    def _open_about_dialog(self) -> None:
        QMessageBox.about(
            self,
            "关于 AdvDynTool GUI",
            "AdvDynTool GUI\nPySide6 Widgets 工作台原型\n当前版本聚焦主样本集、子样本集与任务工作台统一。",
        )

    def _select_project_directory(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "选择项目目录", str(self.session.workdir))
        if not directory:
            return
        self.session.set_project_directory(directory)
        self.workspace.import_workflow.set_project_directory(directory)

    def _select_import_source_file(self) -> None:
        workflow = self.workspace.import_workflow
        start_dir = str(self.session.get_import_start_directory(workflow.import_kind))
        if workflow.import_kind is ImportKind.SAMPLE:
            paths, _ = QFileDialog.getOpenFileNames(self, "选择 CSV 样本", start_dir, "CSV 文件 (*.csv)")
            if not paths:
                return
            self.session.set_import_sources(paths)
            self.workspace.import_workflow.set_sample_batch_paths(paths)
        else:
            path, _ = QFileDialog.getOpenFileName(
                self,
                "选择样本集文件",
                start_dir,
                "H5 文件 (*.h5 *.hdf5);;所有文件 (*.*)",
            )
            if not path:
                return
            self.session.set_import_source(path)
            self.workspace.import_workflow.set_source_path(path)

    def _select_import_source_directory(self) -> None:
        workflow = self.workspace.import_workflow
        start_dir = str(self.session.get_import_start_directory(workflow.import_kind))
        directory = QFileDialog.getExistingDirectory(self, "选择来源目录", start_dir)
        if not directory:
            return
        self.session.set_import_source(directory)
        self.workspace.import_workflow.set_source_path(directory)

    def _ensure_import_ready(self, *, require_preview: bool) -> None:
        if self.session.import_state.busy:
            raise ValueError("当前已有导入任务正在进行。")
        self._sync_session_from_import_widget()
        if not self.session.import_state.project_directory_selected:
            raise ValueError("请先选择项目目录。")
        if not self.session.import_state.has_import_source:
            raise ValueError("请先选择导入来源路径。")
        if require_preview and not self.session.import_state.preview_lines:
            raise ValueError("请先执行轻量预览。")

    def _preview_import(self) -> None:
        try:
            self._ensure_import_ready(require_preview=False)
            title = "预览样本" if self.workspace.import_workflow.import_kind is ImportKind.SAMPLE else "预览样本集"
            detail = (
                "正在检查批量 CSV 文件与整批单位。"
                if self.workspace.import_workflow.import_kind is ImportKind.SAMPLE
                else "正在执行样本集轻量检查。"
            )
            self.import_manager.start_operation(
                task_title=title,
                detail=detail,
                mode="preview",
                operation=self._build_preview_operation(),
            )
        except Exception as exc:  # noqa: BLE001
            self.session.apply_import_error(self._current_import_task_title(), str(exc))
            QMessageBox.warning(self, "导入预览失败", str(exc))

    def _deep_check_units(self) -> None:
        try:
            self._ensure_import_ready(require_preview=True)
            if self.workspace.import_workflow.import_kind is not ImportKind.SAMPLE_SET:
                raise ValueError("深度检查单位仅支持样本集导入。")
            self.import_manager.start_operation(
                task_title="深度检查单位",
                detail="正在按数据分类读取原始数据并汇总单位。",
                mode="deep_check",
                operation=self._build_deep_check_operation(),
            )
        except Exception as exc:  # noqa: BLE001
            self.session.apply_import_error("深度检查单位", str(exc))
            QMessageBox.warning(self, "深度检查失败", str(exc))

    def _execute_import(self) -> None:
        try:
            self._ensure_import_ready(require_preview=True)
            title = "导入样本" if self.workspace.import_workflow.import_kind is ImportKind.SAMPLE else "导入样本集"
            detail = (
                "正在读取 CSV 并组装新的主样本集。"
                if self.workspace.import_workflow.import_kind is ImportKind.SAMPLE
                else "正在加载样本集并刷新主集摘要。"
            )
            self.import_manager.start_operation(
                task_title=title,
                detail=detail,
                mode="execute",
                operation=self._build_execute_operation(),
            )
        except Exception as exc:  # noqa: BLE001
            self.session.apply_import_error(self._current_import_task_title(), str(exc))
            QMessageBox.warning(self, "执行导入失败", str(exc))

    def _build_preview_operation(self) -> Callable[[object], object]:
        if self.workspace.import_workflow.import_kind is ImportKind.SAMPLE:
            request = SampleBatchImportRequest(
                source_paths=self.session.import_state.sample_batch_paths,
                source_directory=self.session.import_state.source_path,
                csv_read_options=self.session.import_state.csv_read_options,
            )
            return lambda controller: self.import_facade.preview_sample_csv_batch(request, controller=controller)

        request = SampleSetImportRequest(
            source_path=self.session.import_state.source_path,
            requested_scheme=self.session.import_state.requested_scheme,
            load_mode=self.session.import_state.load_mode,
            workers=self.session.import_state.workers,
            strict=self.session.import_state.strict,
        )
        return lambda controller: self.import_facade.preview_sample_set_repository_light(
            request, controller=controller, keep_runtime=True
        )

    def _build_deep_check_operation(self) -> Callable[[object], object]:
        request = SampleSetImportRequest(
            source_path=self.session.import_state.source_path,
            requested_scheme=self.session.import_state.requested_scheme,
            load_mode=self.session.import_state.load_mode,
            workers=self.session.import_state.workers,
            strict=self.session.import_state.strict,
        )
        return lambda controller: self.import_facade.preview_sample_set_repository_deep_units(
            request, controller=controller
        )

    def _build_execute_operation(self) -> Callable[[object], object]:
        if self.workspace.import_workflow.import_kind is ImportKind.SAMPLE:
            request = SampleBatchImportRequest(
                source_paths=self.session.import_state.sample_batch_paths,
                source_directory=self.session.import_state.source_path,
                csv_read_options=self.session.import_state.csv_read_options,
            )
            return lambda controller: self.import_facade.execute_sample_csv_batch(request, controller=controller)

        request = SampleSetImportRequest(
            source_path=self.session.import_state.source_path,
            requested_scheme=self.session.import_state.requested_scheme,
            load_mode=self.session.import_state.load_mode,
            workers=self.session.import_state.workers,
            strict=self.session.import_state.strict,
        )
        cached_preview = self._cached_import_preview
        if (
            cached_preview is not None
            and self._cached_import_fingerprint == self._current_import_fingerprint()
            and cached_preview.prepared_runtime is not None
        ):
            return lambda controller: self.import_facade.execute_sample_set_repository_from_preview(
                request, cached_preview, controller=controller
            )
        return lambda controller: self.import_facade.execute_sample_set_repository(request, controller=controller)

    def _current_import_fingerprint(self) -> tuple[object, ...]:
        state = self.session.import_state
        source_path = state.source_path.resolve() if state.source_path is not None else None
        requested_scheme = state.requested_scheme.value if state.requested_scheme is not None else ""
        csv_options = tuple(sorted((key, str(value)) for key, value in state.csv_read_options.items()))
        return (
            state.import_kind.value,
            source_path,
            tuple(path.resolve() for path in state.sample_batch_paths),
            requested_scheme,
            state.load_mode.value,
            state.workers,
            state.strict,
            csv_options,
        )

    @Slot(object)
    def _handle_import_progress(self, payload: object) -> None:
        if isinstance(payload, ImportProgressUpdate):
            self.statusBar().showMessage(payload.progress_prefix, 1200)

    @Slot(object)
    def _handle_import_success(self, payload: object) -> None:
        if self.import_manager.mode in {"preview", "deep_check"}:
            if self.import_manager.mode == "preview" and isinstance(payload, ImportPreview):
                self._cached_import_preview = payload
                self._cached_import_fingerprint = self._current_import_fingerprint()
            self.session.apply_import_preview(payload)
        elif self.import_manager.mode in {"execute", "restore_runtime"}:
            self._cached_import_preview = None
            self._cached_import_fingerprint = None
            task_title = self.import_manager.task_title or getattr(payload, "task_title", "导入样本集")
            self.session.begin_import_finalization(str(task_title))
            self._update_action_states()
            self.statusBar().showMessage("正在刷新主集摘要，界面会在完成后自动恢复。", 1500)
            QTimer.singleShot(0, lambda payload=payload: self._finalize_import_success(payload))

    def _finalize_import_success(self, payload: object) -> None:
        """在事件循环下一轮写回导入结果，让收尾进度先刷新到界面。"""

        try:
            self.session.apply_import_result(payload)
            self._resume_processing_after_runtime_restore()
            self._resume_plot_after_runtime_restore()
        except Exception as exc:  # noqa: BLE001
            task_title = str(getattr(payload, "task_title", "导入样本集"))
            self.session.apply_import_error(task_title, str(exc))
            self._pending_processing_request = None
            self._pending_plot_kwargs = None
            QMessageBox.warning(self, "执行导入失败", str(exc))
        finally:
            self._update_action_states()
        if self._close_after_cleanup and not self.session.import_state.busy:
            self._allow_close = True
            self.session.clear_close_guard()
            self.close()

    @Slot(str, bool)
    def _handle_import_failure(self, message: str, cancelled: bool) -> None:
        task_title = self.import_manager.task_title or self._current_import_task_title()
        if self.import_manager.mode == "restore_runtime":
            self._pending_processing_request = None
        if cancelled:
            self.session.apply_import_cancel(task_title, message, cleanup_message="已安全释放导入线程和临时对象。")
        else:
            self.session.apply_import_error(task_title, message)
            dialog_title = "导入预览失败" if self.import_manager.mode in {"preview", "deep_check"} else "执行导入失败"
            QMessageBox.warning(self, dialog_title, message)
        if self._close_after_cleanup and not self.session.import_state.busy:
            self._allow_close = True
            self.session.clear_close_guard()
            self.close()

    def _cancel_import_operation(self) -> None:
        if self.session.import_state.busy:
            self.import_manager.request_cancel()
            return
        if self.processing_manager.busy:
            self.processing_manager.request_cancel()

    def _sync_session_from_import_widget(self) -> None:
        workflow = self.workspace.import_workflow
        self.session.import_state.csv_sep = str(workflow.csv_read_options["sep"])
        self.session.import_state.csv_header = str(workflow.csv_read_options["header"])
        self.session.import_state.csv_index_col = str(workflow.csv_read_options["index_col"])
        self.session.import_state.csv_encoding = str(workflow.csv_read_options["encoding"])
        self.session.import_state.csv_skiprows = str(workflow.csv_read_options["skiprows"])
        self.session.import_state.csv_decimal = str(workflow.csv_read_options["decimal"])
        self.session.import_state.advanced_expanded = workflow.advanced_expanded
        self.session.import_state.requested_scheme = workflow.requested_scheme
        self.session.import_state.load_mode = workflow.load_mode
        self.session.import_state.workers = workflow.workers
        self.session.import_state.strict = workflow.strict
        if workflow.import_kind is ImportKind.SAMPLE and workflow.sample_batch_paths:
            if self.session.import_state.sample_batch_paths != workflow.sample_batch_paths:
                self.session.set_import_sources(workflow.sample_batch_paths)
            return
        if (
            self.session.import_state.source_path != workflow.source_path
            or self.session.import_state.sample_batch_paths
        ):
            self.session.set_import_source(workflow.source_path)

    def _sync_scope_from_widgets(self, module: ModuleKey) -> None:
        scope_kind, target_text = self._scope_selection_from_workspace(module)
        self._set_session_scope(scope_kind, target_text)

    def _scope_selection_from_workspace(self, module: ModuleKey) -> tuple[str, str]:
        if module is ModuleKey.PROCESSING:
            return self.workspace.processing_workspace.scope_selection()
        if module is ModuleKey.PLOTTING:
            return self.workspace.plotting_workspace.scope_selection()
        if module is ModuleKey.EXPORT:
            return self.workspace.export_workspace.scope_selection()
        return ("all_samples", "")

    def _set_session_scope(self, scope_kind: str, target_text: str = "") -> None:
        subset_ids, sample_uids = self._scope_targets(scope_kind, target_text)
        self.session.set_current_scope(scope_kind, subset_ids=subset_ids, sample_uids=sample_uids)

    def _scope_targets(self, scope_kind: str, target_text: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
        if scope_kind == "saved_subset":
            return ((target_text,) if target_text else (), ())
        if scope_kind == "multi_subset_union":
            return (tuple(item.strip() for item in target_text.split(",") if item.strip()), ())
        if scope_kind in {"temporary_selection", "single_sample"}:
            return ((), tuple(item.strip() for item in target_text.split(",") if item.strip()))
        return ((), ())

    def _current_import_task_title(self) -> str:
        if self.import_manager.mode == "deep_check":
            return "深度检查单位"
        return "批量导入样本" if self.workspace.import_workflow.import_kind is ImportKind.SAMPLE else "导入样本集"

    @Slot(str, str, bool)
    def _save_subset(self, name: str, note: str, freeze: bool) -> None:
        try:
            target_name = name.strip() or f"子样本集 {len(self.session.subset_state.subsets) + 1}"
            self.session.save_subset_definition(name=target_name, note=note.strip(), freeze=freeze)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "保存子样本集失败", str(exc))

    @Slot(str)
    def _delete_subset(self, subset_id: str) -> None:
        self.session.delete_subset_definition(subset_id)

    @Slot(str)
    def _recalculate_subset(self, subset_id: str) -> None:
        try:
            self._ensure_primary_runtime()
            self.session.recalculate_subset_definition(subset_id)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "重算子样本集失败", str(exc))

    @Slot(str)
    def _use_subset_scope(self, subset_id: str) -> None:
        self.session.set_current_scope("saved_subset", subset_ids=(subset_id,), note="当前子样本集")
        self.session.current_module = ModuleKey.PROCESSING
        self.workspace.processing_workspace.load_session(self.session)
        self._set_current_module(ModuleKey.PROCESSING)
        self._refresh_window_context()

    @Slot(str)
    def _select_subset(self, subset_id: str) -> None:
        self.session.select_subset_definition(subset_id)

    @Slot(object)
    def _preview_subset(self, filter_spec: object) -> None:
        try:
            self._ensure_primary_runtime()
            if not isinstance(filter_spec, FilterSpec):
                raise ValueError("筛选条件无效。")
            self.session.preview_subset(filter_spec)
        except Exception as exc:  # noqa: BLE001
            self.session.subset_state.last_failure_message = str(exc)
            self.session.bus.subset_state_changed.emit()
            QMessageBox.warning(self, "筛选失败", str(exc))

    @Slot(object)
    def _run_processing(self, request: object) -> None:
        try:
            self._ensure_write_task_available()
            if not isinstance(request, ProcessingRequestSnapshot):
                raise ValueError("处理请求无效。")
            self._apply_processing_scope(request)
            if self.session.primary_runtime is None:
                self._start_processing_runtime_restore(request)
                return
            self.processing_manager.start_action(request=request)
        except Exception as exc:  # noqa: BLE001
            self._report_processing_precheck_failure(str(exc))

    @Slot(object)
    def _run_processing_preview(self, request: object) -> None:
        try:
            self._ensure_primary_runtime()
            if not isinstance(request, ProcessingPreviewRequestSnapshot):
                raise ValueError("预览请求无效。")
            self._sync_scope_from_widgets(ModuleKey.PROCESSING)
            self.processing_manager.start_preview(
                preview_kind=request.preview_kind,
                preview_scope=request.preview_scope,
                uids_text=request.uids_text,
                metadata_fields=request.metadata_fields,
                features=request.features,
                data_var=request.data_var,
                peak_source=request.peak_source,
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "生成预览表失败", str(exc))

    @Slot(str)
    def _run_required_processing(self, action_name: str) -> None:
        self._run_processing(
            ProcessingRequestSnapshot(
                action_name=action_name,
                scope_kind=self.session.current_scope.scope_kind,
                strict=True,
                overwrite=True,
            )
        )

    def _apply_processing_scope(self, request: ProcessingRequestSnapshot) -> None:
        self._set_session_scope(request.scope_kind, request.scope_target)

    @Slot(object)
    def _handle_processing_success(self, _: object) -> None:
        self._refresh_processing_views()
        self._refresh_window_context()

    @Slot(str)
    def _handle_processing_failure(self, message: str) -> None:
        self.session.processing_state.last_failure_message = message
        self.session.bus.processing_state_changed.emit()
        self.session._prepend_issue("失败", "处理当前主样本集", message)
        self.session.bus.issues_changed.emit()
        QMessageBox.warning(self, "处理失败", message)

    def _report_processing_precheck_failure(self, message: str) -> None:
        self.session.processing_state.last_failure_message = message
        self.session.bus.processing_state_changed.emit()
        self.session._prepend_issue("失败", "处理前置校验", message)
        self.session.bus.issues_changed.emit()
        self._refresh_bottom_panel()
        QMessageBox.warning(self, "处理失败", message)

    @Slot()
    def _render_plot(self) -> None:
        try:
            if self.session.primary_runtime is None:
                self._start_plot_runtime_restore()
                return
            self._sync_scope_from_widgets(ModuleKey.PLOTTING)
            self.plot_manager.start(**self.workspace.plotting_workspace.plot_request_values())
        except Exception as exc:  # noqa: BLE001
            self.session.plot_state.last_failure_message = str(exc)
            self.session.set_plot_message(message="绘图失败。", missing_reason=str(exc))

    @Slot(object)
    def _handle_plot_success(self, payload: object) -> None:
        figure = getattr(payload, "figure", None)
        if figure is not None:
            self._current_plot_figure = figure
            self.workspace.plotting_workspace.set_figure(figure)
        self._refresh_plot_views()

    @Slot(str)
    def _handle_plot_failure(self, message: str) -> None:
        self.session.plot_state.last_failure_message = message
        self.session.set_plot_message(message="绘图失败。", missing_reason=message)
        self.session.add_issue("绘图失败", "图形绘制", message)
        QMessageBox.warning(self, "绘图失败", message)

    @Slot(str)
    def _save_plot(self, format_name: str) -> None:
        if self._current_plot_figure is None:
            QMessageBox.warning(self, "保存图片失败", "当前还没有可保存的图像。")
            return
        default_dir = self.session.export_dir / "plots"
        default_dir.mkdir(parents=True, exist_ok=True)
        path, _ = QFileDialog.getSaveFileName(
            self,
            "保存图片",
            str(default_dir / f"plot.{format_name}"),
            f"{format_name.upper()} 文件 (*.{format_name})",
        )
        if not path:
            return
        self.plot_manager.save_figure(self._current_plot_figure, path)
        self._refresh_plot_views()

    @Slot(str, str, str, object, object, str, str, bool, bool)
    def _run_export(
        self,
        export_kind: str,
        output_path: str,
        format_name: str,
        metadata_fields: object,
        features: object,
        data_var: str,
        source: str,
        include_plots: bool,
        include_eval_summary: bool,
    ) -> None:
        try:
            self._ensure_primary_runtime()
            self._sync_scope_from_widgets(ModuleKey.EXPORT)
            if export_kind == "current_plot_image":
                if self._current_plot_figure is None:
                    raise ValueError("当前还没有可导出的图形。")
                target_path = Path(output_path).resolve()
                if target_path.suffix == "":
                    target_path = target_path.with_suffix(f".{format_name}")
                self.plot_manager.save_figure(self._current_plot_figure, target_path)
                self.session.exports.insert(
                    0,
                    ExportRecord(
                        "当前图形",
                        str(target_path),
                        "成功",
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    ),
                )
                self.session.set_export_message(message="已导出当前图形。", output_path=str(target_path))
                self._refresh_export_views()
                self._refresh_bottom_panel()
                return
            self._ensure_write_task_available()
            validation = self.export_manager.validate_sync(
                export_kind=export_kind,
                output_path=output_path,
                data_var=data_var,
                source=source,
            )
            if not validation.valid:
                self._refresh_export_views()
                return
            self.export_manager.start(
                export_kind=export_kind,
                output_path=output_path,
                format_name=format_name,
                metadata_fields=tuple(metadata_fields) if isinstance(metadata_fields, tuple) else tuple(),
                features=tuple(features) if isinstance(features, tuple) else tuple(),
                data_var=data_var,
                source=source,
                include_plots=include_plots,
                include_eval_summary=include_eval_summary,
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "导出失败", str(exc))

    @Slot(object)
    def _handle_export_success(self, _: object) -> None:
        self._refresh_export_views()
        self._refresh_bottom_panel()

    @Slot(str)
    def _handle_export_failure(self, message: str) -> None:
        self.session.export_state.last_failure_message = message
        self.session.bus.export_state_changed.emit()
        self.session._prepend_issue("失败", "导出当前主样本集", message)
        self.session.bus.issues_changed.emit()

    def _ensure_primary_runtime(self) -> None:
        if self.session.primary_runtime is None:
            raise ValueError("当前主样本集还没有真实运行态对象，请先完成数据接入。")

    def _start_processing_runtime_restore(self, request: ProcessingRequestSnapshot) -> None:
        source_path = self.session.import_state.source_path
        if source_path is None:
            raise ValueError("当前主样本集还没有真实运行态对象，请先完成数据接入。")
        if self.session.import_state.import_kind is not ImportKind.SAMPLE_SET:
            raise ValueError("当前仅支持从样本集导入来源恢复主样本集运行态。")
        self._pending_processing_request = request
        restore_request = SampleSetImportRequest(
            source_path=source_path,
            requested_scheme=self.session.import_state.requested_scheme,
            load_mode=self.session.import_state.load_mode,
            workers=self.session.import_state.workers,
            strict=self.session.import_state.strict,
        )
        self.import_manager.start_operation(
            task_title="恢复主样本集运行态",
            detail="正在从当前导入来源恢复主样本集运行态，完成后会自动继续执行处理。",
            mode="restore_runtime",
            operation=lambda controller: self.import_facade.execute_sample_set_repository(
                restore_request,
                controller=controller,
            ),
        )

    def _resume_processing_after_runtime_restore(self) -> None:
        request = self._pending_processing_request
        if request is None:
            return
        self._pending_processing_request = None
        self.processing_manager.start_action(request=request)

    def _start_plot_runtime_restore(self) -> None:
        source_path = self.session.import_state.source_path
        if source_path is None:
            raise ValueError("当前主样本集还没有真实运行态对象，请先完成数据接入。")
        if self.session.import_state.import_kind is not ImportKind.SAMPLE_SET:
            raise ValueError("当前仅支持从样本集导入来源恢复主样本集运行态。")
        self._pending_plot_kwargs = self.workspace.plotting_workspace.plot_request_values()
        restore_request = SampleSetImportRequest(
            source_path=source_path,
            requested_scheme=self.session.import_state.requested_scheme,
            load_mode=self.session.import_state.load_mode,
            workers=self.session.import_state.workers,
            strict=self.session.import_state.strict,
        )
        self.import_manager.start_operation(
            task_title="恢复主样本集运行态",
            detail="正在从当前导入来源恢复主样本集运行态，完成后会自动继续渲染图形。",
            mode="restore_runtime",
            operation=lambda controller: self.import_facade.execute_sample_set_repository(
                restore_request,
                controller=controller,
            ),
        )

    def _resume_plot_after_runtime_restore(self) -> None:
        kwargs = self._pending_plot_kwargs
        if kwargs is None:
            return
        self._pending_plot_kwargs = None
        self._sync_scope_from_widgets(ModuleKey.PLOTTING)
        self.plot_manager.start(**kwargs)

    def _ensure_write_task_available(self) -> None:
        if self.session.import_state.busy or self.processing_manager.busy or self.export_manager.busy:
            raise ValueError("当前已有会写回主样本集的任务正在运行，请等待完成。")

    def _restore_default_layout(self) -> None:
        self.left_dock.show()
        self.bottom_dock.show()
        self.setWindowState(self.windowState() & ~Qt.WindowState.WindowMaximized)
        width, height = self._recommended_window_size()
        self.resize(width, height)
        self._apply_default_screen_mode()
        self._apply_adaptive_layout(force=True)
        self._set_current_module(ModuleKey.PROJECT)

    def _apply_default_screen_mode(self) -> None:
        """高分辨率屏幕默认以最大化进入工作台。"""

        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return
        available = screen.availableGeometry()
        if resolve_workbench_layout_profile(available.width(), available.height()).is_landscape:
            self.setWindowState(self.windowState() | Qt.WindowState.WindowMaximized)

    def resizeEvent(self, event: QResizeEvent) -> None:  # type: ignore[override]
        """窗口尺寸变化后同步收紧 dock 布局。"""

        super().resizeEvent(event)
        self._apply_adaptive_layout()

    def showEvent(self, event: QShowEvent) -> None:  # type: ignore[override]
        """窗口首次显示后再按真实布局收紧一次 dock。"""

        super().showEvent(event)
        QTimer.singleShot(0, lambda: self._apply_adaptive_layout(force=True))

    def _recommended_window_size(self) -> tuple[int, int]:
        """返回当前屏幕下更稳妥的默认窗口尺寸。"""

        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return (1720, 1040)
        available = screen.availableGeometry()
        width = max(1600, min(2200, int(available.width() * 0.86)))
        height = max(980, min(1280, int(available.height() * 0.85)))
        return (width, height)

    def _recommended_dock_sizes(self) -> tuple[int, int]:
        """返回当前窗口下推荐的对象树与底部任务区尺寸。"""

        profile = self._current_layout_profile()
        left_target = max(profile.left_dock_target_min, min(profile.left_dock_target_max, int(self.width() * 0.075)))
        bottom_target = max(
            profile.bottom_dock_target_min,
            min(profile.bottom_dock_target_max, int(self.height() * 0.08)),
        )
        return (left_target, bottom_target)

    def _current_layout_profile(self) -> WorkbenchLayoutProfile:
        """返回当前窗口或屏幕对应的工作台布局配置。"""

        width = self.width()
        height = self.height()
        if width <= 0 or height <= 0:
            screen = QGuiApplication.primaryScreen()
            if screen is not None:
                available = screen.availableGeometry()
                width = available.width()
                height = available.height()
        return resolve_workbench_layout_profile(width, height)

    def _apply_adaptive_layout(self, *, force: bool = False) -> None:
        """按当前分辨率收紧 dock 默认尺寸，避免不同屏幕下过度摊开。"""

        profile = self._current_layout_profile()
        self.left_dock.setMaximumWidth(profile.left_dock_max_width)
        self.left_dock.setMinimumWidth(profile.left_dock_min_width)
        self.bottom_dock.setMinimumHeight(profile.bottom_dock_min_height)
        left_target, bottom_target = self._recommended_dock_sizes()
        if force or self.left_dock.width() == 0 or self.left_dock.width() > left_target + 120:
            self.resizeDocks([self.left_dock], [left_target], Qt.Orientation.Horizontal)
        if force or self.bottom_dock.height() == 0 or self.bottom_dock.height() > bottom_target + 80:
            self.resizeDocks([self.bottom_dock], [bottom_target], Qt.Orientation.Vertical)

    def _switch_demo(self, demo_key: str) -> None:
        if self._is_busy():
            QMessageBox.warning(self, "无法切换演示数据", "当前有任务正在运行，请等待完成或先中止任务。")
            return
        self.session.switch_demo(demo_key)

    def _is_busy(self) -> bool:
        """返回当前是否存在后台任务。"""

        return (
            self.session.import_state.busy
            or self.processing_manager.busy
            or self.plot_manager.busy
            or self.export_manager.busy
        )

    def _update_action_states(self) -> None:
        busy = self._is_busy()
        self.actions_map["中止当前任务"].setEnabled(
            (self.session.import_state.busy and self.session.import_state.cancellable) or self.processing_manager.busy
        )
        for action_name in ("新建项目", "打开项目", "保存项目", "切换桥梁演示数据", "切换通用演示数据"):
            self.actions_map[action_name].setEnabled(not busy)
        self.actions_map["导入与筛选"].setEnabled(not busy)
        self.actions_map["校验"].setEnabled(not busy)
        self.actions_map["执行"].setEnabled(not busy)

    def _trigger_action(self, action_name: str) -> None:
        quick_map = {
            "接入主样本集": "导入与筛选",
            "管理子样本集": "构建子集",
            "开始分析": "切换到数据处理页",
            "快速出图": "切换到图形绘制页",
            "去交付": "交付预检",
        }
        mapped_name = quick_map.get(action_name, action_name)
        if mapped_name in self.actions_map:
            self.actions_map[mapped_name].trigger()
            return
        if action_name == "查看 metadata 字段":
            TableDialog(
                "metadata 字段",
                ("字段名",),
                [(field,) for field in (self.session.primary_sampleset.metadata_fields or ("无",))],
                self,
            ).exec()
            return
        if action_name == "查看支持 categories":
            TableDialog(
                "支持 categories",
                ("分类",),
                [(item,) for item in (self.session.primary_sampleset.supported_categories or ("无",))],
                self,
            ).exec()
            return
        if action_name == "构建子集":
            self._set_current_module(ModuleKey.IMPORT)
            self.workspace.import_filter_workspace.focus_subset_workspace()
            return
        if action_name == "执行工程导出":
            ExportPrecheckDialog(self.session, self).exec()
            return
        if action_name == "导入预览":
            ImportPreviewDialog(self.session, self).exec()
            return

        direct_actions = {
            "接入主样本集": lambda: self._open_import_workflow(ImportKind.SAMPLE_SET),
            "管理子样本集": lambda: (
                self._set_current_module(ModuleKey.IMPORT),
                self.workspace.import_filter_workspace.focus_subset_workspace(),
            ),
            "开始分析": lambda: self._set_current_module(ModuleKey.PROCESSING),
            "快速出图": lambda: self._set_current_module(ModuleKey.PLOTTING),
            "去交付": lambda: ExportPrecheckDialog(self.session, self).exec(),
            "查看结果预览": lambda: ResultPreviewDialog(self.session, self).exec(),
            "打开大图预览": lambda: FigurePreviewDialog(self._current_plot_figure, self).exec(),
            "刷新预览": lambda: FigurePreviewDialog(self._current_plot_figure, self).exec(),
            "交付预检": lambda: ExportPrecheckDialog(self.session, self).exec(),
            "查看日志详情": lambda: LogDetailDialog(self.session, self).exec(),
            "打开长任务进度": lambda: LongTaskProgressDialog(self.session, self._cancel_import_operation, self).exec(),
            "代码审查结果": lambda: CodeReviewResultDialog(self.session, self).exec(),
        }
        if action_name in direct_actions:
            direct_actions[action_name]()
            return

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._allow_close:
            self._allow_close = False
            self._close_after_cleanup = False
            self._save_settings_from_session()
            self.settings_store.save_main_window(self)
            event.accept()
            return
        if self.session.import_state.busy:
            result = QMessageBox.question(
                self,
                "导入仍在进行",
                "导入正在进行，将先中止并清理资源。是否继续关闭？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if result is QMessageBox.StandardButton.Yes:
                self._close_after_cleanup = True
                self.session.arm_close_guard()
                self._cancel_import_operation()
            event.ignore()
            return
        self.session.clear_close_guard()
        self._save_settings_from_session()
        self.settings_store.save_main_window(self)
        super().closeEvent(event)
