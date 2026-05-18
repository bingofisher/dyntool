"""资源树模型。"""

from __future__ import annotations

from dataclasses import dataclass, field

from PySide6.QtCore import QAbstractItemModel, QModelIndex, QObject, Qt

from ..session import PlotNode, ProjectSession


@dataclass(slots=True)
class ResourceNode:
    """资源树节点。"""

    key: str
    title: str
    children: tuple["ResourceNode", ...] = ()


@dataclass(slots=True)
class ResourceTreeSnapshot:
    """资源树快照。"""

    nodes: tuple[ResourceNode, ...]


@dataclass(slots=True)
class _TreeItem:
    """资源树运行时节点。"""

    node: ResourceNode
    parent: "_TreeItem | None" = None
    children: list["_TreeItem"] = field(default_factory=list)

    def row(self) -> int:
        """返回当前节点在父节点中的行号。"""

        if self.parent is None:
            return 0
        return self.parent.children.index(self)


class ResourceTreeBuilder:
    """资源树快照构造器。"""

    def build_snapshot(self, session: ProjectSession) -> ResourceTreeSnapshot:
        """根据会话构造资源树快照。"""

        subset_nodes = tuple(
            ResourceNode(
                f"subset.item.{index}",
                item.name,
                (
                    ResourceNode(f"subset.item.{index}.count", f"样本数量: {item.sample_count}"),
                    ResourceNode(f"subset.item.{index}.updated", f"更新时间: {item.updated_at}"),
                ),
            )
            for index, item in enumerate(session.subset_state.subsets)
        ) or (ResourceNode("subset.empty", "尚未保存子样本集"),)

        other_sampleset_nodes: list[ResourceNode] = []
        if session.compare_sampleset is not None:
            other_sampleset_nodes.append(
                ResourceNode(
                    "other.compare",
                    f"对比集: {session.compare_sampleset.name}",
                    (
                        ResourceNode("other.compare.count", f"样本数量: {session.compare_sampleset.sample_count}"),
                        ResourceNode("other.compare.domain", f"域: {session.compare_sampleset.sample_domain}"),
                    ),
                )
            )
        for index, ss in enumerate(session.other_samplesets):
            other_sampleset_nodes.append(
                ResourceNode(
                    f"other.extra.{index}",
                    ss.name,
                    (
                        ResourceNode(f"other.extra.{index}.count", f"样本数量: {ss.sample_count}"),
                        ResourceNode(f"other.extra.{index}.domain", f"域: {ss.sample_domain}"),
                    ),
                )
            )
        if not other_sampleset_nodes:
            other_sampleset_nodes.append(ResourceNode("other.empty", "暂无其他集合"))

        nodes: list[ResourceNode] = [
            ResourceNode(
                "sampleset.primary",
                "当前主样本集",
                (
                    ResourceNode("sampleset.primary.name", session.primary_sampleset.name),
                    ResourceNode(
                        "sampleset.primary.count",
                        f"样本数量: {session.primary_sampleset.sample_count}",
                    ),
                    ResourceNode(
                        "sampleset.primary.class_name",
                        f"类型: {session.primary_sampleset.class_name}",
                    ),
                    ResourceNode(
                        "sampleset.primary.domain",
                        f"域: {session.primary_sampleset.sample_domain}",
                    ),
                ),
            ),
            ResourceNode("subset.root", "子集集合", subset_nodes),
            ResourceNode("other.root", "其他集合", tuple(other_sampleset_nodes)),
            ResourceNode(
                "plot.root",
                "图形记录",
                tuple(
                    self._convert_plot_node(node, prefix=f"plot.{index}")
                    for index, node in enumerate(session.plot_tree)
                ),
            ),
            ResourceNode(
                "export.root",
                "导出记录",
                tuple(ResourceNode(f"export.record.{index}", item.name) for index, item in enumerate(session.exports)),
            ),
        ]
        return ResourceTreeSnapshot(nodes=tuple(nodes))

    def build(self, session: ProjectSession) -> tuple[ResourceNode, ...]:
        """兼容旧调用，返回根节点元组。"""

        return self.build_snapshot(session).nodes

    def _convert_plot_node(self, node: PlotNode, *, prefix: str) -> ResourceNode:
        """转换绘图树节点。"""

        return ResourceNode(
            prefix,
            node.title,
            tuple(
                self._convert_plot_node(child, prefix=f"{prefix}.{index}") for index, child in enumerate(node.children)
            ),
        )


class ResourceTreeModel(QAbstractItemModel):
    """资源树 item model。"""

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._snapshot = ResourceTreeSnapshot(nodes=())
        self._root_item = _TreeItem(ResourceNode("root", "root"))
        self._items_by_key: dict[str, _TreeItem] = {}

    def set_snapshot(self, snapshot: ResourceTreeSnapshot) -> None:
        """应用新的资源树快照。"""

        self.beginResetModel()
        self._snapshot = snapshot
        self._root_item = _TreeItem(ResourceNode("root", "root"))
        self._items_by_key.clear()
        for node in snapshot.nodes:
            self._root_item.children.append(self._build_item(node, self._root_item))
        self.endResetModel()

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        del parent
        return 1

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        item = self._item_from_index(parent)
        return len(item.children)

    def index(self, row: int, column: int, parent: QModelIndex = QModelIndex()) -> QModelIndex:  # noqa: N802
        if row < 0 or column != 0:
            return QModelIndex()
        parent_item = self._item_from_index(parent)
        if row >= len(parent_item.children):
            return QModelIndex()
        child = parent_item.children[row]
        return self.createIndex(row, column, child)

    def parent(self, index: QModelIndex) -> QModelIndex:  # noqa: N802
        if not index.isValid():
            return QModelIndex()
        item = self._item_from_index(index)
        parent_item = item.parent
        if parent_item is None or parent_item is self._root_item:
            return QModelIndex()
        return self.createIndex(parent_item.row(), 0, parent_item)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> str | None:  # noqa: N802
        if not index.isValid():
            return None
        item = self._item_from_index(index)
        if role == Qt.ItemDataRole.DisplayRole:
            return item.node.title
        if role == Qt.ItemDataRole.ToolTipRole:
            return item.node.title
        return None

    def headerData(  # noqa: N802
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> str | None:
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole and section == 0:
            return "资源"
        return None

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:  # noqa: N802
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable

    def index_for_key(self, key: str) -> QModelIndex:
        """按稳定键查找索引。"""

        item = self._items_by_key.get(key)
        if item is None or item.parent is None:
            return QModelIndex()
        return self.createIndex(item.row(), 0, item)

    def key_for_index(self, index: QModelIndex) -> str:
        """返回索引对应的稳定键。"""

        if not index.isValid():
            return ""
        return self._item_from_index(index).node.key

    def _build_item(self, node: ResourceNode, parent: _TreeItem) -> _TreeItem:
        item = _TreeItem(node=node, parent=parent)
        self._items_by_key[node.key] = item
        item.children.extend(self._build_item(child, item) for child in node.children)
        return item

    def _item_from_index(self, index: QModelIndex) -> _TreeItem:
        if index.isValid():
            item = index.internalPointer()
            if isinstance(item, _TreeItem):
                return item
        return self._root_item
