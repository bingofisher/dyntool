"""底部任务与日志区。"""

from __future__ import annotations

from PySide6.QtWidgets import QAbstractItemView, QTableWidget, QTableWidgetItem, QTabWidget

from ..models import PanelDataBuilder
from ..session import ProjectSession

TAB_HEADERS: dict[str, tuple[str, ...]] = {
    "任务队列": ("任务", "状态", "进度", "说明"),
    "运行日志": ("时间", "级别", "logger", "消息"),
    "问题列表": ("状态", "主题", "说明"),
    "导出记录": ("时间", "名称", "状态", "目标"),
    "审查结论": ("状态", "标题", "摘要"),
}


class BottomPanel(QTabWidget):
    """底部多页签面板。"""

    def __init__(self, parent: object | None = None) -> None:
        super().__init__(parent)
        self._builder = PanelDataBuilder()
        self._tables: dict[str, QTableWidget] = {}
        for name, headers in TAB_HEADERS.items():
            table = QTableWidget()
            table.setColumnCount(len(headers))
            table.setHorizontalHeaderLabels(list(headers))
            table.setAlternatingRowColors(True)
            table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
            table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
            self._tables[name] = table
            self.addTab(table, name)

    def load_session(self, session: ProjectSession) -> None:
        """刷新底部表格。"""

        rows_by_name = self._builder.build_bottom_rows(session)
        for name, rows in rows_by_name.items():
            table = self._tables[name]
            table.setRowCount(len(rows))
            for row_index, row in enumerate(rows):
                for column_index, value in enumerate(row):
                    table.setItem(row_index, column_index, QTableWidgetItem(value))
            table.resizeColumnsToContents()
