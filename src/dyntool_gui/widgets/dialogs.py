"""骨架阶段使用的子窗口。"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QLabel, QPlainTextEdit, QProgressBar, QTableWidget, QTableWidgetItem, QVBoxLayout

from ..session import ProjectSession


class PlaceholderDialog(QDialog):
    """文本型占位对话框。"""

    def __init__(self, title: str, body: str, parent: object | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(680, 420)
        layout = QVBoxLayout(self)
        text = QPlainTextEdit(body)
        text.setReadOnly(True)
        layout.addWidget(text)


class TableDialog(QDialog):
    """表格型占位对话框。"""

    def __init__(
        self, title: str, headers: tuple[str, ...], rows: list[tuple[str, ...]], parent: object | None = None
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(820, 460)
        layout = QVBoxLayout(self)
        table = QTableWidget(len(rows), len(headers))
        table.setHorizontalHeaderLabels(list(headers))
        for row_index, row in enumerate(rows):
            for column_index, value in enumerate(row):
                table.setItem(row_index, column_index, QTableWidgetItem(value))
        table.resizeColumnsToContents()
        layout.addWidget(table)


class ImportPreviewDialog(PlaceholderDialog):
    """导入文件预览窗。"""

    def __init__(self, session: ProjectSession, parent: object | None = None) -> None:
        body = (
            "当前只展示导入预览的固定槽位：\n"
            "- 源文件列表\n"
            "- 前 20 行解析预览\n"
            "- 单位探测结果\n"
            "- metadata / hook 预处理结果\n\n"
            f"当前主项目：{session.project_name}\n"
            "真实文件读取、单位解析和 hook 执行将在第二轮接入。"
        )
        super().__init__("导入文件预览窗", body, parent)


class LongTaskProgressDialog(QDialog):
    """长任务进度窗。"""

    def __init__(self, parent: object | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("长任务进度窗")
        self.resize(420, 180)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("当前为 GUI 骨架进度占位，不绑定真实后台任务。"))
        progress = QProgressBar()
        progress.setRange(0, 100)
        progress.setValue(38)
        layout.addWidget(progress)


class FigurePreviewDialog(QDialog):
    """大图预览窗。"""

    def __init__(self, parent: object | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("大图预览窗")
        self.resize(860, 560)
        layout = QVBoxLayout(self)
        label = QLabel("Matplotlib 真实画布将在第二轮接入。\n当前只验证窗口、停靠区和绘图模块骨架布局。")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setWordWrap(True)
        label.setStyleSheet("border: 1px dashed #888; padding: 24px;")
        layout.addWidget(label)


class ExportPrecheckDialog(PlaceholderDialog):
    """导出预检窗。"""

    def __init__(self, session: ProjectSession, parent: object | None = None) -> None:
        body = (
            "工程导出预检项固定为：\n"
            "- 项目摘要是否完整\n"
            "- 主 SampleSet 是否已设置\n"
            "- 处理结果表是否已选择\n"
            "- 图组是否已勾选\n"
            "- 输出目录策略是否已确认\n\n"
            f"当前默认导出目录：{session.export_dir}\n"
            "当前为骨架占位，不执行真实导出。"
        )
        super().__init__("导出预检窗", body, parent)


class LogDetailDialog(TableDialog):
    """日志详窗。"""

    def __init__(self, session: ProjectSession, parent: object | None = None) -> None:
        rows = [(item.timestamp, item.level, item.logger_name, item.message) for item in session.logs]
        super().__init__("日志详窗", ("时间", "级别", "logger", "消息"), rows, parent)


class CodeReviewResultDialog(PlaceholderDialog):
    """代码审查结果窗。"""

    def __init__(self, session: ProjectSession, parent: object | None = None) -> None:
        lines = "\n".join(f"- {item.status} | {item.title} | {item.summary}" for item in session.reviews)
        body = f"当前只提供骨架级审查结果占位：\n{lines}"
        super().__init__("代码审查结果窗", body, parent)


class ResultPreviewDialog(PlaceholderDialog):
    """处理结果预览窗。"""

    def __init__(self, parent: object | None = None) -> None:
        body = (
            "当前处理结果预览区固定为：\n"
            "- metadata_frame\n"
            "- scalar_frame\n"
            "- series_frame\n"
            "- peaks_frame\n\n"
            "真实数据表将在第二轮接入。"
        )
        super().__init__("处理结果预览", body, parent)
