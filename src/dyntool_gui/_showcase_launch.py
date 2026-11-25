"""正式展示项目的桌面启动适配，属于 GUI Internal API。"""

from __future__ import annotations

from pathlib import Path
import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from dyntool import DefaultSampleSet, SampleDomain
from dyntool.storage import SampleLoadMode, StorageScheme

from .main_window import MainWindow
from .persistence import AppSettingsStore, ProjectFileStore
from .session import ModuleKey, build_capability_snapshot


class _BuildingShowcaseLauncher:
    """按真实项目恢复数据，并沿用普通窗口的绘图和保存流程。"""

    def make_window(self, project_file: Path) -> MainWindow:
        """配置默认隔振前后时程比较，不恢复占位演示状态。"""

        session = ProjectFileStore().load(project_file)
        if session.analysis_data.path is None:
            raise ValueError("展示项目缺少已保存的分析仓库引用。")
        session.primary_runtime = DefaultSampleSet.from_samples(None, sample_domain=SampleDomain.VIBRATION_TEST).load(
            session.analysis_data.path, storage_scheme=StorageScheme.SET_SQLITE_H5, load_mode=SampleLoadMode.EAGER
        )
        session.capability_snapshot = build_capability_snapshot(session.primary_runtime)
        session.current_module = ModuleKey.PLOTTING
        session.plot_state.plot_mode = "multi_sample"
        session.plot_state.source_kind = "sample_model"
        session.plot_state.source_name = "accel"
        window = MainWindow(session, settings_store=AppSettingsStore(project_file.parent / "gui_settings.ini"))
        window._current_project_file = project_file
        QTimer.singleShot(0, window._render_plot)
        return window


def create_showcase_window(project_file: Path) -> MainWindow:
    """创建自动渲染建筑展示的窗口，调用方需已有 QApplication。

    Args:
        project_file: 建筑展示生成器输出的项目文件。

    Returns:
        已配置真实数据和默认绘图请求的窗口。
    """

    return _BuildingShowcaseLauncher().make_window(project_file.resolve())


def open_showcase(project_file: Path) -> int:
    """启动建筑展示 GUI 的事件循环。

    Args:
        project_file: 已生成的项目文件。

    Returns:
        Qt 应用退出码。
    """

    app = QApplication.instance() or QApplication(sys.argv)
    window = create_showcase_window(project_file)
    window.show()
    return app.exec()
