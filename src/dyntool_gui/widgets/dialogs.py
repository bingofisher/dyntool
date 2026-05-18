"""GUI 子窗口。"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Callable

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
from matplotlib.image import imread
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..persistence import AppSettingsStore
from ..session import ProjectSession
from ..theme import ThemeManager


def _configure_resizable_dialog(dialog: QDialog, title: str, width: int, height: int) -> None:
    """统一配置可拉伸对话框基础属性。"""

    dialog.setWindowTitle(title)
    dialog.resize(width, height)
    dialog.setSizeGripEnabled(True)


class PlaceholderDialog(QDialog):
    """文本型占位对话框。"""

    def __init__(self, title: str, body: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        _configure_resizable_dialog(self, title, 680, 420)
        layout = QVBoxLayout(self)
        text = QPlainTextEdit(body, self)
        text.setReadOnly(True)
        layout.addWidget(text)


class TableDialog(QDialog):
    """表格型对话框。"""

    def __init__(
        self,
        title: str,
        headers: tuple[str, ...],
        rows: list[tuple[str, ...]],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        _configure_resizable_dialog(self, title, 820, 460)
        layout = QVBoxLayout(self)
        table = QTableWidget(len(rows), len(headers), self)
        table.setHorizontalHeaderLabels(list(headers))
        for row_index, row in enumerate(rows):
            for column_index, value in enumerate(row):
                table.setItem(row_index, column_index, QTableWidgetItem(value))
        table.resizeColumnsToContents()
        layout.addWidget(table)


class SettingsDialog(QDialog):
    """窗口级设置对话框。"""

    def __init__(
        self,
        session: ProjectSession,
        settings_store: AppSettingsStore | None = None,
        theme_name: str = "light",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._session = session
        self._settings_store = settings_store
        _configure_resizable_dialog(self, "设置", 820, 560)

        preferences = settings_store.load_preferences() if settings_store is not None else {}
        recent_projects = preferences.get("recent_projects", [])
        recent_sample_dir = str(
            session.import_state.recent_sample_source_dir
            or preferences.get("recent_sample_dir")
            or session.workdir / "imports" / "samples"
        )
        recent_sampleset_dir = str(
            session.import_state.recent_sampleset_source_dir
            or preferences.get("recent_sampleset_dir")
            or session.workdir / "imports" / "sample_sets"
        )

        layout = QVBoxLayout(self)

        summary = QLabel(
            "当前设置页用于统一查看和维护窗口级偏好。主题名当前固定为只读展示，最近项目与最近导入目录支持调整。",
            self,
        )
        summary.setWordWrap(True)
        layout.addWidget(summary)

        panel = QGroupBox("常用偏好", self)
        panel.setObjectName("SettingsGeneralPanel")
        form = QFormLayout(panel)
        self._theme_name_edit = QLineEdit(theme_name, panel)
        self._theme_name_edit.setReadOnly(True)
        self._recent_projects_edit = QPlainTextEdit("\n".join(str(item) for item in recent_projects), panel)
        self._recent_projects_edit.setPlaceholderText("每行一个项目路径")
        self._recent_sample_dir_edit = QLineEdit(recent_sample_dir, panel)
        self._recent_sampleset_dir_edit = QLineEdit(recent_sampleset_dir, panel)
        self._window_restore_edit = QLineEdit("启动时恢复最近一次窗口布局", panel)
        self._window_restore_edit.setReadOnly(True)
        form.addRow("主题名", self._theme_name_edit)
        form.addRow("最近项目", self._recent_projects_edit)
        form.addRow("最近样本目录", self._recent_sample_dir_edit)
        form.addRow("最近样本集目录", self._recent_sampleset_dir_edit)
        form.addRow("窗口恢复策略", self._window_restore_edit)
        layout.addWidget(panel)

        support_scope = QPlainTextEdit(self)
        support_scope.setObjectName("SettingsSupportScope")
        support_scope.setReadOnly(True)
        support_scope.setPlainText(
            "\n".join(
                (
                    "当前已支持：",
                    "- 最近项目列表",
                    "- 最近样本目录",
                    "- 最近样本集目录",
                    "- 窗口布局恢复说明",
                    "- 主题名只读显示",
                    "",
                    "当前未在 GUI 中开放：",
                    "- 仓库级业务默认值",
                    "- 存储格式与单位策略",
                    "- 公开 API 行为开关",
                )
            )
        )
        layout.addWidget(support_scope)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Close, self)
        buttons.accepted.connect(self._save_preferences)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _save_preferences(self) -> None:
        if self._settings_store is not None:
            recent_projects = [
                item.strip() for item in self._recent_projects_edit.toPlainText().splitlines() if item.strip()
            ]
            self._settings_store.save_preferences(
                {
                    "theme_name": self._theme_name_edit.text().strip() or "light",
                    "recent_projects": recent_projects,
                    "recent_sample_dir": self._recent_sample_dir_edit.text().strip(),
                    "recent_sampleset_dir": self._recent_sampleset_dir_edit.text().strip(),
                }
            )
        self._session.import_state.recent_sample_source_dir = _optional_path(self._recent_sample_dir_edit.text())
        self._session.import_state.recent_sampleset_source_dir = _optional_path(self._recent_sampleset_dir_edit.text())
        self.accept()


class HelpDialog(QDialog):
    """本地帮助对话框。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        _configure_resizable_dialog(self, "帮助", 860, 620)

        layout = QVBoxLayout(self)
        summary = QLabel("当前 GUI 使用 4 页工作台和统一底部任务面板，以下说明用于帮助定位主流程和常见入口。", self)
        summary.setWordWrap(True)
        layout.addWidget(summary)

        tabs = QTabWidget(self)
        tabs.setObjectName("HelpContentTabs")
        tabs.addTab(
            _build_readonly_text(
                "\n".join(
                    (
                        "主流程：",
                        "1. 在“导入与筛选”页确认项目目录和导入来源。",
                        "2. 先做轻量预览或单位检查，再执行绑定。",
                        "3. 在“数据处理”页选择动作、范围和结果预览。",
                        "4. 在“图形绘制”页配置主题、范围和保存格式。",
                    )
                ),
                self,
            ),
            "主流程",
        )
        tabs.addTab(
            _build_readonly_text(
                "\n".join(
                    (
                        "页面说明：",
                        "- 总览：查看当前项目、主样本集、能力快照与下一步。",
                        "- 导入与筛选：接入、检查、预览和子集管理。",
                        "- 数据处理：处理动作、参数和结果预览。",
                        "- 图形绘制：绘图配置、画布预览和结果摘要。",
                    )
                ),
                self,
            ),
            "页面说明",
        )
        tabs.addTab(
            _build_readonly_text(
                "\n".join(
                    (
                        "界面约定：",
                        "- 左侧对象树用于定位主样本集、子集、图形记录和导出记录。",
                        "- 底部任务面板统一承载任务、日志、问题、导出和审查记录。",
                        "- 菜单栏提供页面切换、日志详情和长任务进度入口。",
                    )
                ),
                self,
            ),
            "界面约定",
        )
        layout.addWidget(tabs, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)


