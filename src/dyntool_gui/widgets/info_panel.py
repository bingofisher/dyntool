"""右侧信息区。"""

from __future__ import annotations

from PySide6.QtWidgets import QFrame, QLabel, QScrollArea, QVBoxLayout, QWidget

from ..models import InfoPanelSnapshot, PanelDataBuilder, PanelSection
from ..session import ProjectSession


class _InfoCard(QFrame):
    """固定信息卡片。"""

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(self)
        self._title = QLabel(title, self)
        self._title.setStyleSheet("font-weight: 600;")
        self._body = QLabel("", self)
        self._body.setWordWrap(True)
        layout.addWidget(self._title)
        layout.addWidget(self._body)

    def update_section(self, section: PanelSection) -> None:
        """更新卡片内容。"""

        self._title.setText(section.title)
        self._body.setText("\n".join(section.lines))


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
        self._cards_by_key: dict[str, _InfoCard] = {}
        self._visible_keys: list[str] = []
        self.setWidget(self._content)

    def load_session(self, session: ProjectSession) -> None:
        """根据当前会话刷新。"""

        self.apply_snapshot(self._builder.build_info_snapshot(session))

    def apply_snapshot(self, snapshot: InfoPanelSnapshot) -> None:
        """应用信息区快照。"""

        next_visible_keys: list[str] = []
        for section in snapshot.sections:
            card = self._cards_by_key.get(section.key)
            if card is None:
                card = _InfoCard(section.title, self._content)
                self._cards_by_key[section.key] = card
                self._layout.insertWidget(self._layout.count() - 1, card)
            card.update_section(section)
            card.setVisible(True)
            next_visible_keys.append(section.key)
        for key, card in self._cards_by_key.items():
            if key not in next_visible_keys:
                card.setVisible(False)
        self._reorder_visible_cards(next_visible_keys)
        self._visible_keys = next_visible_keys

    def card_widgets(self) -> tuple[QWidget, ...]:
        """返回当前可见卡片。"""

        return tuple(self._cards_by_key[key] for key in self._visible_keys)

    def _reorder_visible_cards(self, ordered_keys: list[str]) -> None:
        insert_position = 0
        for key in ordered_keys:
            card = self._cards_by_key[key]
            self._layout.removeWidget(card)
            self._layout.insertWidget(insert_position, card)
            insert_position += 1
