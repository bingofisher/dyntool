"""左侧项目资源树。"""

from __future__ import annotations

from PySide6.QtCore import QModelIndex, QSize, Qt, Signal
from PySide6.QtWidgets import QTreeView, QVBoxLayout, QWidget

from ..models import ResourceTreeBuilder, ResourceTreeModel, ResourceTreeSnapshot
from ..session import ProjectSession


class ResourceTreeWidget(QWidget):
    """资源树视图。"""

    selection_changed = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._builder = ResourceTreeBuilder()
        self._model = ResourceTreeModel(self)
        self._tree_view = QTreeView(self)
        self._tree_view.setHeaderHidden(True)
        self._tree_view.setEditTriggers(QTreeView.EditTrigger.NoEditTriggers)
        self._tree_view.setUniformRowHeights(True)
        self._tree_view.setIndentation(10)
        self._tree_view.setIconSize(QSize(12, 12))
        self._tree_view.setTextElideMode(Qt.TextElideMode.ElideRight)
        self._tree_view.setStyleSheet(
            """
            QTreeView {
                outline: 0;
            }
            QTreeView::item {
                min-height: 18px;
                padding: 0px 2px;
            }
            QTreeView::branch {
                width: 10px;
            }
            """
        )
        self._tree_view.setModel(self._model)
        self._tree_view.selectionModel().selectionChanged.connect(self._emit_selection)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._tree_view)
        self._selected_key = ""

    def load_session(self, session: ProjectSession) -> None:
        """根据当前会话刷新资源树。"""

        self.apply_snapshot(self._builder.build_snapshot(session))

    def apply_snapshot(self, snapshot: ResourceTreeSnapshot) -> None:
        """应用资源树快照。"""

        self._model.set_snapshot(snapshot)
        self._tree_view.expandToDepth(0)
        self._restore_selection()

    def model(self) -> ResourceTreeModel:
        """返回当前资源树模型。"""

        return self._model

    def card_title(self) -> str:
        """兼容测试中的简单探测。"""

        current = self._tree_view.currentIndex()
        return str(self._model.data(current, Qt.ItemDataRole.DisplayRole) or "")

    def _restore_selection(self) -> None:
        target = self._model.index_for_key(self._selected_key) if self._selected_key else QModelIndex()
        if not target.isValid() and self._model.rowCount() > 0:
            target = self._model.index(0, 0)
        if target.isValid():
            self._expand_to_index(target)
            self._tree_view.setCurrentIndex(target)
            self._emit_selection()

    def _expand_to_index(self, index: QModelIndex) -> None:
        """仅展开当前选中节点所在路径，避免默认整树摊开。"""

        current = index
        while current.isValid():
            self._tree_view.expand(current)
            current = current.parent()

    def _emit_selection(self) -> None:
        current = self._tree_view.currentIndex()
        if not current.isValid():
            return
        self._selected_key = self._model.key_for_index(current)
        title = self._model.data(current, Qt.ItemDataRole.DisplayRole)
        if isinstance(title, str):
            self.selection_changed.emit(title)
