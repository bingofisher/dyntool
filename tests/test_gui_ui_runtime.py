"""GUI 运行时行为测试。"""

from __future__ import annotations

import os
from pathlib import Path

from matplotlib.figure import Figure
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QImage
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QListWidget,
    QPlainTextEdit,
    QPushButton,
    QTabWidget,
    QTableWidget,
    QWidget,
)

from dyntool_gui.main_window import MainWindow
from dyntool_gui.screenshot import GuiScreenshotOptions, capture_main_window_screenshot, resolve_gui_font_family
from dyntool_gui.session import ProjectSession
from dyntool_gui.theme import ThemeManager
from dyntool_gui.widgets import (
    CodeReviewResultDialog,
    ExportPrecheckDialog,
    FigurePreviewDialog,
    HelpDialog,
    ImportPreviewDialog,
    LongTaskProgressDialog,
    PlaceholderDialog,
    PlottingWorkspace,
    ResultPreviewDialog,
    SettingsDialog,
)


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    """提供测试所需的 QApplication。"""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_plotting_workspace_mounts_canvas_hosts_without_right_facts_panel(qapp: QApplication) -> None:
    """图形页应保留画布宿主，但不再挂载右侧 facts panel。"""

    del qapp
    widget = PlottingWorkspace()

    assert widget._toolbar is not None
    assert widget._canvas is not None
    assert widget.findChild(QWidget, "PlottingFactsPanel") is None


def test_theme_qss_defines_chinese_font_fallback_chain(qapp: QApplication) -> None:
    """Qt 全局主题应固定中文字体链，避免截图出现无法渲染的方框。"""

    del qapp
    qss = ThemeManager().build_qss()

    assert "font-family" in qss
    assert "Microsoft YaHei" in qss
    assert "Noto Sans SC" in qss
    assert resolve_gui_font_family()


def test_internal_gui_screenshot_captures_rendered_png(qapp: QApplication, tmp_path: Path) -> None:
    """内部截图入口应直接渲染 MainWindow，并输出有效 PNG。"""

    del qapp
    target = tmp_path / "gui-screenshot.png"

    output = capture_main_window_screenshot(
        GuiScreenshotOptions(
            output_path=target,
            demo_key="generic",
            module_key="plotting",
            width=1280,
            height=720,
        )
    )

    image = QImage(str(output))
    assert output == target.resolve()
    assert output.exists()
    assert not image.isNull()
    assert image.width() == 1280
    assert image.height() == 720


def test_main_window_layout_audit_covers_maximize_size_and_dock_restore(
    monkeypatch: pytest.MonkeyPatch, qapp: QApplication
) -> None:
    """主窗口巡检应覆盖默认最大化、推荐尺寸和 dock 显隐恢复。"""

    del qapp
    from dyntool_gui import main_window as main_window_module

    class _FakeScreen:
        def availableGeometry(self) -> QRect:
            return QRect(0, 0, 2560, 1440)

    monkeypatch.setattr(main_window_module.QGuiApplication, "primaryScreen", lambda: _FakeScreen())
    window = MainWindow(ProjectSession.build_demo())

    recommended_width, recommended_height = window._recommended_window_size()
    assert recommended_width >= 2000
    assert recommended_height >= 1180
    assert bool(window.windowState() & Qt.WindowState.WindowMaximized)

    assert window.left_dock.toggleViewAction().text()
    assert window.bottom_dock.toggleViewAction().text()

    window.left_dock.hide()
    window.bottom_dock.hide()
    assert window.left_dock.isHidden()
    assert window.bottom_dock.isHidden()

    window.left_dock.show()
    window.bottom_dock.show()
    assert not window.left_dock.isHidden()
    assert not window.bottom_dock.isHidden()

    window.left_dock.hide()
    window.bottom_dock.hide()

    window._restore_default_layout()

    assert window.left_dock.isHidden()
    assert not window.bottom_dock.isHidden()
    assert bool(window.windowState() & Qt.WindowState.WindowMaximized)
    assert window.workspace.currentIndex() == 0


def test_primary_dialogs_remain_resizable_after_manual_resize(qapp: QApplication) -> None:
    """关键对话框应允许用户手动拉伸，而不是固定尺寸窗口。"""

    del qapp
    session = ProjectSession.build_demo()
    dialogs = (
        SettingsDialog(session),
        HelpDialog(),
        ImportPreviewDialog(session),
        LongTaskProgressDialog(session),
        FigurePreviewDialog(),
        ExportPrecheckDialog(session),
        CodeReviewResultDialog(session),
        ResultPreviewDialog(session),
    )

    for dialog in dialogs:
        original_size = dialog.size()
        target_width = original_size.width() + 120
        target_height = original_size.height() + 80

        assert dialog.isSizeGripEnabled()
        assert dialog.maximumWidth() > dialog.minimumWidth()
        assert dialog.maximumHeight() > dialog.minimumHeight()

        dialog.resize(target_width, target_height)

        assert dialog.width() >= target_width
        assert dialog.height() >= target_height