class ImportPreviewDialog(QDialog):
    """导入预览窗口。"""

    def __init__(self, session: ProjectSession, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        _configure_resizable_dialog(self, "导入文件预览", 900, 620)

        layout = QVBoxLayout(self)
        state = session.import_state

        summary = QLabel(self)
        summary.setObjectName("ImportPreviewSummary")
        summary.setWordWrap(True)
        source_text = "-"
        if state.sample_batch_paths:
            source_text = f"已选择 {len(state.sample_batch_paths)} 个 CSV 文件"
        elif state.source_path is not None:
            source_text = str(state.source_path)
        summary.setText(
            "\n".join(
                (
                    f"项目：{session.project_name}",
                    f"导入类型：{state.import_kind.value}",
                    f"来源：{source_text}",
                    f"状态：{state.last_success or state.last_error or '执行预览或单位检查后，这里会同步显示摘要。'}",
                )
            )
        )
        layout.addWidget(summary)

        tabs = QTabWidget(self)
        tabs.setObjectName("ImportPreviewTabs")
        tabs.addTab(
            _build_single_column_table(state.preview_lines, empty_text="执行预览后在这里显示导入摘要"), "预览摘要"
        )
        tabs.addTab(_build_single_column_table(state.unit_lines, empty_text="执行单位检查后在这里显示结果"), "单位检查")
        parameter_lines = state.parameter_lines + state.timing_lines if state.timing_lines else state.parameter_lines
        tabs.addTab(
            _build_single_column_table(parameter_lines, empty_text="检查完成后在这里显示参数与耗时"), "参数与耗时"
        )
        layout.addWidget(tabs, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)


class LongTaskProgressDialog(QDialog):
    """长任务进度窗。"""

    def __init__(
        self,
        session: ProjectSession,
        cancel_callback: Callable[[], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._session = session
        self._cancel_callback = cancel_callback
        _configure_resizable_dialog(self, "任务进度", 560, 240)
        layout = QVBoxLayout(self)
        self._title = QLabel(self)
        self._title.setWordWrap(True)
        layout.addWidget(self._title)
        self._detail = QLabel(self)
        self._detail.setWordWrap(True)
        layout.addWidget(self._detail)
        self._progress = QProgressBar(self)
        layout.addWidget(self._progress)
        buttons = QHBoxLayout()
        self._cancel_button = QPushButton("中止", self)
        self._cancel_button.clicked.connect(self._request_cancel)
        buttons.addWidget(self._cancel_button)
        self._close_button = QPushButton("关闭", self)
        self._close_button.clicked.connect(self.accept)
        buttons.addWidget(self._close_button)
        layout.addLayout(buttons)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._timer.start(150)
        self._refresh()

    def _request_cancel(self) -> None:
        if self._cancel_callback is not None:
            self._cancel_callback()
        self._refresh()

    def _refresh(self) -> None:
        state = self._session.import_state
        title = state.progress_text if state.busy else "当前没有运行中的导入任务。"
        detail = state.busy_detail or state.last_cleanup_status or "底部任务区会显示最近一次导入、预览或失败记录。"
        self._title.setText(title)
        self._detail.setText(detail)
        if state.busy:
            if state.progress_total in {None, 0}:
                self._progress.setRange(0, 0)
            else:
                self._progress.setRange(0, state.progress_total)
                self._progress.setValue(state.progress_current or 0)
        else:
            self._progress.setRange(0, 1)
            self._progress.setValue(1 if self._session.tasks else 0)
        self._cancel_button.setText("中止" if state.cancellable else "收尾中不可中止")
        self._cancel_button.setVisible(state.busy)
        self._cancel_button.setEnabled(state.busy and state.cancellable and not state.cancel_requested)

    def closeEvent(self, event: object) -> None:  # type: ignore[override]
        self._timer.stop()
        super().closeEvent(event)


class FigurePreviewDialog(QDialog):
    """大图预览窗。"""

    def __init__(self, figure: Figure | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        _configure_resizable_dialog(self, "大图预览", 960, 680)
        layout = QVBoxLayout(self)

        self._status_label = QLabel(self)
        self._status_label.setWordWrap(True)
        layout.addWidget(self._status_label)

        self._toolbar_host = QWidget(self)
        self._toolbar_host.setObjectName("FigurePreviewToolbarHost")
        toolbar_layout = QVBoxLayout(self._toolbar_host)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._toolbar_host)

        self._canvas_host = QWidget(self)
        self._canvas_host.setObjectName("FigurePreviewCanvasHost")
        canvas_layout = QVBoxLayout(self._canvas_host)
        canvas_layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._canvas_host, 1)

        self._canvas = FigureCanvasQTAgg(_clone_preview_figure(figure))
        self._toolbar = NavigationToolbar2QT(self._canvas, self)
        ThemeManager().apply_plot_toolbar(self._toolbar)
        toolbar_layout.addWidget(self._toolbar)
        canvas_layout.addWidget(self._canvas)

        self._status_label.setText(
            "当前显示最近一次图形预览的只读大图。" if figure is not None else "生成图形后可在这里查看大图预览。"
        )


class ExportPrecheckDialog(QDialog):
    """导出预检窗。"""

    def __init__(self, session: ProjectSession, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        _configure_resizable_dialog(self, "导出预检", 820, 560)

        layout = QVBoxLayout(self)
        state = session.export_state

        summary = QLabel(self)
        summary.setObjectName("ExportPrecheckSummary")
        summary.setWordWrap(True)
        summary.setText(
            "\n".join(
                (
                    f"项目：{session.project_name}",
                    f"校验状态：{'通过' if state.validated else '未通过'}",
                    f"目标路径：{state.output_path or state.last_output_path or session.export_dir}",
                    f"待补算动作：{state.pending_generation_action or '-'}",
                )
            )
        )
        layout.addWidget(summary)

        missing_group = QGroupBox("缺失项", self)
        missing_layout = QVBoxLayout(missing_group)
        self._missing_list = QListWidget(missing_group)
        self._missing_list.setObjectName("ExportPrecheckMissingList")
        if state.missing_requirements:
            for item in state.missing_requirements:
                QListWidgetItem(item, self._missing_list)
        else:
            QListWidgetItem("当前没有缺失项，可直接继续导出。", self._missing_list)
        missing_layout.addWidget(self._missing_list)
        layout.addWidget(missing_group, 1)

        detail = QLabel(self)
        detail.setWordWrap(True)
        detail.setText(
            "\n".join(
                (
                    f"最近结果：{state.last_message or '确认参数后可执行导出'}",
                    f"失败信息：{state.last_failure_message or '-'}",
                    f"缺口说明：{state.missing_reason or '-'}",
                    f"最近耗时：{state.last_duration_ms} ms",
                )
            )
        )
        layout.addWidget(detail)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)


class LogDetailDialog(TableDialog):
    """日志详情窗。"""

    def __init__(self, session: ProjectSession, parent: QWidget | None = None) -> None:
        rows = [(item.timestamp, item.level, item.logger_name, item.message) for item in session.logs]
        super().__init__("日志详情", ("时间", "级别", "来源", "消息"), rows, parent)


class CodeReviewResultDialog(QDialog):
    """代码审查结果窗。"""

    def __init__(self, session: ProjectSession, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        _configure_resizable_dialog(self, "代码审查结果", 860, 540)

        layout = QVBoxLayout(self)
        summary = QLabel(self)
        summary.setObjectName("CodeReviewSummary")
        summary.setWordWrap(True)
        summary.setText(
            f"当前共有 {len(session.reviews)} 条审查记录。"
            if session.reviews
            else "当前还没有审查记录，运行审查后会在这里汇总。"
        )
        layout.addWidget(summary)

        rows = [(item.status, item.title, item.summary) for item in session.reviews]
        table = QTableWidget(self)
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels(["状态", "标题", "摘要"])
        table.setRowCount(max(1, len(rows)))
        if rows:
            for row_index, row in enumerate(rows):
                for column_index, value in enumerate(row):
                    table.setItem(row_index, column_index, QTableWidgetItem(value))
        else:
            table.setItem(0, 0, QTableWidgetItem("无"))
            table.setItem(0, 1, QTableWidgetItem("当前无审查记录"))
            table.setItem(0, 2, QTableWidgetItem("请从底部审查记录或后续检查流程获取结果。"))
        table.resizeColumnsToContents()
        layout.addWidget(table, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)


class ResultPreviewDialog(QDialog):
    """处理结果预览窗。"""

    def __init__(self, session: ProjectSession, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        _configure_resizable_dialog(self, "处理结果预览", 920, 600)

        layout = QVBoxLayout(self)
        state = session.processing_state

        summary = QLabel(self)
        summary.setWordWrap(True)
        summary.setText(
            "\n".join(
                (
                    f"当前动作：{state.current_action or '-'}",
                    f"结果摘要：{state.last_message or '生成预览表或执行分析后在这里汇总。'}",
                    f"最近预览：{state.preview_title or '-'}",
                )
            )
        )
        layout.addWidget(summary)

        self._tabs = QTabWidget(self)
        self._tabs.setObjectName("ResultPreviewTabs")
        self._tabs.addTab(_build_result_table(state.scalar_rows, self), "标量结果")
        self._tabs.addTab(_build_result_table(state.series_rows, self), "序列结果")
        self._tabs.addTab(_build_result_table(state.peaks_rows, self), "峰值结果")
        layout.addWidget(self._tabs, 1)


def _build_readonly_text(body: str, parent: QWidget) -> QWidget:
    container = QWidget(parent)
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    text = QPlainTextEdit(body, container)
    text.setReadOnly(True)
    layout.addWidget(text)
    return container


def _build_single_column_table(lines: tuple[str, ...], *, empty_text: str) -> QWidget:
    table = QTableWidget()
    table.setColumnCount(1)
    table.setHorizontalHeaderLabels(["内容"])
    effective_lines = lines or (empty_text,)
    table.setRowCount(len(effective_lines))
    for row_index, line in enumerate(effective_lines):
        table.setItem(row_index, 0, QTableWidgetItem(line))
    table.resizeColumnsToContents()
    return table


def _optional_path(text: str) -> Path | None:
    stripped = text.strip()
    return Path(stripped).resolve() if stripped else None


def _clone_preview_figure(source: Figure | None) -> Figure:
    """克隆预览图为只读画布。"""

    preview = Figure(figsize=(8.4, 5.6))
    axis = preview.subplots()
    ThemeManager().apply_plot_figure(preview)
    axis.set_axis_off()
    if source is None:
        axis.text(0.5, 0.5, "暂无图形预览", ha="center", va="center", transform=axis.transAxes)
        return preview

    buffer = BytesIO()
    source.savefig(buffer, format="png", bbox_inches="tight")
    buffer.seek(0)
    image = imread(buffer)
    axis.imshow(image)
    axis.set_axis_off()
    return preview


def _build_result_table(rows: tuple[tuple[str, ...], ...], parent: QWidget) -> QWidget:
    """构造结果表。"""

    table = QTableWidget(parent)
    if rows:
        column_count = max(len(row) for row in rows)
        table.setColumnCount(column_count)
        table.setHorizontalHeaderLabels([f"列 {index + 1}" for index in range(column_count)])
        table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            for column_index, value in enumerate(row):
                table.setItem(row_index, column_index, QTableWidgetItem(value))
    else:
        table.setColumnCount(1)
        table.setHorizontalHeaderLabels(["状态"])
        table.setRowCount(1)
        table.setItem(0, 0, QTableWidgetItem("当前无结果"))
    table.resizeColumnsToContents()
    return table
