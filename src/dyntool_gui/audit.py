"""GUI 主流程巡检工具。"""

from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
from time import monotonic
from typing import Callable

from PySide6.QtCore import QRect, QSize, Qt, QTimer
from PySide6.QtGui import QFont
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox, QPushButton, QWidget

from ._session_types import GuiCommandSnapshot, GuiSelectionSnapshot, GuiTaskSnapshot
from .persistence import ProjectFileStore
from .screenshot import resolve_gui_font_family
from .session import ModuleKey, ProjectSession, resolve_scope_uids
from .theme import ThemeManager
from .widgets import (
    CodeReviewResultDialog,
    ExportPrecheckDialog,
    FigurePreviewDialog,
    HelpDialog,
    ImportPreviewDialog,
    LongTaskProgressDialog,
    ResultPreviewDialog,
    SettingsDialog,
)


@dataclass(frozen=True, slots=True)
class GuiAuditOptions:
    """GUI 巡检配置。"""

    output_dir: Path
    data_source: Path | None = None
    project_dir: Path | None = None
    width: int = 1920
    height: int = 1080
    run_heavy_actions: bool = False
    include_deep_check: bool = False
    timeout_seconds: float = 120.0


@dataclass(slots=True)
class AuditActionResult:
    """按钮或菜单动作巡检结果。"""

    name: str
    area: str
    status: str
    detail: str = ""


@dataclass(slots=True)
class AuditScreenshot:
    """截图记录。"""

    name: str
    path: str
    width: int
    height: int