def test_main_flow_buttons_are_present_and_not_placeholder_copy(qapp: QApplication) -> None:
    """主流程按钮应提供真实动作入口，且不使用占位或后续接入文案。"""

    del qapp
    window = MainWindow(ProjectSession.build_demo())

    buttons = {button.text(): button for button in window.findChildren(QPushButton) if button.text()}
    expected_texts = {
        "接入主样本集",
        "管理子样本集",
        "开始分析",
        "快速出图",
        "去交付",
        "选择项目目录",
        "选择文件",
        "选择目录",
        "轻量预览",
        "深度检查单位",
        "绑定为当前主样本集",
        "执行分析",
        "生成预览表",
        "保存图片",
        "执行导出",
    }

    missing_texts = expected_texts - set(buttons)
    assert missing_texts == set()
    assert {"渲染", "恢复并渲染"} & set(buttons)

    forbidden_fragments = ("占位", "后续接入", "TODO", "待实现")
    for text in expected_texts:
        button = buttons[text]
        assert button.isEnabled() or text in {"绑定为当前主样本集", "保存图片", "执行导出"}
        assert all(fragment not in text for fragment in forbidden_fragments)
        assert all(fragment not in button.toolTip() for fragment in forbidden_fragments)


def test_plotting_workspace_exposes_formal_empty_state_copy(qapp: QApplication) -> None:
    """图形页空态应使用正式状态卡，而不是大面积无说明留白。"""

    del qapp
    widget = PlottingWorkspace()
    widget.load_session(ProjectSession.build_demo())

    empty_state = widget.findChild(QLabel, "PlottingEmptyStateLabel")

    assert empty_state is not None
    assert empty_state.property("cardRole") == "emptyState"
    assert "渲染" in empty_state.text()
    assert "补算" in empty_state.text()


def test_placeholder_dialog_keeps_text_template(qapp: QApplication) -> None:
    """占位对话框仍应保留文本模板能力。"""

    del qapp
    dialog = PlaceholderDialog("测试标题", "测试正文")

    body_edit = dialog.findChild(QPlainTextEdit)
    assert body_edit is not None
    assert body_edit.isReadOnly() is True
    assert body_edit.toPlainText() == "测试正文"


def test_primary_dialogs_enable_resize_grip(qapp: QApplication) -> None:
    """主流程子窗口应显式支持拖拽调整大小。"""

    del qapp
    session = ProjectSession.build_demo()
    dialogs = (
        SettingsDialog(session),
        HelpDialog(),
        ImportPreviewDialog(session),
        LongTaskProgressDialog(session),
        FigurePreviewDialog(),
        ExportPrecheckDialog(session),
        CodeReviewResultDialog(session),
        ResultPreviewDialog(session),
    )

    assert all(dialog.isSizeGripEnabled() for dialog in dialogs)


def test_figure_preview_dialog_mounts_real_preview_canvas(qapp: QApplication) -> None:
    """大图预览应加载真实 Matplotlib 预览容器，而不是纯占位文本。"""

    del qapp
    figure = Figure(figsize=(4.0, 3.0))
    axis = figure.subplots()
    axis.plot([0.0, 1.0], [0.0, 1.0])

    dialog = FigurePreviewDialog(figure=figure)

    assert dialog.findChild(QWidget, "FigurePreviewCanvasHost") is not None
    assert dialog.findChild(QWidget, "FigurePreviewToolbarHost") is not None
    assert dialog.findChildren(QPlainTextEdit) == []


def test_result_preview_dialog_mounts_real_result_tabs(qapp: QApplication) -> None:
    """结果预览应以真实结果容器承载处理结果，而不是占位对话框。"""

    del qapp
    session = ProjectSession.build_demo()
    session.set_processing_preview(
        action_name="calc_freqspec",
        message="已生成演示结果。",
        scalar_rows=(("sample_1", "1.0", "2.0"),),
        series_rows=(("sample_1", "0.1", "0.2"),),
        peaks_rows=(("sample_1", "3.0"),),
    )

    dialog = ResultPreviewDialog(session)

    tabs = dialog.findChild(QTabWidget, "ResultPreviewTabs")
    assert tabs is not None
    assert tabs.count() >= 3
    tables = dialog.findChildren(QTableWidget)
    assert len(tables) >= 3
    assert dialog.findChildren(QPlainTextEdit) == []


def test_settings_dialog_mounts_real_preference_fields(qapp: QApplication) -> None:
    """设置入口应显示真实偏好字段，而不是纯占位文本。"""

    del qapp
    session = ProjectSession.build_demo()
    session.import_state.recent_sample_source_dir = session.workdir / "imports" / "samples"
    session.import_state.recent_sampleset_source_dir = session.workdir / "imports" / "sample_sets"

    dialog = SettingsDialog(session)

    assert dialog.findChild(QWidget, "SettingsGeneralPanel") is not None
    assert dialog.findChild(QPlainTextEdit, "SettingsSupportScope") is not None
    assert dialog.findChildren(QPlainTextEdit) != []


