"""筛选与子样本集工作页。"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFrame,
    QFormLayout,
    QGridLayout,
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
    QHeaderView,
    QVBoxLayout,
    QWidget,
)

from ..layout import LANDSCAPE_1080P_PROFILE
from ..session import FilterSpec, MetadataFilterClause, MetadataHookSpec, ProjectSession


class SubsetWorkspace(QWidget):
    """筛选与子样本集页。"""

    preview_requested = Signal(object)
    save_requested = Signal(str, str, bool)
    delete_requested = Signal(str)
    recalculate_requested = Signal(str)
    use_scope_requested = Signal(str)
    selection_requested = Signal(str)
    reset_scope_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._hook_specs: tuple[MetadataHookSpec, ...] = ()
        self._hook_widgets: dict[str, object] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.setObjectName("SubsetWorkspaceSplitter")
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self._build_filter_panel_container())
        splitter.addWidget(self._build_preview_panel())
        splitter.addWidget(self._build_saved_panel_container())
        splitter.setHandleWidth(6)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        splitter.setSizes([300, 900, 280])
        layout.addWidget(splitter)

    def _build_filter_panel_container(self) -> QWidget:
        panel = self._build_filter_panel()
        panel.setMaximumWidth(LANDSCAPE_1080P_PROFILE.side_panel_max_width)
        panel.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.MinimumExpanding)
        self._filter_scroll = QScrollArea(self)
        self._filter_scroll.setObjectName("SubsetFilterScrollArea")
        self._filter_scroll.setMinimumWidth(260)
        self._filter_scroll.setMaximumWidth(LANDSCAPE_1080P_PROFILE.side_panel_max_width)
        self._filter_scroll.setWidgetResizable(True)
        self._filter_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._filter_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._filter_scroll.setWidget(panel)
        return self._filter_scroll

    def _build_filter_panel(self) -> QWidget:
        container = QWidget(self)
        container.setObjectName("SubsetPreviewPanel")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        self._metadata_hook_group = QGroupBox("metadata 字段筛选", container)
        self._metadata_hook_form = QFormLayout(self._metadata_hook_group)
        layout.addWidget(self._metadata_hook_group)

        extra_box = QGroupBox("辅助条件", container)
        extra_form = QFormLayout(extra_box)
        self._keyword_edit = QLineEdit(extra_box)
        self._keyword_edit.setPlaceholderText("匹配 UID 或 alias")
        self._data_categories_edit = QLineEdit(extra_box)
        self._data_categories_edit.setPlaceholderText("例如 accel,freqspec")
        self._result_categories_edit = QLineEdit(extra_box)
        self._result_categories_edit.setPlaceholderText("例如 zvl,otovl")
        self._subset_name_edit = QLineEdit(extra_box)
        self._subset_name_edit.setPlaceholderText("子样本集名称")
        self._note_edit = QLineEdit(extra_box)
        self._note_edit.setPlaceholderText("说明")
        self._sort_by_edit = QLineEdit(extra_box)
        self._sort_by_edit.setPlaceholderText("例如 point、case、alias")
        self._sort_desc_combo = QComboBox(extra_box)
        self._sort_desc_combo.addItem("升序", False)
        self._sort_desc_combo.addItem("降序", True)
        self._limit_edit = QLineEdit(extra_box)
        self._limit_edit.setPlaceholderText("默认 200，最大 200")
        self._offset_edit = QLineEdit(extra_box)
        self._offset_edit.setPlaceholderText("默认 0")
        extra_form.addRow("关键词", self._keyword_edit)
        extra_form.addRow("原始数据存在", self._data_categories_edit)
        extra_form.addRow("分析结果存在", self._result_categories_edit)
        extra_form.addRow("排序字段", self._sort_by_edit)
        extra_form.addRow("排序方向", self._sort_desc_combo)
        extra_form.addRow("分页数量", self._limit_edit)
        extra_form.addRow("分页偏移", self._offset_edit)
        extra_form.addRow("子样本集名称", self._subset_name_edit)
        extra_form.addRow("说明", self._note_edit)
        layout.addWidget(extra_box)

        actions = QGridLayout()
        actions.setSpacing(6)
        self._preview_button = QPushButton("预览命中", container)
        self._preview_button.clicked.connect(self._emit_preview_request)
        self._save_dynamic_button = QPushButton("保存为动态子集", container)
        self._save_dynamic_button.clicked.connect(self._emit_save_dynamic_request)
        self._save_frozen_button = QPushButton("保存为冻结快照", container)
        self._save_frozen_button.clicked.connect(self._emit_save_frozen_request)
        self._use_current_button = QPushButton("设为当前范围", container)
        self._use_current_button.clicked.connect(self._emit_use_scope_request)
        actions.addWidget(self._preview_button, 0, 0)
        actions.addWidget(self._save_dynamic_button, 0, 1)
        actions.addWidget(self._save_frozen_button, 1, 0)
        actions.addWidget(self._use_current_button, 1, 1)
        layout.addLayout(actions)

        self._status_label = QLabel("设置条件后预览命中结果。", container)
        self._status_label.setWordWrap(True)
        self._status_label.setProperty("cardRole", "status")
        layout.addWidget(self._status_label)
        layout.addStretch(1)
        return container

    def _build_preview_panel(self) -> QWidget:
        container = QWidget(self)
        container.setObjectName("SubsetPreviewRegion")
        container.setMinimumWidth(560)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)
        self._preview_header = QLabel("metadata 预览", container)
        self._preview_header.setProperty("cardRole", "header")
        self._preview_header.setWordWrap(True)
        layout.addWidget(self._preview_header)
        self._preview_table = QTableWidget(container)
        self._preview_table.setObjectName("SubsetMetadataPreviewTable")
        self._preview_table.setMinimumWidth(560)
        self._configure_table(self._preview_table)
        layout.addWidget(self._preview_table, 1)
        return container

    def _build_saved_panel_container(self) -> QWidget:
        self._saved_panel_container = self._build_saved_panel()
        self._saved_panel_container.setObjectName("SubsetSavedPanel")
        self._saved_panel_container.setMaximumWidth(LANDSCAPE_1080P_PROFILE.saved_panel_max_width)
        self._saved_panel_container.setMinimumWidth(220)
        return self._saved_panel_container

    def _build_saved_panel(self) -> QWidget:
        container = QWidget(self)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        self._saved_header = QLabel("已保存子样本集", container)
        self._saved_header.setProperty("cardRole", "header")
        layout.addWidget(self._saved_header)
        self._saved_table = QTableWidget(container)
        self._saved_table.setObjectName("SubsetSavedTable")
        self._configure_table(self._saved_table)
        self._saved_table.itemSelectionChanged.connect(self._emit_selection_requested)
        layout.addWidget(self._saved_table, 1)
        buttons = QHBoxLayout()
        self._recalc_button = QPushButton("重算快照", container)
        self._recalc_button.clicked.connect(self._emit_recalculate_request)
        self._delete_button = QPushButton("删除", container)
        self._delete_button.clicked.connect(self._emit_delete_request)
        self._reset_scope_button = QPushButton("回到全部样本", container)
        self._reset_scope_button.clicked.connect(self.reset_scope_requested.emit)
        buttons.addWidget(self._recalc_button)
        buttons.addWidget(self._delete_button)
        buttons.addWidget(self._reset_scope_button)
        layout.addLayout(buttons)
        return container

    def load_session(self, session: ProjectSession) -> None:
        """根据会话刷新页面。"""

        state = session.subset_state
        self._set_hook_specs(state.metadata_hook_specs)
        self._apply_filter_spec(state.filter_spec)
        self._status_label.setText(
            " / ".join(
                filter(
                    None,
                    (
                        f"范围：{session.current_scope.scope_kind}",
                        f"命中：{state.preview_count}",
                        f"条件：{state.current_condition_summary or '未设置筛选条件'}",
                        f"状态：{state.last_message or '设置条件后可预览'}",
                        "" if not state.last_failure_message else f"失败：{state.last_failure_message}",
                    ),
                )
            )
        )
        self._preview_header.setText(f"metadata 预览：命中 {state.preview_count} 个样本（最多显示 200 行）")
        self._load_table(self._preview_table, state.preview_columns, state.preview_rows)
        subset_rows = tuple(
            (item.id, item.name, str(item.sample_count), item.updated_at, "冻结快照" if item.frozen else "动态规则")
            for item in state.subsets
        )
        self._load_table(self._saved_table, ("ID", "名称", "样本数", "更新时间", "类型"), subset_rows)
        self._saved_table.setColumnHidden(0, True)
        self._saved_table.setColumnHidden(3, True)
        self._saved_table.horizontalHeader().setStretchLastSection(True)
        self._select_saved_subset(state.selected_subset_id)

    def metadata_hook_specs(self) -> tuple[MetadataHookSpec, ...]:
        """返回当前 metadata hook 规格。"""

        return self._hook_specs

    def save_editor_values(self) -> tuple[str, str]:
        """返回当前子样本集名称与说明。"""

        return self._subset_name_edit.text().strip(), self._note_edit.text().strip()

    def selected_subset_id(self) -> str:
        """返回当前选中的子样本集 ID。"""

        return self._selected_subset_id()

    def scope_editor_values(self) -> FilterSpec:
        """返回当前结构化筛选条件。"""

        clauses: list[MetadataFilterClause] = []
        for spec in self._hook_specs:
            widget = self._hook_widgets.get(spec.field_name)
            if isinstance(widget, QComboBox):
                values = _split_csv(widget.currentText())
                if values:
                    clauses.append(
                        MetadataFilterClause(
                            field_name=spec.field_name,
                            field_kind=spec.field_kind,
                            match_mode="values",
                            values=values,
                        )
                    )
                continue
            if isinstance(widget, tuple):
                min_edit, max_edit = widget
                min_value = _parse_optional_float(min_edit.text())
                max_value = _parse_optional_float(max_edit.text())
                if min_value is not None or max_value is not None:
                    clauses.append(
                        MetadataFilterClause(
                            field_name=spec.field_name,
                            field_kind=spec.field_kind,
                            match_mode="range",
                            min_value=min_value,
                            max_value=max_value,
                        )
                    )
                continue
            if isinstance(widget, QLineEdit):
                text_value = widget.text().strip()
                if text_value:
                    clauses.append(
                        MetadataFilterClause(
                            field_name=spec.field_name,
                            field_kind=spec.field_kind,
                            match_mode="text",
                            text_value=text_value,
                        )
                    )

        return FilterSpec(
            metadata_clauses=tuple(clauses),
            keyword=self._keyword_edit.text().strip(),
            data_categories=_split_csv(self._data_categories_edit.text()),
            result_categories=_split_csv(self._result_categories_edit.text()),
            sort_by=self._sort_by_edit.text().strip(),
            sort_desc=bool(self._sort_desc_combo.currentData()),
            limit=_parse_optional_int(self._limit_edit.text()),
            offset=_parse_optional_int(self._offset_edit.text(), default=0) or 0,
        )

    def _set_hook_specs(self, specs: tuple[MetadataHookSpec, ...]) -> None:
        if specs == self._hook_specs:
            return
        self._hook_specs = specs
        self._hook_widgets = {}
        while self._metadata_hook_form.rowCount():
            self._metadata_hook_form.removeRow(0)
        for spec in specs:
            widget = self._build_hook_editor(spec)
            self._hook_widgets[spec.field_name] = widget
            if isinstance(widget, tuple):
                row_widget = QWidget(self._metadata_hook_group)
                row_layout = QHBoxLayout(row_widget)
                row_layout.setContentsMargins(0, 0, 0, 0)
                row_layout.setSpacing(6)
                row_layout.addWidget(widget[0])
                row_layout.addWidget(widget[1])
                self._metadata_hook_form.addRow(spec.display_name, row_widget)
            else:
                self._metadata_hook_form.addRow(spec.display_name, widget)

    def _build_hook_editor(self, spec: MetadataHookSpec) -> object:
        if spec.field_kind == "categorical":
            combo = QComboBox(self._metadata_hook_group)
            combo.setEditable(True)
            combo.addItem("")
            for value in spec.candidate_values:
                combo.addItem(value)
            combo.setCurrentIndex(0)
            combo.setEditText("")
            combo.lineEdit().setPlaceholderText("可输入多个值，逗号分隔")
            return combo
        if spec.field_kind == "numeric":
            min_edit = QLineEdit(self._metadata_hook_group)
            min_edit.setPlaceholderText("最小值")
            max_edit = QLineEdit(self._metadata_hook_group)
            max_edit.setPlaceholderText("最大值")
            return (min_edit, max_edit)
        line_edit = QLineEdit(self._metadata_hook_group)
        line_edit.setPlaceholderText("文本匹配")
        return line_edit

    def _apply_filter_spec(self, filter_spec: FilterSpec) -> None:
        clause_map = {clause.field_name: clause for clause in filter_spec.metadata_clauses}
        for spec in self._hook_specs:
            widget = self._hook_widgets.get(spec.field_name)
            clause = clause_map.get(spec.field_name)
            if isinstance(widget, QComboBox):
                widget.setEditText("" if clause is None else ",".join(clause.values))
            elif isinstance(widget, tuple):
                min_edit, max_edit = widget
                min_edit.setText("" if clause is None or clause.min_value is None else str(clause.min_value))
                max_edit.setText("" if clause is None or clause.max_value is None else str(clause.max_value))
            elif isinstance(widget, QLineEdit):
                widget.setText("" if clause is None else clause.text_value)
        self._keyword_edit.setText(filter_spec.keyword)
        self._data_categories_edit.setText(",".join(filter_spec.data_categories))
        self._result_categories_edit.setText(",".join(filter_spec.result_categories))
        self._sort_by_edit.setText(filter_spec.sort_by)
        self._sort_desc_combo.setCurrentIndex(1 if filter_spec.sort_desc else 0)
        self._limit_edit.setText("" if filter_spec.limit is None else str(filter_spec.limit))
        self._offset_edit.setText("" if filter_spec.offset == 0 else str(filter_spec.offset))

    def _emit_preview_request(self) -> None:
        self.preview_requested.emit(self.scope_editor_values())

    def _emit_save_dynamic_request(self) -> None:
        self.save_requested.emit(self._subset_name_edit.text().strip(), self._note_edit.text().strip(), False)

    def _emit_save_frozen_request(self) -> None:
        self.save_requested.emit(self._subset_name_edit.text().strip(), self._note_edit.text().strip(), True)

    def _emit_delete_request(self) -> None:
        subset_id = self._selected_subset_id()
        if subset_id:
            self.delete_requested.emit(subset_id)

    def _emit_recalculate_request(self) -> None:
        subset_id = self._selected_subset_id()
        if subset_id:
            self.recalculate_requested.emit(subset_id)

    def _emit_use_scope_request(self) -> None:
        subset_id = self._selected_subset_id()
        if subset_id:
            self.use_scope_requested.emit(subset_id)

    def _emit_selection_requested(self) -> None:
        subset_id = self._selected_subset_id()
        if subset_id:
            self.selection_requested.emit(subset_id)

    def _selected_subset_id(self) -> str:
        current_row = self._saved_table.currentRow()
        if current_row < 0:
            return ""
        item = self._saved_table.item(current_row, 0)
        return "" if item is None else item.text().strip()

    def _select_saved_subset(self, subset_id: str) -> None:
        if not subset_id:
            return
        for row in range(self._saved_table.rowCount()):
            item = self._saved_table.item(row, 0)
            if item is not None and item.text() == subset_id:
                was_blocked = self._saved_table.blockSignals(True)
                self._saved_table.setCurrentCell(row, 0)
                self._saved_table.blockSignals(was_blocked)
                return

    def _load_table(
        self,
        table: QTableWidget,
        headers: tuple[str, ...],
        rows: tuple[tuple[str, ...], ...],
    ) -> None:
        was_blocked = table.blockSignals(True)
        table.clear()
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(list(headers))
        table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            for column_index, value in enumerate(row):
                table.setItem(row_index, column_index, QTableWidgetItem(value))
        table.resizeColumnsToContents()
        table.verticalHeader().setDefaultSectionSize(24)
        table.blockSignals(was_blocked)

    def _configure_table(self, table: QTableWidget) -> None:
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        table.horizontalHeader().setStretchLastSection(True)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        table.verticalHeader().setDefaultSectionSize(24)


def _split_csv(text: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in text.split(",") if item.strip())


def _parse_optional_float(text: str) -> float | None:
    stripped = text.strip()
    if not stripped:
        return None
    return float(stripped)


def _parse_optional_int(text: str, *, default: int | None = None) -> int | None:
    stripped = text.strip()
    if not stripped:
        return default
    return int(stripped)
