"""GUI 会话信号总线。"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal


class SessionBus(QObject):
    """会话状态变更信号总线。

    所有状态变更事件通过此对象广播。各 workspace 直接连接感兴趣的信号，
    无需经过 ModuleWorkspace 或 MainWindow 中继。
    """

    project_changed = Signal()
    primary_changed = Signal()
    import_state_changed = Signal()
    subset_state_changed = Signal()
    processing_state_changed = Signal()
    plot_state_changed = Signal()
    export_state_changed = Signal()
    resource_tree_changed = Signal()
    selection_changed = Signal()
    task_changed = Signal()
    logs_changed = Signal()
    issues_changed = Signal()

    def emit_all(self) -> None:
        """发出全部状态信号（用于 demo 切换、项目加载等场景）。"""

        self.project_changed.emit()
        self.primary_changed.emit()
        self.import_state_changed.emit()
        self.subset_state_changed.emit()
        self.processing_state_changed.emit()
        self.plot_state_changed.emit()
        self.export_state_changed.emit()
        self.resource_tree_changed.emit()
        self.selection_changed.emit()
        self.task_changed.emit()
        self.logs_changed.emit()
        self.issues_changed.emit()

    def emit_project_related(self) -> None:
        """发出项目相关信号（用于项目目录变更等场景）。"""

        self.project_changed.emit()
        self.resource_tree_changed.emit()
        self.import_state_changed.emit()
        self.subset_state_changed.emit()
        self.selection_changed.emit()