@dataclass(slots=True)
class GuiAuditReport:
    """GUI 巡检报告。"""

    output_dir: str
    data_source: str
    actions: list[AuditActionResult] = field(default_factory=list)
    screenshots: list[AuditScreenshot] = field(default_factory=list)
    dialogs: list[str] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    layout_metrics: list[dict[str, object]] = field(default_factory=list)
    workflow_metrics: list[dict[str, object]] = field(default_factory=list)
    feedback_metrics: list[dict[str, object]] = field(default_factory=list)
    semantic_workflow: list[dict[str, object]] = field(default_factory=list)
    command_snapshots: list[GuiCommandSnapshot] = field(default_factory=list)
    feedback_events: list[dict[str, object]] = field(default_factory=list)
    artifacts: list[dict[str, object]] = field(default_factory=list)
    rule_snapshots: list[dict[str, object]] = field(default_factory=list)
    button_state_snapshots: list[dict[str, object]] = field(default_factory=list)
    plot_consistency_snapshots: list[dict[str, object]] = field(default_factory=list)
    cancel_snapshots: list[dict[str, object]] = field(default_factory=list)
    consistency_issues: list[str] = field(default_factory=list)

    def write(self) -> None:
        """写出 JSON 与 Markdown 报告。"""

        output_dir = Path(self.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "audit-report.json").write_text(
            json.dumps(asdict(self), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        lines = [
            "# GUI 巡检报告",
            "",
            f"- 数据源：{self.data_source or '-'}",
            f"- 截图数量：{len(self.screenshots)}",
            f"- 动作数量：{len(self.actions)}",
            f"- 问题数量：{len(self.issues)}",
            f"- 一致性问题数量：{len(self.consistency_issues)}",
            "",
            "## 动作结果",
            "",
        ]
        lines.extend(f"- `{item.area}` / `{item.name}`：{item.status} {item.detail}".rstrip() for item in self.actions)
        if self.workflow_metrics:
            lines.extend(["", "## 操作链快照", ""])
            for item in self.workflow_metrics:
                lines.append(
                    "- `{label}`：页面={module}，范围={scope_kind}，后台忙碌={busy}".format(
                        label=item.get("label", ""),
                        module=item.get("current_module", ""),
                        scope_kind=item.get("scope_kind", ""),
                        busy=item.get("any_busy", False),
                    )
                )
        if self.layout_metrics:
            lines.extend(["", "## 布局指标", ""])
            for item in self.layout_metrics:
                regions = item.get("regions", [])
                lines.append(f"- `{item.get('label', '')}`：记录区域 {len(regions)} 个")
        if self.feedback_metrics:
            lines.extend(["", "## 反馈快照", ""])
            for item in self.feedback_metrics:
                lines.append(
                    "- `{label}`：状态栏={status_task_text}，进度条={progress_visible}，任务/日志/问题/导出={task_rows}/{log_rows}/{issue_rows}/{export_rows}".format(
                        label=item.get("label", ""),
                        status_task_text=item.get("status_task_text", ""),
                        progress_visible=item.get("progress_visible", False),
                        task_rows=item.get("task_rows", 0),
                        log_rows=item.get("log_rows", 0),
                        issue_rows=item.get("issue_rows", 0),
                        export_rows=item.get("export_rows", 0),
                    )
                )
        if self.semantic_workflow:
            lines.extend(["", "## 语义工作流", ""])
            lines.extend(
                "- `{label}`：{stage} / {area} / {name} / {status}".format(
                    label=item.get("label", ""),
                    stage=item.get("stage", ""),
                    area=item.get("area", ""),
                    name=item.get("name", ""),
                    status=item.get("status", ""),
                ).rstrip(" / ")
                for item in self.semantic_workflow
            )
        if self.command_snapshots:
            lines.extend(["", "## 命令快照", ""])
            for item in self.command_snapshots:
                lines.append(
                    "- `{label}`：页面={module}，范围={scope}，状态栏={status}".format(
                        label=item.label,
                        module=item.selection.current_module,
                        scope=item.selection.scope_kind,
                        status=item.task.status_task_text,
                    )
                )
        if self.button_state_snapshots:
            lines.extend(["", "## 按钮状态", ""])
            for item in self.button_state_snapshots:
                disabled_count = sum(1 for button in item.get("buttons", []) if not button.get("enabled", False))
                lines.append(f"- `{item.get('label', '')}`：禁用按钮 {disabled_count} 个")
        if self.plot_consistency_snapshots:
            lines.extend(["", "## 绘图一致性", ""])
            for item in self.plot_consistency_snapshots:
                lines.append(
                    "- `{label}`：可保存={can_save}，当前设置匹配画布={matches}，原因={reason}".format(
                        label=item.get("label", ""),
                        can_save=item.get("can_save", False),
                        matches=item.get("matches_rendered", False),
                        reason=item.get("reason", ""),
                    )
                )
        lines.extend(["", "## 截图", ""])
        lines.extend(f"- `{item.name}`：`{item.path}` ({item.width}x{item.height})" for item in self.screenshots)
        if self.artifacts:
            lines.extend(["", "## 产物", ""])
            lines.extend(
                "- `{name}`：{artifact_type} `{path}`".format(
                    name=item.get("name", ""),
                    artifact_type=item.get("artifact_type", ""),
                    path=item.get("path", ""),
                )
                for item in self.artifacts
            )
        if self.consistency_issues:
            lines.extend(["", "## 反馈一致性", ""])
            lines.extend(f"- {issue}" for issue in self.consistency_issues)
        if self.issues:
            lines.extend(["", "## 问题", ""])
            lines.extend(f"- {issue}" for issue in self.issues)
        (output_dir / "audit-report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


@dataclass(slots=True)
class _AuditSnapshotRecorder:
    """记录 GUI 操作链和反馈链快照。"""

    report: GuiAuditReport
    window: QWidget
    app: QApplication

    def capture(
        self,
        label: str,
        *,
        stage: str = "checkpoint",
        area: str = "",
        name: str = "",
        status: str = "",
        detail: str = "",
    ) -> None:
        """记录一次当前窗口状态。"""

        selection = self._selection_snapshot()
        task = self._task_snapshot()
        action_states = self._action_states()
        command_snapshot = GuiCommandSnapshot(
            label=label,
            area=area,
            name=name,
            status=status,
            detail=detail,
            selection=selection,
            task=task,
            action_states=action_states,
        )
        workflow = {
            "label": label,
            "current_module": selection.current_module,
            "scope_kind": selection.scope_kind,
            "scope_note": selection.scope_note,
            "busy": task.manager_busy,
            "any_busy": task.any_busy,
            "action_states": action_states,
        }
        feedback = {
            "label": label,
            "status_task_text": task.status_task_text,
            "progress_visible": task.progress_visible,
            "task_rows": task.task_rows,
            "log_rows": task.log_rows,
            "issue_rows": task.issue_rows,
            "export_rows": task.export_rows,
            "active_dialog_titles": list(task.active_dialog_titles),
        }
        self.report.workflow_metrics.append(workflow)
        self.report.layout_metrics.append(self._layout_metric(label))
        self.report.feedback_metrics.append(feedback)
        self.report.command_snapshots.append(command_snapshot)
        self.report.rule_snapshots.append(self._rule_snapshot(label))
        self.report.button_state_snapshots.append(self._button_state_snapshot(label))
        self.report.plot_consistency_snapshots.append(self._plot_consistency_snapshot(label))
        self.report.cancel_snapshots.append(self._cancel_snapshot(label))
        self.report.semantic_workflow.append(
            {
                "label": label,
                "stage": stage,
                "area": area,
                "name": name,
                "status": status,
                "current_module": selection.current_module,
                "scope_kind": selection.scope_kind,
            }
        )
        self.report.feedback_events.append(
            {
                "label": label,
                "event_kind": stage,
                "status_task_text": task.status_task_text,
                "progress_visible": task.progress_visible,
                "manager_busy": task.manager_busy,
                "bottom_rows": {
                    "tasks": task.task_rows,
                    "logs": task.log_rows,
                    "issues": task.issue_rows,
                    "exports": task.export_rows,
                },
                "active_dialog_titles": list(task.active_dialog_titles),
            }
        )
        self._append_consistency_issues(label, task, action_states)

    def capture_action(self, area: str, result: AuditActionResult) -> None:
        """记录动作执行后的命令快照。"""

        self.capture(
            f"{area}/{result.name}",
            stage="action",
            area=area,
            name=result.name,
            status=result.status,
            detail=result.detail,
        )

    def _selection_snapshot(self) -> GuiSelectionSnapshot:
        session = self.window.session  # type: ignore[attr-defined]
        scope = session.current_scope
        return GuiSelectionSnapshot(
            current_module=getattr(session.current_module, "value", str(session.current_module)),
            current_selection=str(getattr(session, "current_selection", "")),
            scope_kind=scope.scope_kind,
            subset_ids=tuple(scope.subset_ids),
            sample_uids=tuple(scope.sample_uids),
            scope_note=scope.note,
        )

    def _task_snapshot(self) -> GuiTaskSnapshot:
        session = self.window.session  # type: ignore[attr-defined]
        return GuiTaskSnapshot(
            manager_busy=self._manager_busy(),
            any_busy=bool(self.window._is_busy()),  # type: ignore[attr-defined]
            status_task_text=self._status_task_text(),
            progress_visible=self._progress_visible(),
            task_rows=len(session.tasks),
            log_rows=len(session.logs),
            issue_rows=len(session.issues),
            export_rows=len(session.exports),
            active_dialog_titles=tuple(self._active_dialog_titles()),
        )

    def _manager_busy(self) -> dict[str, bool]:
        session = self.window.session  # type: ignore[attr-defined]
        return {
            "import_state": bool(session.import_state.busy),
            "import_manager": bool(self.window.import_manager.busy),  # type: ignore[attr-defined]
            "processing_manager": bool(self.window.processing_manager.busy),  # type: ignore[attr-defined]
            "plot_manager": bool(self.window.plot_manager.busy),  # type: ignore[attr-defined]
            "export_manager": bool(self.window.export_manager.busy),  # type: ignore[attr-defined]
        }

    def _action_states(self) -> dict[str, bool]:
        actions_map = getattr(self.window, "actions_map", {})
        return {
            name: bool(action.isEnabled())
            for name, action in actions_map.items()
            if name in {"新建项目", "打开项目", "保存项目", "校验", "执行", "导入与筛选", "中止当前任务"}
        }

    def _rule_snapshot(self, label: str) -> dict[str, object]:
        workspace = getattr(self.window, "workspace", None)
        subset = getattr(workspace, "subset_workspace", None)
        if subset is None:
            return {"label": label, "available": False}
        try:
            spec = subset.scope_editor_values()
        except Exception as exc:  # noqa: BLE001
            return {"label": label, "available": False, "error": str(exc)}
        return {"label": label, "available": True, "filter_spec": asdict(spec)}

    def _button_state_snapshot(self, label: str) -> dict[str, object]:
        buttons: list[dict[str, object]] = []
        for button in self.window.findChildren(QPushButton):
            name = button.objectName() or button.text().strip()
            if not name:
                continue
            enabled = bool(button.isEnabled())
            reason = ""
            reason_source = ""
            if not enabled:
                if button.toolTip():
                    reason = button.toolTip()
                    reason_source = "tooltip"
                elif button.statusTip():
                    reason = button.statusTip()
                    reason_source = "statusTip"
                else:
                    reason = "当前入口不可用"
                    reason_source = "fallback"
            rect = button.geometry()
            buttons.append(
                {
                    "name": name,
                    "text": button.text().strip(),
                    "enabled": enabled,
                    "disabled_reason": reason,
                    "disabled_reason_source": reason_source,
                    "visible": bool(button.isVisible()),
                    "rect": (rect.x(), rect.y(), rect.width(), rect.height()),
                    "area": rect.width() * rect.height(),
                }
            )
        return {"label": label, "buttons": buttons}

    def _layout_metric(self, label: str) -> dict[str, object]:
        region_names = (
            "ImportActionRegion",
            "ImportResultRegion",
            "SubsetFilterScrollArea",
            "SubsetPreviewRegion",
            "SubsetSavedPanel",
            "ProcessingActionRegion",
            "ProcessingResultRegion",
            "PlottingActionRegion",
            "PlottingResultRegion",
            "PlottingCanvasSurface",
            "PlottingResultTabs",
        )
        window_area = max(1, self.window.width() * self.window.height())
        regions: list[dict[str, object]] = []
        for name in region_names:
            widget = self.window.findChild(QWidget, name)
            if widget is None:
                continue
            rect = widget.geometry()
            top_left = widget.mapTo(self.window, rect.topLeft())
            area = rect.width() * rect.height()
            regions.append(
                {
                    "name": name,
                    "surface_role": str(widget.property("surfaceRole") or ""),
                    "rect": (top_left.x(), top_left.y(), rect.width(), rect.height()),
                    "area": area,
                    "area_ratio_window": area / window_area,
                    "visible": bool(widget.isVisible()),
                }
            )
        return {
            "label": label,
            "window_size": (self.window.width(), self.window.height()),
            "regions": regions,
        }

    def _plot_consistency_snapshot(self, label: str) -> dict[str, object]:
        session = self.window.session  # type: ignore[attr-defined]
        workspace = getattr(self.window, "workspace", None)
        plotting = getattr(workspace, "plotting_workspace", None)
        if plotting is None:
            return {"label": label, "available": False}
        try:
            current = plotting.plot_request_snapshot(tuple(resolve_scope_uids(session)))
            can_save, reason = plotting.save_availability(session)
        except Exception as exc:  # noqa: BLE001
            return {"label": label, "available": False, "error": str(exc)}
        rendered = session.plot_state.rendered_request
        return {
            "label": label,
            "available": True,
            "current_request": asdict(current),
            "rendered_request": None if rendered is None else asdict(rendered),
            "matches_rendered": current == rendered,
            "can_save": can_save,
            "reason": reason,
        }

    def _cancel_snapshot(self, label: str) -> dict[str, object]:
        session = self.window.session  # type: ignore[attr-defined]
        return {
            "label": label,
            "import": {
                "busy": bool(session.import_state.busy),
                "cancellable": bool(session.import_state.cancellable),
                "cancel_requested": bool(session.import_state.cancel_requested),
            },
            "processing": {
                "busy": bool(session.processing_state.busy),
                "cancel_requested": bool(session.processing_state.cancel_requested),
            },
        }

    def _status_task_text(self) -> str:
        status_task = getattr(self.window, "_status_task", None)
        if status_task is None:
            return ""
        return str(status_task.text())

    def _progress_visible(self) -> bool:
        progress = getattr(self.window, "_status_progress", None)
        return bool(progress is not None and not progress.isHidden())

    def _active_dialog_titles(self) -> list[str]:
        return sorted(
            str(widget.windowTitle())
            for widget in self.app.topLevelWidgets()
            if isinstance(widget, QDialog) and widget.isVisible() and widget.windowTitle()
        )

    def _append_consistency_issues(
        self,
        label: str,
        task: GuiTaskSnapshot,
        action_states: dict[str, bool],
    ) -> None:
        status_text = task.status_task_text
        if task.any_busy and not task.progress_visible:
            self.report.consistency_issues.append(f"{label}：后台任务忙碌但状态栏进度不可见。")
        if task.any_busy and action_states.get("执行", False):
            self.report.consistency_issues.append(f"{label}：后台任务忙碌但主执行入口仍可用。")
        if task.any_busy and action_states.get("新建项目", False):
            self.report.consistency_issues.append(f"{label}：后台任务忙碌但新建项目入口仍可用。")
        if not task.any_busy and any(token in status_text for token in ("进行中", "收尾中")):
            self.report.consistency_issues.append(f"{label}：后台任务空闲但状态栏仍显示忙碌。")


def run_gui_audit(options: GuiAuditOptions) -> GuiAuditReport:
    """执行 GUI 主流程巡检并返回报告。"""

    app = QApplication.instance() or QApplication([])
    app.setFont(QFont(resolve_gui_font_family(), 10))
    output_dir = options.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    session = ProjectSession.build_empty()
    project_dir = (options.project_dir or output_dir / "project").resolve()
    project_dir.mkdir(parents=True, exist_ok=True)

    from .main_window import MainWindow

    window = MainWindow(session, theme_manager=ThemeManager(), project_store=ProjectFileStore())
    window.setWindowState(Qt.WindowState.WindowNoState)
    window.resize(QSize(options.width, options.height))
    window.show()
    _pump_events(app)

    report = GuiAuditReport(
        output_dir=str(output_dir),
        data_source=str(options.data_source.resolve()) if options.data_source is not None else "",
    )
    recorder = _AuditSnapshotRecorder(report=report, window=window, app=app)

    with _DialogInterceptor(report):
        _prepare_real_source(window, project_dir, options.data_source)
        recorder.capture("initial")
        _capture_window(report, window, "00-initial", output_dir, options.width, options.height)
        _exercise_window_layout(report, window, output_dir)
        recorder.capture("layout")
        _exercise_navigation_and_overview(report, window, output_dir, app, recorder)
        recorder.capture("navigation")
        _exercise_import_flow(report, window, options, output_dir, app, recorder)
        recorder.capture("import")
        _exercise_subset_processing_plot_export(report, window, options, output_dir, app, recorder)
        recorder.capture("workflow")
        _capture_dialogs(report, window, output_dir, app)
        recorder.capture("dialogs")

    window.close()
    _pump_events(app)
    report.write()
    return report


def _prepare_real_source(window: QWidget, project_dir: Path, data_source: Path | None) -> None:
    session = window.session  # type: ignore[attr-defined]
    workflow = window.workspace.import_workflow  # type: ignore[attr-defined]
    session.set_project_directory(project_dir)
    workflow.set_project_directory(project_dir)
    if data_source is not None:
        session.set_import_source(data_source)
        workflow.set_source_path(data_source)
    window._reload_view()  # type: ignore[attr-defined]


def _exercise_window_layout(report: GuiAuditReport, window: QWidget, output_dir: Path) -> None:
    for width, height in ((1366, 768), (1600, 900), (1920, 1080), (2560, 1440)):
        window.setWindowState(Qt.WindowState.WindowNoState)
        window.resize(width, height)
        window._apply_adaptive_layout(force=True)  # type: ignore[attr-defined]
        _pump_events(QApplication.instance())
        _capture_window(report, window, f"resize-{width}x{height}", output_dir, width, height)
    window.showMaximized()
    _pump_events(QApplication.instance())
    _capture_window(report, window, "window-maximized", output_dir, 1920, 1080)
    window.showNormal()
    window.resize(1920, 1080)
    window.left_dock.hide()  # type: ignore[attr-defined]
    window.bottom_dock.hide()  # type: ignore[attr-defined]
    _capture_window(report, window, "dock-hidden", output_dir, 1920, 1080)
    window._restore_default_layout()  # type: ignore[attr-defined]
    _capture_window(report, window, "dock-restored", output_dir, 1920, 1080)


def _exercise_navigation_and_overview(
    report: GuiAuditReport,
    window: QWidget,
    output_dir: Path,
    app: QApplication,
    recorder: _AuditSnapshotRecorder,
) -> None:
    for module in (ModuleKey.PROJECT, ModuleKey.IMPORT, ModuleKey.PROCESSING, ModuleKey.PLOTTING):
        _record_action(
            report,
            "导航",
            module.value,
            lambda module=module: window.workspace.set_current_module(module),
            recorder,
        )
        _pump_events(app)
        _capture_window(report, window, f"page-{module.value}", output_dir, 1920, 1080)
    for label in ("接入主样本集", "管理子样本集", "开始分析", "快速出图", "去交付"):
        _record_action(
            report,
            "总览快捷",
            label,
            lambda label=label: window._trigger_action(label),  # type: ignore[attr-defined]
            recorder,
        )
        _pump_events(app)


def _exercise_import_flow(
    report: GuiAuditReport,
    window: QWidget,
    options: GuiAuditOptions,
    output_dir: Path,
    app: QApplication,
    recorder: _AuditSnapshotRecorder,
) -> None:
    project_dir = (options.project_dir or output_dir / "project").resolve()
    _prepare_real_source(window, project_dir, options.data_source)
    window.workspace.set_current_module(ModuleKey.IMPORT)  # type: ignore[attr-defined]
    _capture_window(report, window, "import-before-actions", output_dir, 1920, 1080)
    if options.data_source is None:
        _record_action(
            report,
            "导入链路",
            "轻量预览",
            lambda: window._preview_import(),  # type: ignore[attr-defined]
            recorder,
        )
        return
    _record_action(
        report,
        "导入链路",
        "轻量预览",
        lambda: window._preview_import(),  # type: ignore[attr-defined]
        recorder,
    )
    _wait_for_idle(window, app, options.timeout_seconds)
    _capture_window(report, window, "import-after-preview", output_dir, 1920, 1080)
    if options.include_deep_check:
        _record_action(
            report,
            "导入链路",
            "深度检查单位",
            lambda: window._deep_check_units(),  # type: ignore[attr-defined]
            recorder,
        )
        _wait_for_idle(window, app, options.timeout_seconds)
        _capture_window(report, window, "import-after-deep-check", output_dir, 1920, 1080)
    if options.run_heavy_actions:
        _record_action(
            report,
            "导入链路",
            "绑定为当前主样本集",
            lambda: window._execute_import(),  # type: ignore[attr-defined]
            recorder,
        )
        _wait_for_idle(window, app, options.timeout_seconds)
        _capture_window(report, window, "import-after-bind", output_dir, 1920, 1080)


def _exercise_subset_processing_plot_export(
    report: GuiAuditReport,
    window: QWidget,
    options: GuiAuditOptions,
    output_dir: Path,
    app: QApplication,
    recorder: _AuditSnapshotRecorder,
) -> None:
    window.workspace.set_current_module(ModuleKey.IMPORT)  # type: ignore[attr-defined]
    window.workspace.import_filter_workspace.focus_subset_workspace()  # type: ignore[attr-defined]
    _capture_window(report, window, "subset-before-actions", output_dir, 1920, 1080)
    subset = window.workspace.subset_workspace  # type: ignore[attr-defined]
    for label, action in (
        ("预览命中", lambda: window._preview_subset(subset.scope_editor_values())),  # type: ignore[attr-defined]
        ("保存为动态子集", subset._emit_save_dynamic_request),
        ("保存为冻结快照", subset._emit_save_frozen_request),
        ("设为当前范围", subset._emit_use_scope_request),
        ("回到全部样本", lambda: window._trigger_action("回到全部样本")),  # type: ignore[attr-defined]
    ):
        _record_action(report, "子集链路", label, action, recorder)
        _pump_events(app)
    _capture_window(report, window, "subset-after-actions", output_dir, 1920, 1080)

    window.workspace.set_current_module(ModuleKey.PROCESSING)  # type: ignore[attr-defined]
    processing = window.workspace.processing_workspace  # type: ignore[attr-defined]
    if options.run_heavy_actions:
        _record_action(
            report,
            "分析链路",
            "选择单样本轻量分析",
            lambda: _configure_single_sample_processing(window, processing),
            recorder,
        )
    for label, action in (
        ("处理参数", lambda: _show_transient_dialog(processing._processing_config_dialog)),
        ("执行分析", processing._run_button.click),
        ("生成预览表", processing._preview_button.click),
    ):
        _record_action(report, "分析链路", label, action, recorder)
        if options.run_heavy_actions:
            if not _safe_wait_for_idle(report, window, app, options.timeout_seconds, f"分析链路 / {label}"):
                _capture_window(report, window, "processing-timeout", output_dir, 1920, 1080)
                return
        else:
            _pump_events(app)
    _capture_window(report, window, "processing-after-actions", output_dir, 1920, 1080)

    window.workspace.set_current_module(ModuleKey.PLOTTING)  # type: ignore[attr-defined]
    plotting = window.workspace.plotting_workspace  # type: ignore[attr-defined]
    for label, action in (
        ("计算所需结果", plotting._emit_compute_request),
        ("绘图设置", lambda: _show_transient_dialog(plotting._plot_settings_dialog)),
        ("渲染", plotting._render_button.click),
        (
            "保存图片",
            lambda: (
                _save_current_plot_for_audit(window, output_dir)
                if options.run_heavy_actions
                else plotting._save_button.click()
            ),
        ),
    ):
        _record_action(report, "绘图链路", label, action, recorder)
        if options.run_heavy_actions:
            if not _safe_wait_for_idle(report, window, app, options.timeout_seconds, f"绘图链路 / {label}"):
                _capture_window(report, window, "plotting-timeout", output_dir, 1920, 1080)
                return
        else:
            _pump_events(app)
    _capture_window(report, window, "plotting-after-actions", output_dir, 1920, 1080)

    export = window.workspace.export_workspace  # type: ignore[attr-defined]
    export.load_session(window.session)  # type: ignore[attr-defined]
    _record_action(
        report,
        "导出链路",
        "导出预检",
        lambda: ExportPrecheckDialog(window.session, window).show(),  # type: ignore[attr-defined]
        recorder,
    )
    _record_action(report, "导出链路", "执行导出", export._emit_export_request, recorder)
    if options.run_heavy_actions:
        if not _safe_wait_for_idle(report, window, app, options.timeout_seconds, "导出链路 / 执行导出"):
            _capture_window(report, window, "export-timeout", output_dir, 1920, 1080)
            return
    else:
        _pump_events(app)


def _capture_dialogs(report: GuiAuditReport, window: QWidget, output_dir: Path, app: QApplication) -> None:
    session = window.session  # type: ignore[attr-defined]
    dialogs: tuple[tuple[str, QDialog], ...] = (
        ("dialog-settings", SettingsDialog(session, parent=window)),
        ("dialog-help", HelpDialog(parent=window)),
        ("dialog-import-preview", ImportPreviewDialog(session, parent=window)),
        ("dialog-result-preview", ResultPreviewDialog(session, parent=window)),
        ("dialog-figure-preview", FigurePreviewDialog(parent=window)),
        ("dialog-export-precheck", ExportPrecheckDialog(session, parent=window)),
        ("dialog-long-task", LongTaskProgressDialog(session, parent=window)),
        ("dialog-code-review", CodeReviewResultDialog(session, parent=window)),
    )
    for name, dialog in dialogs:
        dialog.resize(960, 640)
        dialog.show()
        _pump_events(app)
        _capture_widget(report, dialog, name, output_dir)
        dialog.resize(1280, 760)
        _pump_events(app)
        _capture_widget(report, dialog, f"{name}-resized", output_dir)
        dialog.close()


def _record_action(
    report: GuiAuditReport,
    area: str,
    name: str,
    action: Callable[[], object],
    recorder: _AuditSnapshotRecorder | None = None,
) -> AuditActionResult:
    try:
        action()
    except Exception as exc:  # noqa: BLE001
        result = AuditActionResult(name=name, area=area, status="failed", detail=str(exc))
        report.actions.append(result)
        report.issues.append(f"{area}/{name} 触发失败：{exc}")
    else:
        result = AuditActionResult(name=name, area=area, status="ok")
        report.actions.append(result)
    if recorder is not None:
        recorder.capture_action(area, result)
    return result


def _show_transient_dialog(dialog: QDialog) -> None:
    dialog.show()
    dialog.raise_()
    QTimer.singleShot(100, dialog.close)


def _wait_for_idle(window: QWidget, app: QApplication, timeout_seconds: float) -> None:
    deadline = monotonic() + timeout_seconds
    while monotonic() < deadline:
        _pump_events(app)
        if not window._is_busy():  # type: ignore[attr-defined]
            return
        QTest.qWait(50)
    raise TimeoutError(f"GUI 任务超过 {timeout_seconds:.0f} 秒仍未完成")


def _safe_wait_for_idle(
    report: GuiAuditReport,
    window: QWidget,
    app: QApplication,
    timeout_seconds: float,
    label: str,
) -> bool:
    try:
        _wait_for_idle(window, app, timeout_seconds)
    except TimeoutError as exc:
        report.issues.append(f"{label} 超时：{exc}")
        _force_stop_busy_tasks(window, app)
        return False
    return True


def _force_stop_busy_tasks(window: QWidget, app: QApplication) -> None:
    """巡检超时兜底：避免后台线程拖住截图进程。"""

    cancel = getattr(window, "_cancel_import_operation", None)
    if callable(cancel):
        cancel()
    _pump_events(app)
    for manager_name in ("processing_manager", "plot_manager", "export_manager", "import_manager"):
        manager = getattr(window, manager_name, None)
        thread = getattr(manager, "_thread", None)
        if thread is None:
            continue
        thread.terminate()
        thread.wait(3000)
        cleanup = getattr(manager, "_cleanup", None)
        if callable(cleanup):
            cleanup()
    _pump_events(app)


def _save_current_plot_for_audit(window: QWidget, output_dir: Path) -> None:
    """审计模式下不打开文件对话框，直接保存当前图形。"""

    figure = getattr(window, "_current_plot_figure", None)
    if figure is None:
        raise ValueError("当前还没有可保存的图像。")
    target = output_dir / "artifacts" / "current-plot.png"
    plot_manager = getattr(window, "plot_manager")
    plot_manager.save_figure(figure, target)
    refresh = getattr(window, "_refresh_plot_views", None)
    if callable(refresh):
        refresh()


def _configure_single_sample_processing(window: QWidget, processing: QWidget) -> None:
    """为真实数据巡检选择可在有限时间内完成的单样本分析。"""

    runtime = window.session.primary_runtime  # type: ignore[attr-defined]
    first_uid = ""
    if runtime is not None and hasattr(runtime, "keys"):
        first_uid = str(next(iter(runtime.keys()), ""))
    processing._set_action_value("eval_zvl")  # type: ignore[attr-defined]
    processing._set_combo_value(processing._scope_kind_combo, "single_sample")  # type: ignore[attr-defined]
    processing._scope_target_edit.setText(first_uid)  # type: ignore[attr-defined]


def _capture_window(
    report: GuiAuditReport,
    window: QWidget,
    name: str,
    output_dir: Path,
    width: int,
    height: int,
) -> None:
    _pump_events(QApplication.instance())
    pixmap = window.grab(QRect(0, 0, width, height))
    path = output_dir / f"{name}.png"
    pixmap.save(str(path), "PNG")
    report.screenshots.append(AuditScreenshot(name=name, path=str(path), width=width, height=height))
    report.artifacts.append(
        {
            "name": name,
            "artifact_type": "screenshot",
            "path": str(path),
            "width": width,
            "height": height,
        }
    )


def _capture_widget(report: GuiAuditReport, widget: QWidget, name: str, output_dir: Path) -> None:
    pixmap = widget.grab()
    path = output_dir / f"{name}.png"
    pixmap.save(str(path), "PNG")
    size = widget.size()
    report.screenshots.append(AuditScreenshot(name=name, path=str(path), width=size.width(), height=size.height()))
    report.artifacts.append(
        {
            "name": name,
            "artifact_type": "screenshot",
            "path": str(path),
            "width": size.width(),
            "height": size.height(),
        }
    )


def _pump_events(app: QApplication | None) -> None:
    if app is None:
        return
    for _ in range(3):
        app.processEvents()


class _DialogInterceptor(AbstractContextManager["_DialogInterceptor"]):
    def __init__(self, report: GuiAuditReport) -> None:
        self._report = report
        self._original_warning = QMessageBox.warning
        self._original_information = QMessageBox.information
        self._original_about = QMessageBox.about
        self._original_question = QMessageBox.question
        self._original_exec = QDialog.exec

    def __enter__(self) -> "_DialogInterceptor":
        def _record_message(parent: QWidget | None, title: str, text: str, *args: object, **kwargs: object) -> object:
            del parent, args, kwargs
            self._report.dialogs.append(str(title))
            self._report.feedback_events.append(
                {
                    "label": f"消息框/{title}",
                    "event_kind": "message_box",
                    "message": str(text),
                }
            )
            return QMessageBox.StandardButton.Ok

        def _record_exec(dialog: QDialog) -> int:
            self._report.dialogs.append(dialog.windowTitle())
            dialog.show()
            _pump_events(QApplication.instance())
            dialog.close()
            return int(QDialog.DialogCode.Accepted)

        QMessageBox.warning = _record_message  # type: ignore[method-assign]
        QMessageBox.information = _record_message  # type: ignore[method-assign]
        QMessageBox.about = _record_message  # type: ignore[method-assign]
        QMessageBox.question = lambda *args, **kwargs: QMessageBox.StandardButton.No  # type: ignore[method-assign]
        QDialog.exec = _record_exec  # type: ignore[method-assign]
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        QMessageBox.warning = self._original_warning  # type: ignore[method-assign]
        QMessageBox.information = self._original_information  # type: ignore[method-assign]
        QMessageBox.about = self._original_about  # type: ignore[method-assign]
        QMessageBox.question = self._original_question  # type: ignore[method-assign]
        QDialog.exec = self._original_exec  # type: ignore[method-assign]


__all__ = ["AuditActionResult", "AuditScreenshot", "GuiAuditOptions", "GuiAuditReport", "run_gui_audit"]
