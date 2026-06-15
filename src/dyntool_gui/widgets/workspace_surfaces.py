"""GUI 工作台内部通用展示组件。"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QButtonGroup, QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget


class SegmentedControl(QWidget):
    """等宽分段选择控件。"""

    value_changed = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("SegmentedControl")
        self.setProperty("surfaceRole", "segmentedControl")
        self._buttons: dict[str, QPushButton] = {}
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(4)

    def add_option(self, text: str, value: str) -> None:
        """添加一个分段选项。"""

        button = QPushButton(text, self)
        button.setCheckable(True)
        button.setProperty("buttonRole", "segmented")
        button.setMinimumHeight(30)
        button.setMinimumWidth(108)
        button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._buttons[value] = button
        self._group.addButton(button)
        self._layout.addWidget(button, 1)
        button.clicked.connect(lambda checked=False, item=value: self._emit_value(item))
        if len(self._buttons) == 1:
            button.setChecked(True)

    def buttons(self) -> tuple[QPushButton, ...]:
        """返回分段按钮，供 GUI 视觉合同测试使用。"""

        return tuple(self._buttons.values())

    def value(self) -> str:
        """返回当前选中值。"""

        for value, button in self._buttons.items():
            if button.isChecked():
                return value
        return ""

    def set_value(self, value: str) -> None:
        """设置当前选中值。"""

        button = self._buttons.get(value)
        if button is None:
            return
        was_blocked = self.blockSignals(True)
        button.setChecked(True)
        self.blockSignals(was_blocked)

    def _emit_value(self, value: str) -> None:
        self.value_changed.emit(value)


class WorkspaceSection(QFrame):
    """轻量工作台区块，避免把普通区域做成厚重 GroupBox。"""

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("surfaceRole", "section")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        self.title_label = QLabel(title, self)
        self.title_label.setProperty("cardRole", "sectionTitle")
        layout.addWidget(self.title_label)

    def body_layout(self) -> QVBoxLayout:
        """返回区块内容布局。"""

        layout = self.layout()
        if not isinstance(layout, QVBoxLayout):
            raise TypeError("WorkspaceSection 使用 QVBoxLayout。")
        return layout

    def title(self) -> str:
        """返回区块标题，兼容旧视觉合同测试。"""

        return self.title_label.text()
