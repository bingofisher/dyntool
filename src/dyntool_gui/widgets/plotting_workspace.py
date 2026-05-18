"""图形工作页。"""

from __future__ import annotations

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFrame,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..layout import LANDSCAPE_2K_PROFILE
from ..session import ProjectSession, describe_scope, resolve_scope_uids
from ..theme import ThemeManager
from .page_header import PageHeader


class PlottingWorkspace(QWidget):
    """当前主样本集图形页。"""

    plot_requested = Signal()
    save_requested = Signal(str)
    compute_required = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._current_session: ProjectSession | None = None
        self._has_figure = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self._page_header = PageHeader("Plotting", "图形绘制", "配置图形来源、预览画布并收口图形结果与导出动作。", self)
        self._page_header.hide()

        self._splitter = QSplitter(Qt.Orientation.Horizontal, self)
        self._splitter.setObjectName("PlottingWorkspaceSplitter")
        self._splitter.setChildrenCollapsible(False)
        self._control_panel = self._build_control_panel()
        self._preview_panel = self._build_preview_panel()
        self._splitter.addWidget(self._control_panel)
        self._splitter.addWidget(self._preview_panel)
        self._splitter.setStretchFactor(0, 0)
        self._splitter.setStretchFactor(1, 1)
        self._splitter.setSizes([320, 1400])
        layout.addWidget(self._splitter)
        self._sync_mode_ui()

    def _build_control_panel(self) -> QWidget:
        container = QWidget(self)
        container.setObjectName("PlottingControlPanel")
        container.setMinimumWidth(300)
        container.setMaximumWidth(LANDSCAPE_2K_PROFILE.side_panel_max_width)
        container.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.MinimumExpanding)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        layout.addWidget(self._build_mode_group())
        layout.addWidget(self._build_mode_stack())
        layout.addWidget(self._build_render_group())
        layout.addStretch(1)

        scroll = QScrollArea(self)
        scroll.setObjectName("PlottingActionRegion")
        scroll.setProperty("surfaceRole", "actionPanel")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setMaximumWidth(LANDSCAPE_2K_PROFILE.side_panel_max_width)
        scroll.setWidget(container)
        return scroll

    def _build_mode_group(self) -> QGroupBox:
        box = QGroupBox("绘图模式", self)
        layout = QVBoxLayout(box)
        self._plot_mode_combo = QComboBox(box)
        self._plot_mode_combo.addItem("单样本图", "single_sample")
        self._plot_mode_combo.addItem("多样本图", "multi_sample")
        self._plot_mode_combo.currentIndexChanged.connect(self._sync_mode_ui)
        self._plot_mode_combo.hide()
        self._mode_group = QButtonGroup(self)
        self._single_radio = QRadioButton("单样本", box)
        self._multi_radio = QRadioButton("多样本对比", box)
        self._mode_group.addButton(self._single_radio, 0)
        self._mode_group.addButton(self._multi_radio, 1)
        self._single_radio.setChecked(True)
        self._mode_group.idClicked.connect(self._on_radio_mode_changed)
        radio_row = QHBoxLayout()
        radio_row.addWidget(self._single_radio)
        radio_row.addWidget(self._multi_radio)
        radio_row.addStretch(1)
        layout.addLayout(radio_row)
        layout.addWidget(self._plot_mode_combo)
        return box

    def _build_mode_stack(self) -> QGroupBox:
        box = QGroupBox("来源与范围", self)
        layout = QVBoxLayout(box)
        self._mode_stack = QStackedWidget(box)
        self._mode_stack.addWidget(self._build_single_mode_page())
        self._mode_stack.addWidget(self._build_multi_mode_page())
        layout.addWidget(self._mode_stack)
        return box

    def _build_single_mode_page(self) -> QWidget:
        page = QWidget(self)
        form = QFormLayout(page)
        self._single_source_name_combo = QComboBox(page)
        self._single_source_name_combo.setEditable(True)
        self._single_source_name_combo.currentIndexChanged.connect(self._sync_compute_action)
        self._single_sample_combo = QComboBox(page)
        self._single_uid_edit = QLineEdit(page)
        self._single_uid_edit.setPlaceholderText("可输入 UID 或 alias 覆盖下拉选择")
        form.addRow("来源名称", self._single_source_name_combo)
        form.addRow("目标样本", self._single_sample_combo)
        form.addRow("样本搜索", self._single_uid_edit)
        return page

    def _build_multi_mode_page(self) -> QWidget:
        page = QWidget(self)
        form = QFormLayout(page)
        self._multi_scope_kind_combo = QComboBox(page)
        self._multi_scope_kind_combo.addItem("全部样本", "all_samples")
        self._multi_scope_kind_combo.addItem("当前子样本集", "saved_subset")
        self._multi_scope_kind_combo.addItem("多个子样本集", "multi_subset_union")
        self._multi_scope_kind_combo.addItem("临时手选", "temporary_selection")
        self._multi_scope_kind_combo.currentIndexChanged.connect(self._sync_compute_action)
        self._multi_scope_target_edit = QLineEdit(page)
        self._multi_scope_target_edit.setPlaceholderText("子样本集 ID，或逗号分隔 UID / alias")
        self._multi_source_kind_combo = QComboBox(page)
        self._multi_source_kind_combo.addItem("同来源多样本比较", "sample_model")
        self._multi_source_kind_combo.addItem("标量表", "scalar_frame")
        self._multi_source_kind_combo.addItem("序列表", "series_frame")
        self._multi_source_kind_combo.currentIndexChanged.connect(self._sync_multi_source_candidates)
        self._multi_source_name_combo = QComboBox(page)
        self._multi_source_name_combo.setEditable(True)
        self._multi_source_name_combo.currentIndexChanged.connect(self._sync_compute_action)
        self._multi_selected_uids_edit = QLineEdit(page)
        self._multi_selected_uids_edit.setPlaceholderText("留空 = 使用当前范围；或逗号分隔 UID / alias")
        form.addRow("范围来源", self._multi_scope_kind_combo)
        form.addRow("范围目标", self._multi_scope_target_edit)
        form.addRow("来源类型", self._multi_source_kind_combo)
        form.addRow("来源名称", self._multi_source_name_combo)
        form.addRow("样本勾选", self._multi_selected_uids_edit)
        return page

    def _build_render_group(self) -> QGroupBox:
        box = QGroupBox("动作", self)
        layout = QVBoxLayout(box)
        form = QFormLayout()
        self._theme_path_edit = QLineEdit(box)
        self._theme_path_edit.setPlaceholderText("留空 = 默认主题")
        self._point_limit_edit = QLineEdit("20000", box)
        self._save_mode_combo = QComboBox(box)
        self._save_mode_combo.addItem("使用当前预览", "preview")
        self._save_mode_combo.addItem("重新高精度渲染", "full")
        self._save_format_combo = QComboBox(box)
        self._save_format_combo.addItems(("png", "svg", "pdf"))
        form.addRow("主题文件", self._theme_path_edit)
        form.addRow("点数上限", self._point_limit_edit)
        form.addRow("保存模式", self._save_mode_combo)
        form.addRow("保存格式", self._save_format_combo)
        layout.addLayout(form)

        button_row = QHBoxLayout()
        self._render_button = QPushButton("渲染", box)
        self._render_button.setProperty("buttonRole", "primary")
        self._render_button.clicked.connect(self.plot_requested.emit)
        self._save_button = QPushButton("保存图片", box)
        self._save_button.setProperty("buttonRole", "secondary")
        self._save_button.clicked.connect(self._emit_save_request)
        button_row.addWidget(self._render_button)
        button_row.addWidget(self._save_button)
        layout.addLayout(button_row)

        self._compute_button = QPushButton("计算所需结果", box)
        self._compute_button.setProperty("buttonRole", "ghost")
        self._compute_button.clicked.connect(self._emit_compute_request)
        self._compute_button.hide()
        layout.addWidget(self._compute_button)
        return box

    def _build_preview_panel(self) -> QWidget:
        container = QWidget(self)
        container.setObjectName("PlottingResultRegion")
        container.setProperty("surfaceRole", "resultPanel")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        header_row = QHBoxLayout()
        self._preview_title = QLabel("图形预览", container)
        self._preview_title.setProperty("cardRole", "header")
        header_row.addWidget(self._preview_title)
        header_row.addStretch(1)
        layout.addLayout(header_row)

        empty_text = "选择来源后点击渲染；若缺少前置结果，可先执行补算。"
        self._empty_state_label = QLabel(container)
        self._empty_state_label.setText(empty_text)
        self._empty_state_label.setObjectName("PlottingEmptyStateLabel")
        self._empty_state_label.setWordWrap(True)
        self._empty_state_label.setProperty("cardRole", "emptyState")
        self._empty_state_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_state_label.setMinimumHeight(80)
        layout.addWidget(self._empty_state_label)

        self._canvas_container = _CanvasContainer(container)
        canvas_layout = QVBoxLayout(self._canvas_container)
        canvas_layout.setContentsMargins(0, 0, 0, 0)
        canvas_layout.setSpacing(0)
        self._canvas = FigureCanvasQTAgg(Figure(figsize=(8.0, 5.0)))
        self._canvas_hint_label = QLabel(
            "未生成图形。点击“渲染”开始；如果项目运行态缺失，请使用“恢复并渲染”。",
            self._canvas_container,
        )
        self._canvas_hint_label.setObjectName("PlottingCanvasHintLabel")
        self._canvas_hint_label.setProperty("cardRole", "emptyState")
        self._canvas_hint_label.setWordWrap(True)
        self._canvas_hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._canvas_hint_label.setMaximumWidth(620)
        self._toolbar = NavigationToolbar2QT(self._canvas, self._canvas_container)
        ThemeManager().apply_plot_toolbar(self._toolbar)
        self._canvas_container.set_toolbar(self._toolbar)
        self._canvas_container.set_hint(self._canvas_hint_label)
        canvas_layout.addWidget(self._canvas)
        layout.addWidget(self._canvas_container, 1)

        self._result_tabs = QTabWidget(container)
        self._result_tabs.setObjectName("PlottingResultTabs")
        self._summary_label = self._build_result_label("渲染后在这里汇总图形摘要。")
        self._sample_list_label = self._build_result_label("选择样本后在这里显示列表。")
        self._detail_label = self._build_result_label("渲染结果将在执行后更新。")
        self._result_tabs.addTab(self._wrap_label_tab(self._summary_label), "图形摘要")
        self._result_tabs.addTab(self._wrap_label_tab(self._sample_list_label), "样本列表")
        self._result_tabs.addTab(self._wrap_label_tab(self._detail_label), "渲染结果")
        self._result_tabs.setMaximumHeight(LANDSCAPE_2K_PROFILE.result_tabs_max_height)
        layout.addWidget(self._result_tabs)
        return container

    def _build_result_label(self, text: str) -> QLabel:
        label = QLabel(text, self)
        label.setWordWrap(True)
        label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        return label

    def _wrap_label_tab(self, label: QLabel) -> QWidget:
        tab = QWidget(self)
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.addWidget(label)
        layout.addStretch(1)
        return tab

    def load_session(self, session: ProjectSession) -> None:
        """根据会话刷新页面。"""

        self._current_session = session
        state = session.plot_state
        self._page_header.set_summary_lines(
            f"当前范围：{describe_scope(session)}",
            f"绘图模式：{'单样本图' if (state.plot_mode or 'single_sample') == 'single_sample' else '多样本图'}",
            f"最近状态：{state.last_message or '选择来源后可渲染图形'}",
        )
        self._set_combo_value(self._plot_mode_combo, state.plot_mode or "single_sample")
        self._set_combo_value(self._save_mode_combo, state.save_mode or "preview")
        self._point_limit_edit.setText(str(state.point_limit))
        self._sync_mode_ui()
        self._rebuild_source_candidates(session)
        self._rebuild_sample_candidates(session)

        if state.selected_uid:
            self._single_uid_edit.setText(state.selected_uid)
        elif not self._single_uid_edit.hasFocus():
            self._single_uid_edit.clear()
        if state.selected_uids:
            self._multi_selected_uids_edit.setText(",".join(state.selected_uids))
        elif not self._multi_selected_uids_edit.hasFocus():
            self._multi_selected_uids_edit.clear()

        self._theme_path_edit.setText("")
        self._set_combo_value(self._multi_scope_kind_combo, session.current_scope.scope_kind)
        self._set_scope_target_text(session)
        self._set_result_texts(session)
        self._sync_compute_action()

        can_restore_runtime = session.primary_runtime is None and session.import_state.source_path is not None
        enabled = (session.primary_runtime is not None or can_restore_runtime) and not state.busy
        self._render_button.setEnabled(enabled)
        self._render_button.setText("恢复并渲染" if can_restore_runtime else "渲染")
        self._save_button.setEnabled(self._has_figure and state.render_complete)
        self._empty_state_label.setVisible(not state.render_complete)
        self._canvas_hint_label.setVisible(not state.render_complete)
        if state.last_failure_message:
            empty_text = f"请先处理失败项，处理完成后这里会更新图形：{state.last_failure_message}"
        elif can_restore_runtime:
            empty_text = "当前项目已记录导入来源，点击“恢复并渲染”会先恢复运行态；如仍缺少前置结果，可先执行补算。"
        else:
            empty_text = "选择来源后点击渲染；若缺少前置结果，可先执行补算。"
        self._empty_state_label.setText(empty_text)

    def set_figure(self, figure: Figure) -> None:
        """替换当前图形。"""

        self._canvas.figure = figure
        ThemeManager().apply_plot_figure(figure)
        self._canvas.draw_idle()
        self._has_figure = True

    def scope_selection(self) -> tuple[str, str]:
        """返回当前范围来源。"""

        if self.plot_mode() == "single_sample":
            return "single_sample", self._current_single_sample_token()
        return str(self._multi_scope_kind_combo.currentData()), self._multi_scope_target_edit.text().strip()

    def plot_request_values(self) -> dict[str, object]:
        """返回当前绘图动作参数。"""

        plot_mode = self.plot_mode()
        if plot_mode == "single_sample":
            return {
                "plot_mode": "single_sample",
                "source_kind": "sample_model",
                "source_name": self._single_source_name_combo.currentText().strip(),
                "selected_uid": self._current_single_sample_token(),
                "selected_uids": (),
                "theme_path": self._theme_path_edit.text().strip() or None,
                "point_limit": _parse_positive_int(self._point_limit_edit.text(), default=20000),
                "save_mode": str(self._save_mode_combo.currentData()),
            }
        return {
            "plot_mode": "multi_sample",
            "source_kind": str(self._multi_source_kind_combo.currentData()),
            "source_name": self._multi_source_name_combo.currentText().strip(),
            "selected_uid": "",
            "selected_uids": tuple(_split_csv_tokens(self._multi_selected_uids_edit.text())),
            "theme_path": self._theme_path_edit.text().strip() or None,
            "point_limit": _parse_positive_int(self._point_limit_edit.text(), default=20000),
            "save_mode": str(self._save_mode_combo.currentData()),
        }

    def plot_mode(self) -> str:
        """返回当前绘图模式。"""

        return str(self._plot_mode_combo.currentData())

    def _on_radio_mode_changed(self, button_id: int) -> None:
        mode = "multi_sample" if button_id == 1 else "single_sample"
        self._set_combo_value(self._plot_mode_combo, mode)

    def _sync_mode_ui(self) -> None:
        is_multi = self.plot_mode() == "multi_sample"
        self._mode_stack.setCurrentIndex(1 if is_multi else 0)
        self._preview_title.setText("图形预览" if not is_multi else "多样本图形预览")
        self._multi_radio.setChecked(is_multi)
        self._single_radio.setChecked(not is_multi)
        self._sync_compute_action()

    def _sync_multi_source_candidates(self) -> None:
        if self._current_session is None:
            return
        self._rebuild_source_candidates(self._current_session)
        self._sync_compute_action()

    def _rebuild_source_candidates(self, session: ProjectSession) -> None:
        slots = tuple(session.capability_snapshot.data_slots) or ("accel",)
        single_candidates = self._single_source_candidates(slots)
        multi_candidates = self._multi_source_candidates(slots)

        current_single = self._single_source_name_combo.currentText().strip() or session.plot_state.source_name
        current_multi = self._multi_source_name_combo.currentText().strip() or session.plot_state.source_name
        self._reset_combo_items(self._single_source_name_combo, single_candidates, current_single)
        self._reset_combo_items(self._multi_source_name_combo, multi_candidates, current_multi)

    def _rebuild_sample_candidates(self, session: ProjectSession) -> None:
        runtime = session.primary_runtime
        self._single_sample_combo.blockSignals(True)
        self._single_sample_combo.clear()
        if runtime is None:
            self._single_sample_combo.addItem("暂无可选样本", "")
            self._single_sample_combo.blockSignals(False)
            return

        samples_by_uid = {str(uid): sample for uid, sample in runtime.items()}
        sample_tokens = resolve_scope_uids(session) or list(samples_by_uid)
        for token in sample_tokens:
            sample = samples_by_uid.get(str(token))
            if sample is None:
                continue
            self._single_sample_combo.addItem(f"{getattr(sample, 'alias', token)} ({token})", str(token))
        if self._single_sample_combo.count() == 0:
            self._single_sample_combo.addItem("暂无可选样本", "")
        if session.plot_state.selected_uid:
            self._set_combo_value(self._single_sample_combo, session.plot_state.selected_uid)
        self._single_sample_combo.blockSignals(False)

    def _set_scope_target_text(self, session: ProjectSession) -> None:
        if self.plot_mode() == "single_sample":
            return
        scope = session.current_scope
        if scope.subset_ids:
            self._multi_scope_target_edit.setText(",".join(scope.subset_ids))
            return
        if scope.sample_uids:
            self._multi_scope_target_edit.setText(",".join(scope.sample_uids))
            return
        self._multi_scope_target_edit.clear()

    def _set_result_texts(self, session: ProjectSession) -> None:
        state = session.plot_state
        current_source = self._current_source_name() or "-"
        selected_tokens = self._selected_tokens_for_display(session)
        sample_lines = selected_tokens or ["尚未显式选中样本，将按当前范围解析。"]
        next_action = "保存图片" if state.render_complete else "点击渲染生成图形"
        if self._compute_button.isVisible():
            next_action = "先计算所需结果，再重新渲染"

        self._summary_label.setText(
            "\n".join(
                (
                    f"当前状态：{state.last_message or '尚未渲染图形。'}",
                    f"模式：{'单样本图' if self.plot_mode() == 'single_sample' else '多样本图'}",
                    f"来源名称：{current_source}",
                    f"下一步：{next_action}",
                )
            )
        )
        self._sample_list_label.setText("\n".join(sample_lines))
        self._detail_label.setText(
            "\n".join(
                (
                    f"当前范围：{describe_scope(session)}",
                    f"范围来源：{self.scope_selection()[0]}",
                    f"点数上限：{_parse_positive_int(self._point_limit_edit.text(), default=20000)}",
                    f"保存模式：{self._save_mode_combo.currentText()}",
                    f"最近保存：{state.last_saved_path or '暂无'}",
                    f"缺口说明：{state.missing_reason or '无'}",
                    f"失败信息：{state.last_failure_message or '无'}",
                )
            )
        )

    def _selected_tokens_for_display(self, session: ProjectSession) -> list[str]:
        if self.plot_mode() == "single_sample":
            token = self._current_single_sample_token()
            return [token] if token else []
        manual = _split_csv_tokens(self._multi_selected_uids_edit.text())
        if manual:
            return list(manual)
        return resolve_scope_uids(session)

    def _current_source_name(self) -> str:
        if self.plot_mode() == "single_sample":
            return self._single_source_name_combo.currentText().strip()
        return self._multi_source_name_combo.currentText().strip()

    def _current_single_sample_token(self) -> str:
        return self._single_uid_edit.text().strip() or str(self._single_sample_combo.currentData() or "")

    def _single_source_candidates(self, slots: tuple[str, ...]) -> tuple[str, ...]:
        ordered = ("accel", "vel", "disp", "force", "freqspec", "respspec", "otovl")
        return tuple(item for item in ordered if item in slots) or ("accel",)

    def _multi_source_candidates(self, slots: tuple[str, ...]) -> tuple[str, ...]:
        if str(self._multi_source_kind_combo.currentData()) == "sample_model":
            ordered = ("accel", "vel", "disp", "force", "freqspec", "respspec")
            return tuple(item for item in ordered if item in slots) or ("accel",)
        return tuple(item for item in slots) or ("accel",)

    def _reset_combo_items(self, combo: QComboBox, items: tuple[str, ...], current_text: str) -> None:
        combo.blockSignals(True)
        combo.clear()
        combo.addItems(list(items))
        if current_text:
            combo.setCurrentText(current_text)
        combo.blockSignals(False)

    def _sync_compute_action(self) -> None:
        source_name = self._current_source_name()
        action_name = None
        if self.plot_mode() == "single_sample":
            action_name = _required_action(source_name)
        elif str(self._multi_source_kind_combo.currentData()) in {"sample_model", "series_frame"}:
            action_name = _required_action(source_name)

        if self._current_session is not None:
            available = self._current_session.capability_snapshot.data_slots
            if source_name in available or str(self._multi_source_kind_combo.currentData()) == "scalar_frame":
                action_name = None

        self._compute_button.setVisible(action_name is not None)
        self._compute_button.setProperty("action_name", action_name or "")

    def _emit_save_request(self) -> None:
        self.save_requested.emit(self._save_format_combo.currentText())

    def _emit_compute_request(self) -> None:
        action_name = self._compute_button.property("action_name")
        if isinstance(action_name, str) and action_name:
            self.compute_required.emit(action_name)

    def _set_combo_value(self, combo: QComboBox, value: str) -> None:
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)


