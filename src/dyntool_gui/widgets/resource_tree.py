"""左侧项目资源树。"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem

from ..models import ResourceNode, ResourceTreeBuilder
from ..session import ProjectSession


class ResourceTreeWidget(QTreeWidget):
    """资源树控件。"""

    selection_changed = Signal(str)

    def __init__(self, parent: object | None = None) -> None:
        super().__init__(parent)
        self.setHeaderHidden(True)
        self.itemSelectionChanged.connect(self._emit_selection)
        self._builder = ResourceTreeBuilder()

    def load_session(self, session: ProjectSession) -> None:
        """加载当前会话树。"""

        self.clear()
        for node in self._builder.build(session):
            self.addTopLevelItem(self._build_item(node))
        self.expandAll()
        if self.topLevelItemCount() > 0:
            self.setCurrentItem(self.topLevelItem(0))

    def _build_item(self, node: ResourceNode) -> QTreeWidgetItem:
        item = QTreeWidgetItem([node.title])
        for child in node.children:
            item.addChild(self._build_item(child))
        return item

    def _emit_selection(self) -> None:
        current = self.currentItem()
        if current is not None:
            self.selection_changed.emit(current.text(0))
