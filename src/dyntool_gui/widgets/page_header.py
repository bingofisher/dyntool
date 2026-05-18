"""统一页面头部组件。"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from ..layout import LANDSCAPE_2K_PROFILE


class PageHeader(QWidget):
    """用于固定页面标题、说明与摘要的统一头部。"""

    def __init__(
        self,
        page_key: str,
        title: str,
        subtitle: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName(f"{page_key}PageHeader")
        self.setProperty("pageHeader", True)
        self.setProperty("surfaceRole", "pageHeader")
        self.setMaximumHeight(LANDSCAPE_2K_PROFILE.page_header_max_height)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(12)

        title_column = QWidget(self)
        title_layout = QVBoxLayout(title_column)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(0)

        self._title_label = QLabel(title, self)
        self._title_label.setObjectName(f"{page_key}PageHeaderTitle")
        self._title_label.setProperty("cardRole", "pageTitle")
        self._title_label.setMaximumHeight(24)
        title_layout.addWidget(self._title_label)

        self._subtitle_label = QLabel(subtitle, self)
        self._subtitle_label.setObjectName(f"{page_key}PageHeaderSubtitle")
        self._subtitle_label.setWordWrap(False)
        self._subtitle_label.setProperty("cardRole", "pageSubtitle")
        self._subtitle_label.setMaximumHeight(20)
        title_layout.addWidget(self._subtitle_label)
        layout.addWidget(title_column, 0)

        self._summary_label = QLabel(self)
        self._summary_label.setObjectName(f"{page_key}PageHeaderSummary")
        self._summary_label.setWordWrap(False)
        self._summary_label.setProperty("cardRole", "pageSummary")
        self._summary_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        self._summary_label.setMaximumHeight(32)
        self._summary_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout.addWidget(self._summary_label, 1)

    def set_summary_lines(self, *lines: str) -> None:
        """更新头部摘要。"""

        self._summary_label.setText(" / ".join(line for line in lines if line))