class _CanvasContainer(QWidget):
    """画布容器，负责将工具栏悬浮在右下角。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._toolbar: NavigationToolbar2QT | None = None
        self._hint: QLabel | None = None

    def set_toolbar(self, toolbar: NavigationToolbar2QT) -> None:
        """设置悬浮工具栏。"""

        self._toolbar = toolbar
        self._reposition_toolbar()

    def set_hint(self, hint: QLabel) -> None:
        """设置画布中心空态提示。"""

        self._hint = hint
        self._reposition_hint()

    def resizeEvent(self, event: object) -> None:
        """重定位工具栏到右下角。"""

        super().resizeEvent(event)  # type: ignore[arg-type]
        self._reposition_toolbar()
        self._reposition_hint()

    def _reposition_toolbar(self) -> None:
        if self._toolbar is None:
            return
        self._toolbar.adjustSize()
        x = self.width() - self._toolbar.width() - 8
        y = self.height() - self._toolbar.height() - 8
        self._toolbar.move(x, y)
        self._toolbar.raise_()

    def _reposition_hint(self) -> None:
        if self._hint is None:
            return
        self._hint.adjustSize()
        width = min(max(360, self.width() // 2), self._hint.maximumWidth())
        height = max(56, self._hint.height())
        x = max(12, (self.width() - width) // 2)
        y = max(12, (self.height() - height) // 2)
        self._hint.setGeometry(x, y, width, height)
        self._hint.raise_()


def _required_action(source_name: str) -> str | None:
    return {
        "freqspec": "calc_freqspec",
        "respspec": "calc_respspec",
        "zvl": "eval_zvl",
        "otovl": "eval_otovl",
        "fdmvl": "eval_fdmvl",
        "fpvdv": "eval_fpvdv",
    }.get(source_name)


def _parse_positive_int(text: str, *, default: int) -> int:
    try:
        value = int(text.strip())
    except ValueError:
        return default
    return value if value > 0 else default


def _split_csv_tokens(text: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in text.split(",") if item.strip())
