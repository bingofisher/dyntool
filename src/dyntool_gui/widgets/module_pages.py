"""模块页骨架。"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QGroupBox,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..session import MODULE_LABELS, ModuleKey


class ModuleWorkspace(QTabWidget):
    """中央模块工作区。"""

    action_requested = Signal(str)

    def __init__(self, parent: object | None = None) -> None:
        super().__init__(parent)
        self._action_buttons: list[QPushButton] = []
        self._pages: dict[ModuleKey, QWidget] = {
            ModuleKey.PROJECT: self._build_project_page(),
            ModuleKey.IMPORT: self._build_import_page(),
            ModuleKey.PROCESSING: self._build_processing_page(),
            ModuleKey.PLOTTING: self._build_plotting_page(),
            ModuleKey.EXPORT: self._build_export_page(),
        }
        for key, page in self._pages.items():
            self.addTab(page, MODULE_LABELS[key])

    def current_module(self) -> ModuleKey:
        """返回当前模块键。"""

        return list(self._pages)[self.currentIndex()]

    def set_current_module(self, module: ModuleKey) -> None:
        """切换当前模块。"""

        self.setCurrentIndex(list(self._pages).index(module))

    def _build_project_page(self) -> QWidget:
        page = QWidget()
        layout = QGridLayout(page)
        layout.addWidget(self._group("项目本体", ("项目总览", "工作目录", "默认导出目录", "最近保存时间")), 0, 0)
        layout.addWidget(
            self._group("主 SampleSet 信息", ("名称 / 类名 / sample_type", "sample_domain", "metadata 类型与字段")),
            0,
            1,
        )
        layout.addWidget(
            self._group("SampleSet 能力", ("supported_categories", "storable_categories", "supported_fields")), 1, 0
        )
        layout.addWidget(
            self._button_group(
                "项目动作",
                ("设置主集", "设置对比集", "查看 metadata 字段", "查看支持 categories", "保存项目"),
            ),
            1,
            1,
        )
        return page

    def _build_import_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        tabs = QTabWidget()
        tabs.addTab(
            self._build_import_subpage(
                "导入 Sample",
                ("添加文件", "预览导入文件", "检查单位", "试导入", "执行导入 Sample"),
            ),
            "导入 Sample",
        )
        tabs.addTab(
            self._build_import_subpage(
                "导入 SampleSet",
                ("添加目录", "预览导入文件", "检查单位", "试导入", "执行导入 SampleSet"),
            ),
            "导入 SampleSet",
        )
        layout.addWidget(tabs)
        return page

    def _build_processing_page(self) -> QWidget:
        page = QWidget()
        layout = QGridLayout(page)
        layout.addWidget(
            self._group(
                "子集构建器", ("来源: 主集 / 对比集 / 查询子集", "条件: uids / criteria / filter", "先构建子集再处理")
            ),
            0,
            0,
        )
        layout.addWidget(
            self._group(
                "处理与评价入口", ("preprocess / pipeline", "freqspec / respspec", "zvl / otovl / fdmvl / fpvdv")
            ),
            0,
            1,
        )
        layout.addWidget(
            self._group("结果导出准备", ("metadata_frame", "scalar_frame", "series_frame", "peaks_frame")), 0, 2
        )
        result_tabs = QTabWidget()
        for name in ("metadata_frame", "scalar_frame", "series_frame", "peaks_frame"):
            result_tabs.addTab(self._placeholder_text(f"{name} 结果预览占位"), name)
        layout.addWidget(result_tabs, 1, 0, 1, 2)
        layout.addWidget(
            self._button_group(
                "处理动作",
                ("构建子集", "运行处理", "查看结果预览", "导出处理结果"),
            ),
            1,
            2,
        )
        return page

    def _build_plotting_page(self) -> QWidget:
        page = QWidget()
        layout = QGridLayout(page)
        layout.addWidget(self._group("图任务树", ("图组", "图任务", "子图", "绑定数据")), 0, 0)
        layout.addWidget(self._preview_frame("绘图预览区", "首轮不接 Matplotlib 真实画布。"), 0, 1)
        layout.addWidget(
            self._group("统一图参数区", ("数据绑定", "绘图入口", "坐标 / 标签 / 图例", "局部 hook 与导出")), 0, 2
        )
        layout.addWidget(
            self._button_group(
                "绘图动作",
                ("新建图组", "新建图任务", "绑定绘图数据", "刷新预览", "打开大图预览", "导出当前图组"),
            ),
            1,
            0,
            1,
            3,
        )
        return page

    def _build_export_page(self) -> QWidget:
        page = QWidget()
        layout = QGridLayout(page)
        layout.addWidget(self._group("导出任务与模板", ("当前工程导出任务", "最近导出", "预设模板")), 0, 0)
        layout.addWidget(
            self._group("导出内容编排", ("项目摘要", "处理结果表", "图组选择", "report package 入口")), 0, 1
        )
        layout.addWidget(self._group("输出与预检", ("输出目录", "覆盖策略", "预检结果", "可视化进度")), 0, 2)
        layout.addWidget(
            self._button_group(
                "工程导出动作",
                ("工程导出预检", "执行工程导出", "仅导出结果表", "仅导出图组", "仅导出报告包"),
            ),
            1,
            0,
            1,
            3,
        )
        return page

    def _build_import_subpage(self, title: str, actions: tuple[str, ...]) -> QWidget:
        page = QWidget()
        layout = QGridLayout(page)
        layout.addWidget(self._group(f"{title} / 导入源", ("文件 / 目录 / 存储路径", "来源类型", "导入状态")), 0, 0)
        layout.addWidget(
            self._group(f"{title} / 预览与检测", ("按钮触发文件预览", "单位检测结果", "存储结构检测结果")), 0, 1
        )
        layout.addWidget(
            self._group(f"{title} / 导入参数", ("目标: 新建 / 追加 / 合并", "解析参数", "hook / metadata / 单位策略")),
            0,
            2,
        )
        layout.addWidget(self._button_group(f"{title} / 动作", actions), 1, 0, 1, 3)
        return page

    def _group(self, title: str, lines: tuple[str, ...]) -> QGroupBox:
        box = QGroupBox(title)
        layout = QVBoxLayout(box)
        for line in lines:
            label = QLabel(line)
            label.setWordWrap(True)
            layout.addWidget(label)
        layout.addStretch(1)
        return box

    def _button_group(
        self,
        title: str,
        labels: tuple[str, ...],
        row: int = 0,
        column: int = 0,
        row_span: int = 1,
        column_span: int = 1,
    ) -> QGroupBox:
        del row, column, row_span, column_span
        box = QGroupBox(title)
        layout = QGridLayout(box)
        for index, text in enumerate(labels):
            button = QPushButton(text)
            button.clicked.connect(lambda checked=False, name=text: self.action_requested.emit(name))
            self._action_buttons.append(button)
            layout.addWidget(button, index // 3, index % 3)
        return box

    def _preview_frame(self, title: str, text: str) -> QGroupBox:
        box = QGroupBox(title)
        layout = QVBoxLayout(box)
        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        inner = QVBoxLayout(frame)
        label = QLabel(text)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setWordWrap(True)
        inner.addWidget(label)
        layout.addWidget(frame)
        return box

    def _placeholder_text(self, text: str) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        edit = QPlainTextEdit(text)
        edit.setReadOnly(True)
        layout.addWidget(edit)
        return widget
