"""右侧信息区。"""

from __future__ import annotations

from PySide6.QtWidgets import QFrame, QLabel, QScrollArea, QVBoxLayout, QWidget

from ..models import PanelDataBuilder, PanelSection
from ..session import ProjectSession


class InformationPanel(QScrollArea):
    """右侧信息区。"""

    def __init__(self, parent: object | None = None) -> None:
        super().__init__(parent)
        self.setWidgetResizable(True)
        self._builder = PanelDataBuilder()
        self._content = QWidget()
        self._layout = QVBoxLayout(self._content)
        self._layout.setContentsMargins(8, 8, 8, 8)
        self._layout.setSpacing(10)
        self._layout.addStretch(1)
        self._cards: list[QWidget] = []
        self.setWidget(self._content)

    def load_session(self, session: ProjectSession) -> None:
        """根据当前会话刷新。"""

        for card in self._cards:
            self._layout.removeWidget(card)
            card.deleteLater()
        self._cards.clear()
        for section in self._builder.build_info_sections(session):
            card = self._build_card(section)
            self._layout.insertWidget(self._layout.count() - 1, card)
            self._cards.append(card)

    def _build_card(self, section: PanelSection) -> QWidget:
        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(frame)
        title = QLabel(section.title)
        title.setStyleSheet("font-weight: 600;")
        body = QLabel("\n".join(section.lines))
        body.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(body)
        return frame
