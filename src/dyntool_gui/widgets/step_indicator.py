"""导入步骤指示器。"""

from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget


class StepIndicator(QWidget):
    """显示当前步骤与已完成步骤。"""

    def __init__(self, labels: tuple[str, ...], parent: object | None = None) -> None:
        super().__init__(parent)
        self._labels = labels
        self._current_step = 0
        self._completed_steps = 0
        self._badges: list[QLabel] = []
        self._texts: list[QLabel] = []

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)
        for index, label_text in enumerate(labels, start=1):
            container = QWidget(self)
            container_layout = QVBoxLayout(container)
            container_layout.setContentsMargins(0, 0, 0, 0)
            container_layout.setSpacing(4)
            badge = QLabel(str(index), container)
            badge.setObjectName("stepIndicatorBadge")
            text = QLabel(label_text, container)
            text.setObjectName("stepIndicatorText")
            container_layout.addWidget(badge)
            container_layout.addWidget(text)
            layout.addWidget(container)
            self._badges.append(badge)
            self._texts.append(text)
        self._apply_state()

    def set_current_step(self, index: int) -> None:
        """设置当前步骤索引。"""

        self._current_step = max(0, min(index, len(self._labels) - 1))
        self._apply_state()

    def current_step(self) -> int:
        """返回当前步骤索引。"""

        return self._current_step

    def set_completed_steps(self, count: int) -> None:
        """设置已完成步骤数量。"""

        self._completed_steps = max(0, min(count, len(self._labels)))
        self._apply_state()

    def completed_steps(self) -> int:
        """返回已完成步骤数量。"""

        return self._completed_steps

    def step_count(self) -> int:
        """返回总步骤数量。"""

        return len(self._labels)

    def _apply_state(self) -> None:
        for index, (badge, text) in enumerate(zip(self._badges, self._texts, strict=True)):
            if index < self._completed_steps:
                badge.setText("✓")
                badge.setStyleSheet(
                    "background:#F0FDF4;color:#16A34A;border:1px solid #86EFAC;"
                    "border-radius:12px;padding:4px 8px;font-weight:700;"
                )
                text.setStyleSheet("color:#16A34A;font-weight:600;")
            elif index == self._current_step:
                badge.setText(str(index + 1))
                badge.setStyleSheet(
                    "background:#EFF6FF;color:#2563EB;border:1px solid #93C5FD;"
                    "border-radius:12px;padding:4px 8px;font-weight:700;"
                )
                text.setStyleSheet("color:#2563EB;font-weight:600;")
            else:
                badge.setText(str(index + 1))
                badge.setStyleSheet(
                    "background:#F1F5F9;color:#64748B;border:1px solid #CBD5E1;border-radius:12px;padding:4px 8px;"
                )
                text.setStyleSheet("color:#64748B;")
