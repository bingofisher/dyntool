"""PySide6 GUI 骨架测试。"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QPushButton

from dyntool_gui.main_window import MainWindow
from dyntool_gui.session import MODULE_LABELS, ModuleKey, ProjectSession
from dyntool_gui.widgets import ModuleWorkspace


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    """提供测试所需的 QApplication。"""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_project_session_demo_switches() -> None:
    """假数据切换后主项目摘要应同步刷新。"""

    session = ProjectSession.build_demo("bridge")
    assert session.primary_sampleset.sample_count == 48
    session.switch_demo("generic")
    assert session.project_name == "通用样本项目骨架"
    assert session.primary_sampleset.sample_domain == "default"


def test_main_window_exposes_required_shell(qapp: QApplication) -> None:
    """主窗口应包含既定的骨架结构。"""

    del qapp
    window = MainWindow(ProjectSession.build_demo())

    assert window.workspace.count() == 5
    assert [window.workspace.tabText(index) for index in range(window.workspace.count())] == [
        MODULE_LABELS[ModuleKey.PROJECT],
        MODULE_LABELS[ModuleKey.IMPORT],
        MODULE_LABELS[ModuleKey.PROCESSING],
        MODULE_LABELS[ModuleKey.PLOTTING],
        MODULE_LABELS[ModuleKey.EXPORT],
    ]
    assert window.left_dock.windowTitle() == "项目资源树"
    assert window.right_dock.windowTitle() == "右侧信息区"
    assert window.bottom_dock.windowTitle() == "底部任务区"


def test_main_window_switch_demo_updates_status(qapp: QApplication) -> None:
    """切换假数据后标题与状态栏应更新。"""

    del qapp
    window = MainWindow(ProjectSession.build_demo())

    window._switch_demo("generic")

    assert "通用样本项目骨架" in window.windowTitle()
    assert "Generic-Set" in window._status_sampleset.text()


def test_module_workspace_emits_action_requested(qapp: QApplication) -> None:
    """模块页按钮应把动作统一上送。"""

    del qapp
    workspace = ModuleWorkspace()
    captured: list[str] = []

    workspace.action_requested.connect(captured.append)
    for button in workspace.findChildren(QPushButton):
        if button.text() == "刷新预览":
            button.click()
            break

    assert captured == ["刷新预览"]
