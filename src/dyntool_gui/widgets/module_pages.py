"""中央模块工作区。"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..layout import LANDSCAPE_2K_PROFILE
from ..session import MODULE_LABELS, ImportKind, ModuleKey, ProjectSession
from .export_workspace import ExportWorkspace
from .import_filter_workspace import ImportFilterWorkspace
from .plotting_workspace import PlottingWorkspace
from .processing_workspace import ProcessingWorkspace
from .project_overview import ProjectOverviewWidget


class ModuleWorkspace(QWidget):
    """中央任务工作区（纯导航 + 页面容器）。

    不再声明或中继任何业务信号。各子 workspace 的信号由外部直接连接。
    """

    currentChanged = Signal(int)

    def __init__(self, parent: object | None = None) -> None:
        super().__init__(parent)
        self.project_overview = ProjectOverviewWidget(self)
        self.import_filter_workspace = ImportFilterWorkspace(self)
        self.import_workflow = self.import_filter_workspace.import_workflow
        self.subset_workspace = self.import_filter_workspace.subset_workspace
        self.processing_workspace = ProcessingWorkspace(self)
        self.plotting_workspace = PlottingWorkspace(self)
        self.export_workspace = ExportWorkspace(self)

        self._pages: dict[ModuleKey, QWidget] = {
            ModuleKey.PROJECT: self.project_overview,
            ModuleKey.IMPORT: self.import_filter_workspace,
            ModuleKey.PROCESSING: self.processing_workspace,
            ModuleKey.PLOTTING: self.plotting_workspace,
        }
        self._module_order = tuple(self._pages.keys())
        self._nav_buttons: list[QPushButton] = []

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(4)

        self._context_bar = QFrame(self)
        self._context_bar.setObjectName("contextBar")
        self._context_bar.setProperty("surfaceRole", "contextBar")
        self._context_bar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._context_bar.setFixedHeight(LANDSCAPE_2K_PROFILE.context_bar_height)
        self._context_bar.setStyleSheet(
            """
            QFrame#contextBar {
                background: #1E3A8A;
                border-bottom: 1px solid #1D4ED8;
            }
            """
        )
        bar_layout = QHBoxLayout(self._context_bar)
        bar_layout.setContentsMargins(0, 0, 0, 0)
        bar_layout.setSpacing(0)
        self._context_label = QLabel("未加载项目", self._context_bar)
        self._context_label.setObjectName("ContextBarTitleLabel")
        self._context_label.setStyleSheet(
            "background-color: #1E3A8A; color: #FFFFFF; font-size: 11pt; font-weight: 600; padding-left: 16px;"
        )
        self._context_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        bar_layout.addWidget(self._context_label, 1)
        self._progress_label = QLabel("", self._context_bar)
        self._progress_label.setObjectName("ContextBarProgressLabel")
        self._progress_label.setStyleSheet(
            "background-color: #1E3A8A; color: #DBEAFE; font-size: 9pt; padding-right: 16px;"
        )
        bar_layout.addWidget(self._progress_label)
        root_layout.addWidget(self._context_bar)

        self._nav_bar = QWidget(self)
        self._nav_bar.setObjectName("ModuleNavigationBar")
        self._nav_bar.setMaximumHeight(LANDSCAPE_2K_PROFILE.nav_button_height + 6)
        self._nav_bar.setStyleSheet(
            "QWidget#ModuleNavigationBar { border-bottom: 1px solid #E2E8F0; background: #FFFFFF; }"
        )
        nav_layout = QHBoxLayout(self._nav_bar)
        nav_layout.setContentsMargins(8, 0, 8, 0)
        nav_layout.setSpacing(0)
        for index, module in enumerate(self._module_order):
            button = QPushButton(MODULE_LABELS[module], self._nav_bar)
            button.setProperty("navButton", True)
            button.setCheckable(True)
            button.setMinimumHeight(LANDSCAPE_2K_PROFILE.nav_button_height)
            button.setMaximumHeight(LANDSCAPE_2K_PROFILE.nav_button_height)
            button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            button.clicked.connect(lambda checked=False, idx=index: self.setCurrentIndex(idx))
            nav_layout.addWidget(button)
            self._nav_buttons.append(button)
        root_layout.addWidget(self._nav_bar)

        self._stack = QStackedWidget(self)
        self._stack.setObjectName("ModuleWorkspaceStack")
        for page in self._pages.values():
            self._stack.addWidget(page)
        root_layout.addWidget(self._stack, 1)

        self.setCurrentIndex(0)

    def count(self) -> int:
        """返回页面数量。"""

        return len(self._module_order)

    def tabText(self, index: int) -> str:
        """返回指定页面标签。"""

        return MODULE_LABELS[self._module_order[index]]

    def currentIndex(self) -> int:
        """返回当前页面索引。"""

        return self._stack.currentIndex()

    def setCurrentIndex(self, index: int) -> None:
        """切换当前页面。"""

        if index < 0 or index >= self.count():
            return
        if index == self._stack.currentIndex():
            self._sync_nav_state(index)
            return
        self._stack.setCurrentIndex(index)
        self._sync_nav_state(index)
        self.currentChanged.emit(index)

    def current_module(self) -> ModuleKey:
        """返回当前模块。"""

        return self._module_order[self.currentIndex()]

    def set_current_module(self, module: ModuleKey) -> None:
        """切换当前模块。"""

        if module in {ModuleKey.SUBSET, ModuleKey.EXPORT}:
            module = ModuleKey.IMPORT if module is ModuleKey.SUBSET else ModuleKey.PLOTTING
        self.setCurrentIndex(self._module_order.index(module))

    def set_import_kind(self, import_kind: ImportKind) -> None:
        """更新导入工作流的导入类型。"""

        self.import_workflow.set_import_kind(import_kind)

    def load_session(self, session: ProjectSession) -> None:
        """刷新各任务页。"""

        self.project_overview.load_session(session)
        self.import_filter_workspace.load_session(session)
        self.processing_workspace.load_session(session)
        self.plotting_workspace.load_session(session)
        self.export_workspace.load_session(session)
        self.set_current_module(session.current_module)

    def update_context(
        self,
        project_name: str,
        primary_name: str,
        dirty: bool,
        progress_text: str = "",
    ) -> None:
        """更新顶部项目上下文条。"""

        dirty_mark = " ●" if dirty else ""
        text = f"{project_name}  ·  主集: {primary_name}{dirty_mark}"
        self._context_label.setText(text)
        self._progress_label.setText(progress_text)

    def _sync_nav_state(self, current_index: int) -> None:
        for index, button in enumerate(self._nav_buttons):
            checked = index == current_index
            button.blockSignals(True)
            button.setChecked(checked)
            button.setProperty("current", checked)
            button.style().unpolish(button)
            button.style().polish(button)
            button.blockSignals(False)