def test_help_dialog_mounts_real_help_content(qapp: QApplication) -> None:
    """帮助入口应显示真实帮助内容区，而不是纯占位说明。"""

    del qapp
    dialog = HelpDialog()

    assert dialog.findChild(QTabWidget, "HelpContentTabs") is not None
    assert dialog.findChildren(QPlainTextEdit) != []


def test_import_preview_dialog_mounts_real_preview_containers(qapp: QApplication) -> None:
    """导入预览应显示真实摘要和表格容器，而不是占位正文。"""

    del qapp
    session = ProjectSession.build_demo()
    session.import_state.preview_lines = ("已解析 12 个样本", "检测到 7 个 metadata 字段")
    session.import_state.unit_lines = ("axis: s", "data: m/s^2")
    session.import_state.parameter_lines = ("sep=,", "header=0")
    session.import_state.timing_lines = ("预览耗时: 120 ms",)

    dialog = ImportPreviewDialog(session)

    assert dialog.findChild(QWidget, "ImportPreviewSummary") is not None
    assert dialog.findChild(QTabWidget, "ImportPreviewTabs") is not None
    assert dialog.findChildren(QTableWidget) != []


def test_import_workflow_idle_copy_is_actionable(qapp: QApplication) -> None:
    """导入页首屏文案应提示下一步，而不是重复空闲/尚未执行。"""

    del qapp
    from dyntool_gui.widgets.import_workflow import ImportWorkflowWidget

    widget = ImportWorkflowWidget()
    widget.load_session(ProjectSession.build_demo())

    assert "请选择项目目录" in widget._project_status.text()
    assert "选择文件或目录后可检查" in widget._source_hint.text()
    assert "绑定后会显示" in widget._result_label.text()
    assert "执行预览后显示摘要" in widget._preview_text.toPlainText()
    assert "可执行单位检查" in widget._units_text.toPlainText()
    assert "检查后显示参数与耗时" in widget._parameter_text.toPlainText()


def test_import_preview_dialog_empty_state_uses_readonly_container_not_placeholder(qapp: QApplication) -> None:
    """导入预览无数据时应显示空态，而不是“后续接入”占位文案。"""

    del qapp
    dialog = ImportPreviewDialog(ProjectSession.build_demo())

    tables = dialog.findChildren(QTableWidget)
    texts: list[str] = [label.text() for label in dialog.findChildren(QLabel)]
    for table in tables:
        for row in range(table.rowCount()):
            for column in range(table.columnCount()):
                item = table.item(row, column)
                if item is not None:
                    texts.append(item.text())
    joined_text = "\n".join(filter(None, texts))

    assert "后续轮次接入" not in joined_text
    assert "占位" not in joined_text


def test_export_precheck_dialog_mounts_real_precheck_containers(qapp: QApplication) -> None:
    """导出预检应显示真实校验容器，而不是占位正文。"""

    del qapp
    session = ProjectSession.build_demo()
    session.export_state.validated = False
    session.export_state.missing_requirements = ("缺少标量结果", "缺少图形输出")
    session.export_state.pending_generation_action = "calc_freqspec"
    session.export_state.output_path = str(session.export_dir / "review.xlsx")

    dialog = ExportPrecheckDialog(session)

    assert dialog.findChild(QWidget, "ExportPrecheckSummary") is not None
    assert dialog.findChild(QListWidget, "ExportPrecheckMissingList") is not None
    assert dialog.findChildren(QPlainTextEdit) == []


def test_export_precheck_dialog_empty_state_uses_status_copy_not_placeholder(qapp: QApplication) -> None:
    """导出预检无缺项时应显示当前状态文案，而不是占位说明。"""

    del qapp
    dialog = ExportPrecheckDialog(ProjectSession.build_demo())

    texts: list[str] = [label.text() for label in dialog.findChildren(QLabel)]
    missing_list = dialog.findChild(QListWidget, "ExportPrecheckMissingList")
    if missing_list is not None:
        for index in range(missing_list.count()):
            texts.append(missing_list.item(index).text())
    joined_text = "\n".join(filter(None, texts))

    assert "后续轮次接入" not in joined_text
    assert "占位" not in joined_text


def test_code_review_result_dialog_mounts_real_review_containers(qapp: QApplication) -> None:
    """代码审查结果应显示真实结果容器，而不是占位文本。"""

    del qapp
    session = ProjectSession.build_demo()

    dialog = CodeReviewResultDialog(session)

    assert dialog.findChild(QWidget, "CodeReviewSummary") is not None
    assert dialog.findChildren(QTableWidget) != []
    assert dialog.findChildren(QPlainTextEdit) == []
