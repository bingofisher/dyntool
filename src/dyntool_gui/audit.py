"""GUI 主流程巡检工具。"""

from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
from time import monotonic
from typing import Callable

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QFont
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox, QWidget

from .persistence import ProjectFileStore
from .screenshot import resolve_gui_font_family
from .session import ModuleKey, ProjectSession
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
            "",
            "## 动作结果",
            "",
        ]
        lines.extend(f"- `{item.area}` / `{item.name}`：{item.status} {item.detail}".rstrip() for item in self.actions)
        lines.extend(["", "## 截图", ""])
        lines.extend(f"- `{item.name}`：`{item.path}` ({item.width}x{item.height})" for item in self.screenshots)
        if self.issues:
            lines.extend(["", "## 问题", ""])
            lines.extend(f"- {issue}" for issue in self.issues)
        (output_dir / "audit-report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


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

    with _DialogInterceptor(report):
        _prepare_real_source(window, project_dir, options.data_source)
        _capture_window(report, window, "00-initial", output_dir, options.width, options.height)
        _exercise_window_layout(report, window, output_dir)
        _exercise_navigation_and_overview(report, window, output_dir, app)
        _exercise_import_flow(report, window, options, output_dir, app)
        _exercise_subset_processing_plot_export(report, window, options, output_dir, app)
        _capture_dialogs(report, window, output_dir, app)

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
) -> None:
    for module in (ModuleKey.PROJECT, ModuleKey.IMPORT, ModuleKey.PROCESSING, ModuleKey.PLOTTING):
        _record_action(report, "导航", module.value, lambda module=module: window.workspace.set_current_module(module))
        _pump_events(app)
        _capture_window(report, window, f"page-{module.value}", output_dir, 1920, 1080)
    for label in ("接入主样本集", "管理子样本集", "开始分析", "快速出图", "去交付"):
        _record_action(report, "总览快捷", label, lambda label=label: window._trigger_action(label))  # type: ignore[attr-defined]
        _pump_events(app)


def _exercise_import_flow(
    report: GuiAuditReport,
    window: QWidget,
    options: GuiAuditOptions,
    output_dir: Path,
    app: QApplication,
) -> None:
    project_dir = (options.project_dir or output_dir / "project").resolve()
    _prepare_real_source(window, project_dir, options.data_source)
    window.workspace.set_current_module(ModuleKey.IMPORT)  # type: ignore[attr-defined]
    _capture_window(report, window, "import-before-actions", output_dir, 1920, 1080)
    if options.data_source is None:
        _record_action(report, "导入链路", "轻量预览", lambda: window._preview_import())  # type: ignore[attr-defined]
        return
    _record_action(report, "导入链路", "轻量预览", lambda: window._preview_import())  # type: ignore[attr-defined]
    _wait_for_idle(window, app, options.timeout_seconds)
    _capture_window(report, window, "import-after-preview", output_dir, 1920, 1080)
    if options.include_deep_check:
        _record_action(report, "导入链路", "深度检查单位", lambda: window._deep_check_units())  # type: ignore[attr-defined]
        _wait_for_idle(window, app, options.timeout_seconds)
        _capture_window(report, window, "import-after-deep-check", output_dir, 1920, 1080)
    if options.run_heavy_actions:
        _record_action(report, "导入链路", "绑定为当前主样本集", lambda: window._execute_import())  # type: ignore[attr-defined]
        _wait_for_idle(window, app, options.timeout_seconds)
        _capture_window(report, window, "import-after-bind", output_dir, 1920, 1080)


def _exercise_subset_processing_plot_export(
    report: GuiAuditReport,
    window: QWidget,
    options: GuiAuditOptions,
    output_dir: Path,
    app: QApplication,
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
        _record_action(report, "子集链路", label, action)
        _pump_events(app)
    _capture_window(report, window, "subset-after-actions", output_dir, 1920, 1080)

    window.workspace.set_current_module(ModuleKey.PROCESSING)  # type: ignore[attr-defined]
    processing = window.workspace.processing_workspace  # type: ignore[attr-defined]
    if options.run_heavy_actions:
        _record_action(
            report, "分析链路", "选择单样本轻量分析", lambda: _configure_single_sample_processing(window, processing)
        )
    for label, action in (
        ("高级选项", processing._adv_options_toggle.click),
        ("执行分析", processing._run_button.click),
        ("生成预览表", processing._preview_button.click),
    ):
        _record_action(report, "分析链路", label, action)
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
        ("渲染", plotting._render_button.click),
        ("保存图片", plotting._save_button.click),
    ):
        _record_action(report, "绘图链路", label, action)
        if options.run_heavy_actions:
            if not _safe_wait_for_idle(report, window, app, options.timeout_seconds, f"绘图链路 / {label}"):
                _capture_window(report, window, "plotting-timeout", output_dir, 1920, 1080)
                return
        else:
            _pump_events(app)
    _capture_window(report, window, "plotting-after-actions", output_dir, 1920, 1080)

    export = window.workspace.export_workspace  # type: ignore[attr-defined]
    export.load_session(window.session)  # type: ignore[attr-defined]
    _record_action(report, "导出链路", "导出预检", lambda: ExportPrecheckDialog(window.session, window).show())  # type: ignore[attr-defined]
    _record_action(report, "导出链路", "执行导出", export._emit_export_request)
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


def _record_action(report: GuiAuditReport, area: str, name: str, action: Callable[[], object]) -> None:
    try:
        action()
    except Exception as exc:  # noqa: BLE001
        report.actions.append(AuditActionResult(name=name, area=area, status="failed", detail=str(exc)))
        report.issues.append(f"{area}/{name} 触发失败：{exc}")
    else:
        report.actions.append(AuditActionResult(name=name, area=area, status="ok"))


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


def _capture_widget(report: GuiAuditReport, widget: QWidget, name: str, output_dir: Path) -> None:
    pixmap = widget.grab()
    path = output_dir / f"{name}.png"
    pixmap.save(str(path), "PNG")
    size = widget.size()
    report.screenshots.append(AuditScreenshot(name=name, path=str(path), width=size.width(), height=size.height()))


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
            self._report.issues.append(f"消息框：{title} / {text}")
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
