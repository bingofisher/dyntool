"""分析工作页。"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..layout import LANDSCAPE_2K_PROFILE
from ..session import (
    ProcessingActionSpec,
    ProcessingParameterSpec,
    ProcessingPreviewRequestSnapshot,
    ProcessingRequestSnapshot,
    ProjectSession,
)
from .page_header import PageHeader

_ACTION_SPECS: dict[str, ProcessingActionSpec] = {
    "calc_freqspec": ProcessingActionSpec(
        action_name="calc_freqspec",
        label="计算频谱",
    ),
    "calc_respspec": ProcessingActionSpec(
        action_name="calc_respspec",
        label="计算响应谱",
        specific_params=(
            ProcessingParameterSpec(
                key="method",
                label="method",
                editor_kind="choice",
                options=(("Nigam-Jennings", "nigam-jennings"),),
                default_value="nigam-jennings",
            ),
            ProcessingParameterSpec(
                key="calc_unit_system",
                label="calc_unit_system",
                editor_kind="choice",
                options=(("默认", ""), ("SI", "si"), ("工程制", "engineering")),
                default_value="",
            ),
            ProcessingParameterSpec(
                key="output_unit_system",
                label="output_unit_system",
                editor_kind="choice",
                options=(("默认", ""), ("SI", "si"), ("工程制", "engineering")),
                default_value="",
            ),
            ProcessingParameterSpec(
                key="periods",
                label="periods",
                placeholder="例如 0.1,0.5,1.0",
                default_value="0.1,0.5,1.0",
            ),
        ),
    ),
    "eval_zvl": ProcessingActionSpec(
        action_name="eval_zvl",
        label="计算 ZVL",
        specific_params=(
            ProcessingParameterSpec(
                key="freq_range_min", label="freq_range_min", placeholder="最小频率", default_value="0.5"
            ),
            ProcessingParameterSpec(
                key="freq_range_max", label="freq_range_max", placeholder="最大频率", default_value="80"
            ),
            ProcessingParameterSpec(
                key="weight_type",
                label="weight_type",
                editor_kind="choice",
                options=tuple((name.upper(), name) for name in ("wk", "wd", "wf", "wc", "we", "wj")),
                default_value="wk",
            ),
            ProcessingParameterSpec(
                key="time_windows", label="time_windows", placeholder="例如 2.0", default_value="1"
            ),
            ProcessingParameterSpec(
                key="calc_unit_system",
                label="calc_unit_system",
                editor_kind="choice",
                options=(("默认", ""), ("SI", "si"), ("工程制", "engineering")),
                default_value="",
            ),
            ProcessingParameterSpec(
                key="output_unit_system",
                label="output_unit_system",
                editor_kind="choice",
                options=(("默认", ""), ("SI", "si"), ("工程制", "engineering")),
                default_value="",
            ),
        ),
    ),
    "eval_otovl": ProcessingActionSpec(
        action_name="eval_otovl",
        label="计算 OTOVL",
        specific_params=(
            ProcessingParameterSpec(
                key="freq_range_min", label="freq_range_min", placeholder="最小频率", default_value="0.5"
            ),
            ProcessingParameterSpec(
                key="freq_range_max", label="freq_range_max", placeholder="最大频率", default_value="80"
            ),
            ProcessingParameterSpec(
                key="time_windows", label="time_windows", placeholder="例如 2.0", default_value="1"
            ),
            ProcessingParameterSpec(
                key="calc_unit_system",
                label="calc_unit_system",
                editor_kind="choice",
                options=(("默认", ""), ("SI", "si"), ("工程制", "engineering")),
                default_value="",
            ),
            ProcessingParameterSpec(
                key="output_unit_system",
                label="output_unit_system",
                editor_kind="choice",
                options=(("默认", ""), ("SI", "si"), ("工程制", "engineering")),
                default_value="",
            ),
        ),
    ),
    "eval_fdmvl": ProcessingActionSpec(
        action_name="eval_fdmvl",
        label="计算 FDMVL",
        specific_params=(
            ProcessingParameterSpec(
                key="freq_range_min", label="freq_range_min", placeholder="最小频率", default_value="0.5"
            ),
            ProcessingParameterSpec(
                key="freq_range_max", label="freq_range_max", placeholder="最大频率", default_value="80"
            ),
            ProcessingParameterSpec(
                key="calc_unit_system",
                label="calc_unit_system",
                editor_kind="choice",
                options=(("默认", ""), ("SI", "si"), ("工程制", "engineering")),
                default_value="",
            ),
            ProcessingParameterSpec(
                key="output_unit_system",
                label="output_unit_system",
                editor_kind="choice",
                options=(("默认", ""), ("SI", "si"), ("工程制", "engineering")),
                default_value="",
            ),
        ),
    ),
    "eval_fpvdv": ProcessingActionSpec(
        action_name="eval_fpvdv",
        label="计算 FPVDV",
        specific_params=(
            ProcessingParameterSpec(
                key="freq_range_min", label="freq_range_min", placeholder="最小频率", default_value="1"
            ),
            ProcessingParameterSpec(
                key="freq_range_max", label="freq_range_max", placeholder="最大频率", default_value="40"
            ),
            ProcessingParameterSpec(key="nsup", label="nsup", placeholder="例如 4", default_value="4"),
            ProcessingParameterSpec(
                key="calc_unit_system",
                label="calc_unit_system",
                editor_kind="choice",
                options=(("默认", ""), ("SI", "si"), ("工程制", "engineering")),
                default_value="",
            ),
            ProcessingParameterSpec(
                key="output_unit_system",
                label="output_unit_system",
                editor_kind="choice",
                options=(("默认", ""), ("SI", "si"), ("工程制", "engineering")),
                default_value="",
            ),
        ),
    ),
}

_PREVIEW_KIND_LABELS = {
    "scalar_frame": "标量表",
    "series_frame": "序列表",
    "peaks_frame": "峰值表",
}


class ProcessingWorkspace(QWidget):
    """当前主样本集分析页。"""

    process_requested = Signal(object)
    preview_requested = Signal(object)
    cancel_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._specific_widgets: dict[str, QWidget] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self._page_header = PageHeader(
            "Processing", "数据处理", "执行处理动作、调整参数，并查看结果预览与状态反馈。", self
        )
        self._page_header.hide()

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.setObjectName("ProcessingWorkspaceSplitter")
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self._build_left_panel())
        splitter.addWidget(self._build_right_panel())
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([320, 1280])
        layout.addWidget(splitter)
        self._rebuild_specific_params("calc_freqspec")

    def _build_left_panel(self) -> QWidget:
        container = QWidget(self)
        container.setMinimumWidth(300)
        container.setMaximumWidth(LANDSCAPE_2K_PROFILE.side_panel_max_width)
        container.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.MinimumExpanding)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        layout.addWidget(self._build_action_group())
        layout.addWidget(self._run_button)
        layout.addWidget(self._build_preview_group())
        layout.addWidget(self._preview_button)
        self._summary = QLabel("选择动作后开始分析，结果会在右侧更新。", container)
        self._summary.setWordWrap(True)
        self._summary.setProperty("cardRole", "status")
        layout.addWidget(self._summary)
        layout.addStretch(1)

        scroll = QScrollArea(self)
        scroll.setObjectName("ProcessingActionRegion")
        scroll.setProperty("surfaceRole", "actionPanel")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setMaximumWidth(LANDSCAPE_2K_PROFILE.side_panel_max_width)
        scroll.setWidget(container)
        return scroll

    def _build_right_panel(self) -> QWidget:
        container = QWidget(self)
        container.setObjectName("ProcessingResultRegion")
        container.setProperty("surfaceRole", "resultPanel")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        self._phase_label = QLabel("处理状态：等待执行。", container)
        self._phase_label.setWordWrap(True)
        self._phase_label.setStyleSheet("color: #64748B; font-size: 9pt;")
        self._phase_label.setMaximumHeight(22)
        layout.addWidget(self._phase_label)

        metrics_frame = QFrame(container)
        metrics_frame.setObjectName("ProcessingMetricsFrame")
        metrics_frame.setMaximumHeight(34)
        metrics_frame.setStyleSheet(
            "QFrame#ProcessingMetricsFrame { background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 6px; }"
        )
        metrics_layout = QHBoxLayout(metrics_frame)
        metrics_layout.setContentsMargins(10, 4, 10, 4)
        self._metrics_summary = QLabel("完成结果：0 / 缺口：0 / 最近执行：--:--", metrics_frame)
        self._metrics_summary.setObjectName("ProcessingMetricsSummaryLabel")
        self._metrics_summary.setStyleSheet("color: #475569; font-size: 9pt; background: transparent;")
        metrics_layout.addWidget(self._metrics_summary)

        layout.addWidget(metrics_frame)

        self._empty_state_label = QLabel(
            "选择左侧动作后执行分析；如果只需检查已有结果，可先生成预览表。",
            container,
        )
        self._empty_state_label.setObjectName("ProcessingEmptyStateLabel")
        self._empty_state_label.setWordWrap(True)
        self._empty_state_label.setProperty("cardRole", "emptyState")
        self._empty_state_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_state_label.setMinimumHeight(64)
        layout.addWidget(self._empty_state_label)

        self._preview_tabs = QTabWidget(container)
        self._scalar_table = _build_table_widget()
        self._series_table = _build_table_widget()
        self._peaks_table = _build_table_widget()
        self._preview_tabs.addTab(self._scalar_table, "预览表")
        self._preview_tabs.addTab(self._series_table, "标量结果")
        self._preview_tabs.addTab(self._peaks_table, "序列结果")
        layout.addWidget(self._preview_tabs, 1)
        return container

    def _build_action_group(self) -> QGroupBox:
        box = QGroupBox("处理动作", self)
        layout = QVBoxLayout(box)

        common_form = QFormLayout()
        self._action_combo = QComboBox(box)
        for spec in _ACTION_SPECS.values():
            self._action_combo.addItem(spec.label, spec.action_name)
        self._action_combo.currentIndexChanged.connect(self._on_action_changed)
        self._scope_kind_combo = QComboBox(box)
        self._scope_kind_combo.addItem("全部样本", "all_samples")
        self._scope_kind_combo.addItem("当前子样本集", "saved_subset")
        self._scope_kind_combo.addItem("多个子样本集", "multi_subset_union")
        self._scope_kind_combo.addItem("临时手选", "temporary_selection")
        self._scope_kind_combo.addItem("单个样本", "single_sample")
        self._scope_target_edit = QLineEdit(box)
        self._scope_target_edit.setPlaceholderText("子样本集 ID 或样本 UID / alias")
        self._uids_edit = QLineEdit(box)
        self._uids_edit.setPlaceholderText("留空=当前范围全部样本；支持逗号分隔 UID 或 alias")
        tree_hint = QLabel("← 来自对象树选择", box)
        tree_hint.setObjectName("treeHintLabel")
        tree_hint.setStyleSheet("color: #94A3B8; font-size: 9pt;")
        tree_hint.setVisible(True)
        common_form.addRow("处理方法", self._action_combo)
        common_form.addRow("范围来源", self._scope_kind_combo)
        common_form.addRow("", tree_hint)
        common_form.addRow("范围目标", self._scope_target_edit)
        common_form.addRow("临时过滤", self._uids_edit)
        layout.addLayout(common_form)

        self._strict_check = QCheckBox("严格校验", box)
        self._strict_check.setChecked(True)
        self._overwrite_check = QCheckBox("允许覆盖已有结果", box)
        self._overwrite_check.setChecked(True)

        self._adv_options_toggle = QPushButton("▶ 高级选项", box)
        self._adv_options_toggle.setCheckable(True)
        self._adv_options_toggle.setFlat(True)
        self._adv_options_toggle.setStyleSheet("text-align: left; font-size: 9pt; color: #64748B;")
        self._adv_options_group = QWidget(box)
        adv_layout = QVBoxLayout(self._adv_options_group)
        adv_layout.setContentsMargins(8, 0, 0, 0)
        adv_layout.setSpacing(4)
        adv_layout.addWidget(self._strict_check)
        adv_layout.addWidget(self._overwrite_check)
        self._adv_options_group.setVisible(False)
        self._adv_options_toggle.toggled.connect(self._on_adv_options_toggle)
        layout.addWidget(self._adv_options_toggle)
        layout.addWidget(self._adv_options_group)

        self._specific_group = QGroupBox("动作专属参数", box)
        self._specific_form = QFormLayout(self._specific_group)
        layout.addWidget(self._specific_group)

        self._run_button = QPushButton("执行分析", box)
        self._run_button.clicked.connect(self._emit_process_request)
        self._cancel_button = QPushButton("中止", box)
        self._cancel_button.setObjectName("ProcessingCancelButton")
        self._cancel_button.clicked.connect(self.cancel_requested.emit)
        self._cancel_button.hide()
        button_row = QHBoxLayout()
        button_row.addWidget(self._run_button)
        button_row.addWidget(self._cancel_button)
        layout.addLayout(button_row)
        return box

    def _build_preview_group(self) -> QGroupBox:
        box = QGroupBox("结果预览", self)
        layout = QVBoxLayout(box)
        form = QFormLayout()
        self._preview_kind_combo = QComboBox(box)
        for preview_kind, label in _PREVIEW_KIND_LABELS.items():
            self._preview_kind_combo.addItem(label, preview_kind)
        self._preview_scope_combo = QComboBox(box)
        self._preview_scope_combo.addItem("当前 UID 子集", "subset")
        self._preview_scope_combo.addItem("全部已生成结果", "all")
        self._metadata_fields_edit = QLineEdit(box)
        self._metadata_fields_edit.setText("alias")
        self._features_edit = QLineEdit(box)
        self._features_edit.setText("max,rms")
        self._data_var_edit = QLineEdit(box)
        self._data_var_edit.setText("freqspec")
        self._peak_source_edit = QLineEdit(box)
        self._peak_source_edit.setText("accel")
        form.addRow("预览类型", self._preview_kind_combo)
        form.addRow("预览范围", self._preview_scope_combo)
        form.addRow("metadata 字段", self._metadata_fields_edit)
        form.addRow("标量特征", self._features_edit)
        form.addRow("序列表来源", self._data_var_edit)
        form.addRow("峰值来源", self._peak_source_edit)
        layout.addLayout(form)
        self._preview_button = QPushButton("生成预览表", box)
        self._preview_button.clicked.connect(self._emit_preview_request)
        return box

    def load_session(self, session: ProjectSession) -> None:
        """根据会话刷新页面。"""

        state = session.processing_state
        current_request = state.current_request
        if current_request is None:
            scope_target = ""
            if session.current_scope.subset_ids:
                scope_target = ",".join(session.current_scope.subset_ids)
            elif session.current_scope.sample_uids:
                scope_target = ",".join(session.current_scope.sample_uids)
            current_request = ProcessingRequestSnapshot(
                action_name=self.processing_request_values().action_name,
                scope_kind=session.current_scope.scope_kind,
                scope_target=scope_target,
                strict=self._strict_check.isChecked(),
                overwrite=self._overwrite_check.isChecked(),
            )
        self._page_header.set_summary_lines(
            f"当前范围：{session.current_scope.scope_kind}",
            f"当前动作：{current_request.action_name}",
            f"最近状态：{state.last_message or '选择动作后可执行'}",
        )
        self._set_combo_value(self._action_combo, current_request.action_name)
        self._set_combo_value(self._scope_kind_combo, current_request.scope_kind)
        self._scope_target_edit.setText(current_request.scope_target)
        self._uids_edit.setText(current_request.uids_text)
        self._strict_check.setChecked(current_request.strict)
        self._overwrite_check.setChecked(current_request.overwrite)
        self._rebuild_specific_params(current_request.action_name, current_request.action_params)

        capability = "、".join(session.capability_snapshot.data_slots) or "无"
        preview_name = _PREVIEW_KIND_LABELS.get(state.preview_kind, state.preview_kind or "标量表")
        self._summary.setText(
            "\n".join(
                (
                    f"当前能力：{capability}",
                    f"预览状态：{state.preview_title or '生成预览表后显示'}",
                    f"预览类型：{preview_name}",
                )
            )
        )
        self._phase_label.setText(
            "处理状态：" + ("正在执行..." if state.busy else (state.last_message or "选择动作后即可执行。"))
        )
        has_preview_rows = any((state.scalar_rows, state.series_rows, state.peaks_rows))
        self._empty_state_label.setVisible(not has_preview_rows)
        self._empty_state_label.setText(
            "选择左侧动作后执行分析；如果只需检查已有结果，可先生成预览表。"
            if not state.last_failure_message
            else f"请先处理失败项，处理完成后这里会更新结果：{state.last_failure_message}"
        )

        self._set_combo_value(self._preview_kind_combo, state.preview_kind or "scalar_frame")
        self._set_combo_value(self._preview_scope_combo, state.preview_scope or "subset")
        _load_table(self._scalar_table, state.scalar_rows)
        _load_table(self._series_table, state.series_rows)
        _load_table(self._peaks_table, state.peaks_rows)

        gap_text = state.last_failure_message[:8] if state.last_failure_message else "0"
        if state.last_duration_ms > 0:
            secs = state.last_duration_ms // 1000
            mins, sec_part = divmod(secs, 60)
            duration_text = f"{mins:02d}:{sec_part:02d}"
        else:
            duration_text = "--:--"
        self._metrics_summary.setText(
            f"完成结果：{state.last_action_count} / 缺口：{gap_text} / 最近执行：{duration_text}"
        )

        can_restore_runtime = session.primary_runtime is None and session.import_state.source_path is not None
        enabled = not state.busy
        self._run_button.setEnabled(enabled)
        self._preview_button.setEnabled(enabled)
        self._run_button.setText("执行分析")
        self._cancel_button.setVisible(state.busy)
        self._cancel_button.setEnabled(state.busy)
        if state.busy:
            self._phase_label.setText("处理状态：正在执行...")
        elif can_restore_runtime:
            self._phase_label.setText("处理状态：主样本集运行态缺失，可先恢复运行态再执行分析。")

    def scope_selection(self) -> tuple[str, str]:
        """返回当前范围来源。"""

        return str(self._scope_kind_combo.currentData()), self._scope_target_edit.text().strip()

    def processing_request_values(self) -> ProcessingRequestSnapshot:
        """返回当前处理动作请求。"""

        return ProcessingRequestSnapshot(
            action_name=str(self._action_combo.currentData()),
            scope_kind=str(self._scope_kind_combo.currentData()),
            scope_target=self._scope_target_edit.text().strip(),
            uids_text=self._uids_edit.text().strip(),
            strict=self._strict_check.isChecked(),
            overwrite=self._overwrite_check.isChecked(),
            action_params=self._collect_action_params(),
        )

    def preview_request_values(self) -> ProcessingPreviewRequestSnapshot:
        """返回当前预览请求。"""

        return ProcessingPreviewRequestSnapshot(
            preview_kind=str(self._preview_kind_combo.currentData()),
            preview_scope=str(self._preview_scope_combo.currentData()),
            uids_text=self._uids_edit.text().strip(),
            metadata_fields=_split_csv_text(self._metadata_fields_edit.text()),
            features=_split_csv_text(self._features_edit.text()),
            data_var=self._data_var_edit.text().strip(),
            peak_source=self._peak_source_edit.text().strip(),
        )

    def _on_adv_options_toggle(self, checked: bool) -> None:
        self._adv_options_group.setVisible(checked)
        self._adv_options_toggle.setText("▼ 高级选项" if checked else "▶ 高级选项")

    def _on_action_changed(self) -> None:
        self._rebuild_specific_params(str(self._action_combo.currentData()))

    def _set_action_value(self, action_name: str) -> None:
        self._set_combo_value(self._action_combo, action_name)
        self._rebuild_specific_params(action_name)

    def _rebuild_specific_params(self, action_name: str, values: dict[str, str] | None = None) -> None:
        self._specific_widgets = {}
        while self._specific_form.rowCount():
            self._specific_form.removeRow(0)
        spec = _ACTION_SPECS[action_name]
        if not spec.specific_params:
            self._specific_form.addRow("额外参数", QLabel("当前方法无专属参数", self._specific_group))
            return
        values = values or {}
        for param in spec.specific_params:
            editor = self._build_specific_editor(param, values.get(param.key, param.default_value))
            self._specific_widgets[param.key] = editor
            self._specific_form.addRow(param.label, editor)

    def _build_specific_editor(self, spec: ProcessingParameterSpec, value: str) -> QWidget:
        if spec.editor_kind == "choice":
            combo = QComboBox(self._specific_group)
            for label, option_value in spec.options:
                combo.addItem(label, option_value)
            self._set_combo_value(combo, value)
            return combo
        line_edit = QLineEdit(self._specific_group)
        line_edit.setPlaceholderText(spec.placeholder)
        line_edit.setText(value)
        return line_edit

    def _collect_action_params(self) -> dict[str, str]:
        values: dict[str, str] = {}
        for key, widget in self._specific_widgets.items():
            if isinstance(widget, QComboBox):
                values[key] = str(widget.currentData() or "")
            elif isinstance(widget, QLineEdit):
                values[key] = widget.text().strip()
        return values

    def _emit_process_request(self) -> None:
        self.process_requested.emit(self.processing_request_values())

    def _emit_preview_request(self) -> None:
        self.preview_requested.emit(self.preview_request_values())

    def _set_combo_value(self, combo: QComboBox, value: str) -> None:
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)


def _build_table_widget() -> QTableWidget:
    table = QTableWidget()
    table.setColumnCount(0)
    table.setRowCount(0)
    return table


def _split_csv_text(text: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in text.split(",") if item.strip())


def _load_table(table: QTableWidget, rows: tuple[tuple[str, ...], ...]) -> None:
    column_count = max((len(row) for row in rows), default=0)
    table.clear()
    table.setColumnCount(column_count)
    table.setRowCount(len(rows))
    for row_index, row in enumerate(rows):
        for column_index, value in enumerate(row):
            table.setItem(row_index, column_index, QTableWidgetItem(value))
    table.resizeColumnsToContents()
