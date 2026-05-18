"""项目概况页。"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QGridLayout,
    QGroupBox,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ..layout import LANDSCAPE_2K_PROFILE
from ..session import ProjectSession
from .page_header import PageHeader


class ProjectOverviewWidget(QWidget):
    """项目概况页。"""

    action_requested = Signal(str)

    def __init__(self, parent: object | None = None) -> None:
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._page_header = PageHeader(
            "Project", "总览", "查看项目摘要与下一步，确定当前主样本集、范围和后续任务。", self
        )
        root.addWidget(self._page_header)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        content = QWidget(scroll)
        scroll.setWidget(content)
        root.addWidget(scroll, 1)

        grid = QGridLayout(content)
        grid.setContentsMargins(12, 12, 12, 12)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(12)

        self._primary_body = QLabel(content)
        self._primary_body.setWordWrap(True)
        self._primary_body.setProperty("cardRole", "status")
        self._primary_card = self._card("当前主样本集", self._primary_body)
        grid.addWidget(self._primary_card, 0, 0)

        self._capability_body = QLabel(content)
        self._capability_body.setWordWrap(True)
        self._capability_body.setProperty("cardRole", "status")
        self._capability_card = self._card("当前能力", self._capability_body)
        grid.addWidget(self._capability_card, 0, 1)

        self._project_body = QLabel(content)
        self._project_body.setWordWrap(True)
        self._project_body.setProperty("cardRole", "status")
        self._project_card = self._card("项目上下文", self._project_body)
        grid.addWidget(self._project_card, 1, 0)

        self._subset_body = QLabel(content)
        self._subset_body.setWordWrap(True)
        self._subset_body.setProperty("cardRole", "status")
        self._subset_card = self._card("子样本集", self._subset_body)
        grid.addWidget(self._subset_card, 1, 1)

        self._recent_body = QLabel(content)
        self._recent_body.setWordWrap(True)
        self._recent_body.setProperty("cardRole", "status")
        self._recent_card = self._card("最近记录", self._recent_body)
        grid.addWidget(self._recent_card, 2, 0)

        self._action_card = self._build_action_card(content)
        grid.addWidget(self._action_card, 2, 1)

        grid.setRowStretch(3, 1)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)

    def load_session(self, session: ProjectSession) -> None:
        """加载项目概况。"""

        self._page_header.set_summary_lines(
            f"当前项目：{session.project_name}",
            f"当前范围：{session.current_scope.scope_kind}",
            f"建议下一步：{'接入主样本集' if session.primary_runtime is None else '开始分析或快速出图'}",
        )

        self._primary_body.setText(
            "\n".join(
                (
                    f"名称：{session.primary_sampleset.name}",
                    f"类型：{session.primary_sampleset.class_name} / {session.primary_sampleset.sample_type}",
                    f"样本数量：{session.primary_sampleset.sample_count}",
                    f"存储绑定：{session.primary_sampleset.storage_binding}",
                )
            )
        )

        capability = "、".join(session.capability_snapshot.data_slots) or "无原始数据"
        results: list[str] = list(session.capability_snapshot.eval_results)
        if session.capability_snapshot.scalar_frame:
            results.append("标量表")
        if session.capability_snapshot.series_frame:
            results.append("序列表")
        if session.capability_snapshot.peaks_frame:
            results.append("峰值表")
        self._capability_body.setText(
            "\n".join(
                (
                    f"原始数据：{capability}",
                    f"分析结果：{'、'.join(results) if results else '尚未生成'}",
                    f"可绘图：{'是' if session.primary_runtime is not None else '否'}",
                    f"可交付：{'是' if bool(results) else '否'}",
                )
            )
        )

        self._project_body.setText(
            "\n".join(
                (
                    f"项目：{session.project_name}",
                    f"工作目录：{session.workdir}",
                    f"默认导出目录：{session.export_dir}",
                    f"最近保存时间：{session.last_saved}",
                )
            )
        )

        subset_lines = [
            f"已保存子样本集：{len(session.subset_state.subsets)}",
            f"当前范围：{session.current_scope.scope_kind}",
        ]
        if session.subset_state.subsets:
            subset_lines.append(f"最近子样本集：{session.subset_state.subsets[0].name}")
        self._subset_body.setText("\n".join(subset_lines))

        recent_lines = list(session.recent_import_lines or ("最近导入：无",))
        if session.processing_state.last_message:
            recent_lines.append(f"最近分析：{session.processing_state.last_message}")
        if session.plot_records:
            recent_lines.append(f"最近图形：{session.plot_records[0].title}")
        elif session.plot_state.last_message:
            recent_lines.append(f"最近图形：{session.plot_state.last_message}")
        if session.export_state.last_message:
            recent_lines.append(f"最近交付：{session.export_state.last_message}")
        self._recent_body.setText("\n".join(recent_lines))

    def _card(self, title: str, body: QLabel) -> QGroupBox:
        box = QGroupBox(title)
        box.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout = QVBoxLayout(box)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(4)
        layout.addWidget(body)
        return box

    def _build_action_card(self, parent: QWidget) -> QGroupBox:
        box = QGroupBox("快速操作", parent)
        box.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout = QGridLayout(box)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setHorizontalSpacing(8)
        layout.setVerticalSpacing(8)
        actions = (
            ("接入主样本集", "primary"),
            ("管理子样本集", "secondary"),
            ("开始分析", "primary"),
            ("快速出图", "secondary"),
            ("去交付", "ghost"),
        )
        self._next_step_buttons: list[QPushButton] = []
        for index, (text, role) in enumerate(actions):
            button = QPushButton(text, box)
            button.setProperty("buttonRole", role)
            button.setMinimumHeight(LANDSCAPE_2K_PROFILE.nav_button_height)
            button.clicked.connect(lambda checked=False, name=text: self.action_requested.emit(name))
            if index == len(actions) - 1 and index % 2 == 0:
                layout.addWidget(button, index // 2, 0, 1, 2)
            else:
                layout.addWidget(button, index // 2, index % 2)
            self._next_step_buttons.append(button)
        return box
