"""数据导入与筛选组合工作台。"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QSplitter, QTabWidget, QVBoxLayout, QWidget

from ..layout import LANDSCAPE_1080P_PROFILE
from ..session import ProjectSession, describe_scope
from .import_workflow import ImportWorkflowWidget
from .page_header import PageHeader
from .subset_workspace import SubsetWorkspace


class ImportFilterWorkspace(QWidget):
    """合并"接入与检查"和"筛选与子集"的工作台。

    布局：左侧窄配置面板（接入来源参数）+ 右侧两 Tab（检查报告/子集管理）。
    """

    import_kind_changed = Signal(str)
    project_directory_requested = Signal()
    source_file_requested = Signal()
    source_directory_requested = Signal()
    import_preview_requested = Signal()
    import_deep_check_requested = Signal()
    import_execute_requested = Signal()
    import_cancel_requested = Signal()
    subset_preview_requested = Signal(object)
    subset_save_requested = Signal(str, str, bool)
    subset_delete_requested = Signal(str)
    subset_recalculate_requested = Signal(str)
    subset_use_scope_requested = Signal(str)
    subset_selection_requested = Signal(str)
    reset_scope_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.import_workflow = ImportWorkflowWidget(self)
        self.import_workflow.setObjectName("ImportActionRegion")
        self.import_workflow.setProperty("surfaceRole", "actionPanel")
        self.subset_workspace = SubsetWorkspace(self)
        self.subset_workspace.setObjectName("ImportResultRegion")
        self.subset_workspace.setProperty("surfaceRole", "resultPanel")
        self._page_header = PageHeader(
            "ImportFilter",
            "导入与筛选",
            "接入、检查与子样本集统一收口到当前范围。",
            self,
        )

        self.import_workflow.kind_changed.connect(self.import_kind_changed.emit)
        self.import_workflow.project_directory_requested.connect(self.project_directory_requested.emit)
        self.import_workflow.source_file_requested.connect(self.source_file_requested.emit)
        self.import_workflow.source_directory_requested.connect(self.source_directory_requested.emit)
        self.import_workflow.preview_requested.connect(self.import_preview_requested.emit)
        self.import_workflow.deep_check_requested.connect(self.import_deep_check_requested.emit)
        self.import_workflow.execute_requested.connect(self.import_execute_requested.emit)
        self.import_workflow.cancel_requested.connect(self.import_cancel_requested.emit)
        self.subset_workspace.preview_requested.connect(self.subset_preview_requested.emit)
        self.subset_workspace.save_requested.connect(self.subset_save_requested.emit)
        self.subset_workspace.delete_requested.connect(self.subset_delete_requested.emit)
        self.subset_workspace.recalculate_requested.connect(self.subset_recalculate_requested.emit)
        self.subset_workspace.use_scope_requested.connect(self.subset_use_scope_requested.emit)
        self.subset_workspace.selection_requested.connect(self.subset_selection_requested.emit)
        self.subset_workspace.reset_scope_requested.connect(self.reset_scope_requested.emit)

        self._right_tabs = QTabWidget(self)
        self._right_tabs.setObjectName("ImportRightTabs")
        self._right_tabs.addTab(self._build_check_report_tab(), "检查报告")
        self._right_tabs.addTab(self.subset_workspace, "子集管理")

        self.import_workflow.setMinimumWidth(320)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.setObjectName("ImportFilterWorkspaceSplitter")
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(6)
        splitter.addWidget(self.import_workflow)
        splitter.addWidget(self._right_tabs)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([LANDSCAPE_1080P_PROFILE.import_workflow_max_width, 1180])

        self._page_header.hide()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._page_header)
        layout.addWidget(splitter, 1)

    def _build_check_report_tab(self) -> QWidget:
        container = QWidget(self)
        container.setObjectName("ImportCheckReportTab")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        layout.addWidget(self.import_workflow._preview_group)
        layout.addWidget(self.import_workflow._result_card)
        layout.addStretch(1)
        return container

    def load_session(self, session: ProjectSession) -> None:
        """刷新组合工作台。"""

        self._page_header.set_summary_lines(
            f"范围：{describe_scope(session)}  ·  模式：{session.import_state.import_kind.value}"
        )
        self.import_workflow.load_session(session)
        self.subset_workspace.load_session(session)

        has_check = bool(session.import_state.preview_lines or session.import_state.unit_lines)
        if has_check:
            self._right_tabs.setCurrentIndex(0)

    def focus_import_workspace(self) -> None:
        """聚焦导入工作区。"""

        self.import_workflow.setFocus()

    def focus_subset_workspace(self) -> None:
        """聚焦子集工作区。"""

        self._right_tabs.setCurrentIndex(1)
        self.subset_workspace.setFocus()
