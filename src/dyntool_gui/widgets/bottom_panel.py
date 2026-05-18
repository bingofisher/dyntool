"""底部任务与日志区。"""

from __future__ import annotations

from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QTableView, QTabWidget

from ..managers.task_manager import TaskManager
from ..models import ExportTableModel, IssueTableModel, LogTableModel, TaskTableModel
from ..session import ProjectSession


class BottomPanel(QTabWidget):
    """底部多页签面板。"""

    def __init__(self, parent: object | None = None) -> None:
        super().__init__(parent)
        self._task_manager = TaskManager()
        self._views: dict[str, QTableView] = {}
        self._models = {
            "任务队列": TaskTableModel(self),
            "运行日志": LogTableModel(self),
            "问题列表": IssueTableModel(self),
            "导出记录": ExportTableModel(self),
        }
        for name, model in self._models.items():
            table = QTableView(self)
            table.setModel(model)
            table.setAlternatingRowColors(True)
            table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
            table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
            table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
            table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
            table.verticalHeader().setVisible(False)
            table.verticalHeader().setDefaultSectionSize(22)
            table.horizontalHeader().setFixedHeight(24)
            self._views[name] = table
            self.addTab(table, name)

    def load_session(self, session: ProjectSession) -> None:
        """刷新全部底部表格。"""

        snapshot = self._task_manager.build_snapshot(session)
        self._models["任务队列"].set_rows(snapshot.tasks)
        self._models["运行日志"].set_rows(snapshot.logs)
        self._models["问题列表"].set_rows(snapshot.issues)
        self._models["导出记录"].set_rows(snapshot.exports)

    def load_task_rows(self, session: ProjectSession) -> None:
        """仅刷新任务表。"""

        self._models["任务队列"].set_rows(self._task_manager.build_snapshot(session).tasks)

    def load_log_rows(self, session: ProjectSession) -> None:
        """仅刷新日志表。"""

        self._models["运行日志"].set_rows(self._task_manager.build_snapshot(session).logs)

    def load_issue_rows(self, session: ProjectSession) -> None:
        """仅刷新问题表。"""

        self._models["问题列表"].set_rows(self._task_manager.build_snapshot(session).issues)

    def table_model(self, tab_name: str) -> object:
        """返回指定页签的表模型。"""

        return self._models[tab_name]
