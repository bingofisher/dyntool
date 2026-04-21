"""GUI 主窗口。"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QDockWidget, QLabel, QMainWindow, QMessageBox, QStatusBar, QToolBar, QWidget

from .session import ModuleKey, ProjectSession
from .widgets import (
    BottomPanel,
    CodeReviewResultDialog,
    ExportPrecheckDialog,
    FigurePreviewDialog,
    ImportPreviewDialog,
    InformationPanel,
    LogDetailDialog,
    LongTaskProgressDialog,
    ModuleWorkspace,
    PlaceholderDialog,
    ResourceTreeWidget,
    ResultPreviewDialog,
)


class MainWindow(QMainWindow):
    """主窗口骨架。"""

    def __init__(self, session: ProjectSession | None = None) -> None:
        super().__init__()
        self.session = session or ProjectSession.build_demo()
        self.resize(1480, 920)

        self.workspace = ModuleWorkspace(self)
        self.workspace.currentChanged.connect(self._on_module_changed)
        self.workspace.action_requested.connect(self._trigger_action)
        self.setCentralWidget(self.workspace)

        self.resource_tree = ResourceTreeWidget(self)
        self.resource_tree.selection_changed.connect(self._on_selection_changed)
        self.info_panel = InformationPanel(self)
        self.bottom_panel = BottomPanel(self)

        self.left_dock = self._build_dock("项目资源树", self.resource_tree, Qt.DockWidgetArea.LeftDockWidgetArea)
        self.right_dock = self._build_dock("右侧信息区", self.info_panel, Qt.DockWidgetArea.RightDockWidgetArea)
        self.bottom_dock = self._build_dock("底部任务区", self.bottom_panel, Qt.DockWidgetArea.BottomDockWidgetArea)

        self._build_menus()
        self._build_toolbar()
        self._build_status_bar()
        self._reload_view()

    def _build_dock(self, title: str, widget: QWidget, area: Qt.DockWidgetArea) -> QDockWidget:
        dock = QDockWidget(title, self)
        dock.setObjectName(title)
        dock.setWidget(widget)
        self.addDockWidget(area, dock)
        return dock

    def _build_menus(self) -> None:
        menu_specs = {
            "文件": ("新建项目", "打开项目", "保存项目", "另存项目", "退出"),
            "视图": ("显示/隐藏项目资源树", "显示/隐藏右侧信息区", "显示/隐藏底部任务区", "恢复默认布局"),
            "数据": ("导入 Sample", "导入 SampleSet", "预览导入文件", "检查单位", "切换桥梁假数据", "切换通用假数据"),
            "处理": ("构建子集", "运行处理", "查看结果预览"),
            "绘图": ("新建图组", "新建图任务", "绑定绘图数据", "刷新预览", "打开大图预览"),
            "工程导出": ("工程导出预检", "执行工程导出"),
            "工具": ("设置", "打开长任务进度", "查看日志详情", "代码审查结果"),
        }
        for menu_name, actions in menu_specs.items():
            menu = self.menuBar().addMenu(menu_name)
            for action_name in actions:
                action = QAction(action_name, self)
                action.triggered.connect(lambda checked=False, name=action_name: self._trigger_action(name))
                menu.addAction(action)

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("主工具栏", self)
        toolbar.setMovable(False)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar)
        for action_name in (
            "新建项目",
            "保存项目",
            "导入 Sample",
            "导入 SampleSet",
            "构建子集",
            "运行处理",
            "刷新预览",
            "工程导出预检",
            "执行工程导出",
            "打开长任务进度",
            "设置",
        ):
            action = QAction(action_name, self)
            action.triggered.connect(lambda checked=False, name=action_name: self._trigger_action(name))
            toolbar.addAction(action)

    def _build_status_bar(self) -> None:
        status = QStatusBar(self)
        self.setStatusBar(status)
        self._status_project = QLabel()
        self._status_sampleset = QLabel()
        self._status_dirty = QLabel()
        self._status_task = QLabel()
        for widget in (self._status_project, self._status_sampleset, self._status_dirty, self._status_task):
            status.addPermanentWidget(widget)

    def _reload_view(self) -> None:
        self.setWindowTitle(f"AdvDynTool GUI 骨架 - {self.session.project_name}")
        self.workspace.set_current_module(self.session.current_module)
        self.resource_tree.load_session(self.session)
        self.info_panel.load_session(self.session)
        self.bottom_panel.load_session(self.session)
        self._status_project.setText(f"工作目录: {self.session.workdir}")
        self._status_sampleset.setText(f"主 SampleSet: {self.session.primary_sampleset.name}")
        self._status_dirty.setText(f"脏状态: {'是' if self.session.dirty else '否'}")
        task_text = self.session.tasks[0].status if self.session.tasks else "空闲"
        self._status_task.setText(f"任务状态: {task_text}")

    def _on_module_changed(self, index: int) -> None:
        del index
        self.session.set_current_module(self.workspace.current_module())
        self.info_panel.load_session(self.session)

    def _on_selection_changed(self, text: str) -> None:
        self.session.set_current_selection(text)
        self.info_panel.load_session(self.session)

    def _trigger_action(self, action_name: str) -> None:
        direct_actions = {
            "显示/隐藏项目资源树": self.left_dock.toggleViewAction().trigger,
            "显示/隐藏右侧信息区": self.right_dock.toggleViewAction().trigger,
            "显示/隐藏底部任务区": self.bottom_dock.toggleViewAction().trigger,
            "恢复默认布局": self._restore_default_layout,
            "切换桥梁假数据": lambda: self._switch_demo("bridge"),
            "切换通用假数据": lambda: self._switch_demo("generic"),
            "预览导入文件": lambda: ImportPreviewDialog(self.session, self).exec(),
            "查看结果预览": lambda: ResultPreviewDialog(self).exec(),
            "打开大图预览": lambda: FigurePreviewDialog(self).exec(),
            "刷新预览": lambda: FigurePreviewDialog(self).exec(),
            "工程导出预检": lambda: ExportPrecheckDialog(self.session, self).exec(),
            "查看日志详情": lambda: LogDetailDialog(self.session, self).exec(),
            "打开长任务进度": lambda: LongTaskProgressDialog(self).exec(),
            "代码审查结果": lambda: CodeReviewResultDialog(self.session, self).exec(),
            "保存项目": self._simulate_save,
            "退出": self.close,
        }
        if action_name in direct_actions:
            direct_actions[action_name]()
            return

        detail_dialogs = {
            "设置主集": self._open_primary_sampleset_dialog,
            "设置对比集": self._open_compare_sampleset_dialog,
            "查看 metadata 字段": self._open_metadata_fields_dialog,
            "查看支持 categories": self._open_categories_dialog,
        }
        if action_name in detail_dialogs:
            detail_dialogs[action_name]()
            return

        placeholder_messages = {
            "新建项目": "首轮只提供单项目骨架，不创建真实项目目录。",
            "打开项目": "首轮只支持切换内存假数据集。",
            "另存项目": "首轮不生成真实项目文件。",
            "导入 Sample": "真实 Sample 导入、单位检测和 hook 执行将在第二轮接入。",
            "导入 SampleSet": "真实 SampleSet 导入、合并策略和预览将在第二轮接入。",
            "检查单位": "当前只保留单位检测入口，占位结果不会写回项目。",
            "试导入": "当前只保留导入试压入口，不读取真实文件。",
            "执行导入 Sample": "当前只演示 Sample 导入入口归属，不执行真实导入。",
            "执行导入 SampleSet": "当前只演示 SampleSet 导入入口归属，不执行真实导入。",
            "添加文件": "首轮不绑定文件对话框，导入文件列表仍为占位。",
            "添加目录": "首轮不绑定目录选择器，导入目录列表仍为占位。",
            "构建子集": "子集构建器壳已落位，真实筛选逻辑将在第二轮接入。",
            "运行处理": "真实 preprocess / eval / spectrum 链尚未接入。",
            "导出处理结果": "首轮只保留结果导出归属，不落地真实表格导出。",
            "新建图组": "首轮仅固定图组层级，不创建真实绘图任务。",
            "新建图任务": "首轮仅固定图任务入口，不创建真实 plotter 任务。",
            "绑定绘图数据": "真实 PlotDataset 绑定将在第二轮接入。",
            "导出当前图组": "首轮不导出真实图像文件。",
            "执行工程导出": "真实工程导出链将在第二轮接入。",
            "仅导出结果表": "首轮不生成真实统计表或报表文件。",
            "仅导出图组": "首轮不生成真实图组输出。",
            "仅导出报告包": "首轮不生成真实 report package。",
            "设置": "首轮仅保留设置入口占位。",
        }
        message = placeholder_messages.get(action_name)
        if message is not None:
            QMessageBox.information(self, action_name, message)

    def _restore_default_layout(self) -> None:
        self.left_dock.show()
        self.right_dock.show()
        self.bottom_dock.show()
        self.workspace.set_current_module(ModuleKey.PROJECT)
        self.session.set_current_module(ModuleKey.PROJECT)
        self._reload_view()

    def _switch_demo(self, demo_key: str) -> None:
        self.session.switch_demo(demo_key)
        self._reload_view()

    def _simulate_save(self) -> None:
        self.session.mark_saved("2026-04-21 18:00:00")
        self.statusBar().showMessage("项目保存动作已作为骨架占位处理。", 3000)
        self._reload_view()

    def _open_primary_sampleset_dialog(self) -> None:
        sample = self.session.primary_sampleset
        body = (
            f"当前主 SampleSet:\n- 名称: {sample.name}\n- 类型: {sample.class_name}\n"
            f"- sample_type: {sample.sample_type}\n- sample_domain: {sample.sample_domain}\n"
            "首轮不执行真实切换。"
        )
        PlaceholderDialog("主 SampleSet", body, self).exec()

    def _open_compare_sampleset_dialog(self) -> None:
        compare = self.session.compare_sampleset
        if compare is None:
            body = "当前没有对比 SampleSet，占位界面只展示空状态。"
        else:
            body = (
                f"当前对比 SampleSet:\n- 名称: {compare.name}\n- 类型: {compare.class_name}\n"
                f"- 样本数: {compare.sample_count}\n- 存储绑定: {compare.storage_binding}"
            )
        PlaceholderDialog("对比 SampleSet", body, self).exec()

    def _open_metadata_fields_dialog(self) -> None:
        fields_text = "\n".join(f"- {field}" for field in self.session.primary_sampleset.metadata_fields)
        PlaceholderDialog("metadata 字段", fields_text, self).exec()

    def _open_categories_dialog(self) -> None:
        categories = "\n".join(f"- {item}" for item in self.session.primary_sampleset.supported_categories)
        PlaceholderDialog("支持 categories", categories, self).exec()
