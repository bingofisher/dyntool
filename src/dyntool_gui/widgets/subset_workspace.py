"""筛选与子样本集工作页。"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QCompleter,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QFormLayout,
    QGridLayout,
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
from ..session import FilterGroup, FilterPredicate, FilterSpec, MetadataFilterClause, MetadataHookSpec, ProjectSession
from .workspace_surfaces import WorkspaceSection


class _PredicateRuleRow(QFrame):
    """单条筛选谓词编辑行。"""

    changed = Signal()
    copy_requested = Signal(object)
    delete_requested = Signal(object)
    move_requested = Signal(object, int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("SubsetBooleanConditionBlock")
        self.setProperty("surfaceRole", "conditionBlock")
        self.field_combo = QComboBox(self)
        self.field_combo.setEditable(True)
        self.operator_combo = QComboBox(self)
        self.value_edit = QLineEdit(self)
        self._value_candidates: dict[str, tuple[str, ...]] = {}
        self._build()

    def set_field_options(
        self,
        field_paths: tuple[str, ...],
        value_candidates: dict[str, tuple[str, ...]] | None = None,
    ) -> None:
        """刷新字段候选并保留当前输入。"""

        self._value_candidates = dict(value_candidates or {})
        current = self.field_combo.currentText().strip()
        self.field_combo.blockSignals(True)
        self.field_combo.clear()
        self.field_combo.addItem("")
        self.field_combo.addItems(list(dict.fromkeys(field_paths)))
        if current:
            self.field_combo.setCurrentText(current)
        self.field_combo.blockSignals(False)
        self._refresh_value_completer()

    def set_predicate(self, predicate: FilterPredicate) -> None:
        """回填谓词。"""

        self.field_combo.setCurrentText(predicate.field_path)
        self._set_operator(predicate.operator)
        if isinstance(predicate.value, (tuple, list)):
            self.value_edit.setText(",".join(str(item) for item in predicate.value))
        else:
            self.value_edit.setText("" if predicate.value is None else str(predicate.value))
        self._sync_value_editor()
        self._refresh_value_completer()

    def predicate(self) -> FilterPredicate | None:
        """返回当前谓词；字段为空时返回 None。"""

        field_path = self.field_path()
        if not field_path:
            return None
        operator = str(self.operator_combo.currentData())
        if operator in {"exists", "not_exists"}:
            value: object = ()
        elif operator in {"in", "not_in"}:
            value = _split_csv(self.value_edit.text())
        else:
            value = self.value_edit.text().strip()
        return FilterPredicate(field_path=field_path, operator=operator, value=value)

    def field_path(self) -> str:
        """返回字段路径。"""

        return self.field_combo.currentText().strip()

    def _build(self) -> None:
        layout = QGridLayout(self)
        layout.setContentsMargins(8, 7, 8, 8)
        layout.setHorizontalSpacing(8)
        layout.setVerticalSpacing(6)

        caption = QLabel("条件", self)
        caption.setObjectName("SubsetBooleanConditionTitle")
        caption.setProperty("cardRole", "conditionTitle")
        field_label = QLabel("字段", self)
        field_label.setObjectName("SubsetBooleanFieldLabel")
        field_label.setProperty("cardRole", "fieldLabel")
        operator_label = QLabel("操作", self)
        operator_label.setObjectName("SubsetBooleanOperatorLabel")
        operator_label.setProperty("cardRole", "fieldLabel")
        value_label = QLabel("值", self)
        value_label.setObjectName("SubsetBooleanValueLabel")
        value_label.setProperty("cardRole", "fieldLabel")

        for label, value in (
            ("=", "="),
            ("!=", "!="),
            (">", ">"),
            (">=", ">="),
            ("<", "<"),
            ("<=", "<="),
            ("in", "in"),
            ("not in", "not_in"),
            ("contains", "contains"),
            ("not contains", "not_contains"),
            ("exists", "exists"),
            ("not exists", "not_exists"),
        ):
            self.operator_combo.addItem(label, value)
        self.field_combo.setMinimumWidth(0)
        self.operator_combo.setMinimumWidth(0)
        self.value_edit.setPlaceholderText("值；in/not in 使用逗号分隔")
        for widget in (self.field_combo, self.operator_combo, self.value_edit):
            widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self._up_button = QPushButton("上移", self)
        self._down_button = QPushButton("下移", self)
        self._copy_button = QPushButton("复制", self)
        self._delete_button = QPushButton("删除", self)
        self._up_button.setProperty("buttonRole", "ghost")
        self._down_button.setProperty("buttonRole", "ghost")
        self._copy_button.setProperty("buttonRole", "ghost")
        self._delete_button.setProperty("buttonRole", "ghost")

        layout.addWidget(caption, 0, 0, 1, 2)
        layout.addWidget(field_label, 1, 0)
        layout.addWidget(self.field_combo, 1, 1)
        layout.addWidget(operator_label, 2, 0)
        layout.addWidget(self.operator_combo, 2, 1)
        layout.addWidget(value_label, 3, 0)
        layout.addWidget(self.value_edit, 3, 1)
        action_row = QHBoxLayout()
        action_row.addStretch(1)
        action_row.addWidget(self._up_button)
        action_row.addWidget(self._down_button)
        action_row.addWidget(self._copy_button)
        action_row.addWidget(self._delete_button)
        layout.addLayout(action_row, 4, 0, 1, 2)
        layout.setColumnMinimumWidth(0, 44)
        layout.setColumnStretch(1, 1)

        self.operator_combo.currentIndexChanged.connect(self._handle_operator_changed)
        self.field_combo.currentTextChanged.connect(self._handle_field_changed)
        self.value_edit.textChanged.connect(self.changed.emit)
        self._delete_button.clicked.connect(lambda: self.delete_requested.emit(self))
        self._copy_button.clicked.connect(lambda: self.copy_requested.emit(self))
        self._up_button.clicked.connect(lambda: self.move_requested.emit(self, -1))
        self._down_button.clicked.connect(lambda: self.move_requested.emit(self, 1))
        self._sync_value_editor()

    def _handle_field_changed(self) -> None:
        self._refresh_value_completer()
        self.changed.emit()

    def _handle_operator_changed(self) -> None:
        self._sync_value_editor()
        self.changed.emit()

    def _sync_value_editor(self) -> None:
        needs_value = str(self.operator_combo.currentData()) not in {"exists", "not_exists"}
        self.value_edit.setEnabled(needs_value)
        if not needs_value:
            self.value_edit.clear()

    def _refresh_value_completer(self) -> None:
        candidates = self._value_candidates.get(self.field_path(), ())
        if candidates:
            completer = QCompleter(list(candidates), self.value_edit)
            completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            self.value_edit.setCompleter(completer)
            return
        self.value_edit.setCompleter(None)

    def _set_operator(self, value: str) -> None:
        index = self.operator_combo.findData(value)
        if index >= 0:
            self.operator_combo.setCurrentIndex(index)


class _RuleGroupEditor(QFrame):
    """可增删的布尔规则组编辑器。"""

    changed = Signal()
    copy_requested = Signal(object)
    delete_requested = Signal(object)
    move_requested = Signal(object, int)

    def __init__(self, parent: QWidget | None = None, *, title: str = "规则组", always_group: bool = False) -> None:
        super().__init__(parent)
        self.setObjectName("SubsetBooleanRuleGroup")
        self.setProperty("surfaceRole", "ruleGroup")
        self.operator_combo = QComboBox(self)
        self.not_check = QCheckBox("整体取反 NOT", self)
        self._rows: list[_PredicateRuleRow | _RuleGroupEditor] = []
        self._field_paths: tuple[str, ...] = ()
        self._value_candidates: dict[str, tuple[str, ...]] = {}
        self._always_group = always_group
        self._build(title)

    def add_predicate_row(self, predicate: FilterPredicate | None = None) -> _PredicateRuleRow:
        """添加一条条件。"""

        row = _PredicateRuleRow(self)
        row.set_field_options(self._field_paths, self._value_candidates)
        if predicate is not None:
            row.set_predicate(predicate)
        self._append_row(row)
        return row

    def add_group(self, group: FilterGroup | None = None) -> "_RuleGroupEditor":
        """添加一个子规则组。"""

        editor = _RuleGroupEditor(self, title="子规则组", always_group=True)
        editor.set_field_options(self._field_paths, self._value_candidates)
        if group is None:
            editor.add_predicate_row()
        else:
            editor.set_query(group)
        self._append_row(editor)
        return editor

    def clear_rules(self, *, add_empty: bool = False) -> None:
        """清空规则行。"""

        for row in tuple(self._rows):
            self._rows_layout.removeWidget(row)
            row.setParent(None)
            row.deleteLater()
        self._rows = []
        if add_empty:
            self.add_predicate_row()
        self.changed.emit()

    def set_field_options(
        self,
        field_paths: tuple[str, ...],
        value_candidates: dict[str, tuple[str, ...]] | None = None,
    ) -> None:
        """刷新字段候选。"""

        self._field_paths = field_paths
        self._value_candidates = dict(value_candidates or {})
        for row in self._rows:
            row.set_field_options(field_paths, self._value_candidates)

    def query(self) -> FilterPredicate | FilterGroup | None:
        """返回规则组对应的查询树。"""

        children: list[FilterPredicate | FilterGroup] = []
        for row in self._rows:
            child = row.predicate() if isinstance(row, _PredicateRuleRow) else row.query()
            if child is not None:
                children.append(child)
        if not children:
            return None
        if self._always_group or len(children) > 1 or self.not_check.isChecked():
            query: FilterPredicate | FilterGroup = FilterGroup(
                operator=str(self.operator_combo.currentData()),
                children=tuple(children),
            )
        else:
            query = children[0]
        if self.not_check.isChecked():
            query = FilterGroup(operator="not", children=(query,))
        return query

    def set_query(self, query: FilterPredicate | FilterGroup | None) -> None:
        """回填查询树。"""

        self.clear_rules()
        self.not_check.setChecked(False)
        if query is None:
            self.add_predicate_row()
            return
        root = query
        if isinstance(root, FilterGroup) and root.operator == "not" and root.children:
            self.not_check.setChecked(True)
            root = root.children[0]
        if isinstance(root, FilterPredicate):
            self.add_predicate_row(root)
            return
        self._set_operator(root.operator)
        for child in root.children:
            if isinstance(child, FilterPredicate):
                self.add_predicate_row(child)
            else:
                self.add_group(child)

    def _build(self, title: str) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        header = QFrame(self)
        header.setObjectName("SubsetBooleanRootControls" if not self._always_group else "SubsetBooleanGroupControls")
        header.setProperty("surfaceRole", "booleanGroupControls")
        header_layout = QGridLayout(header)
        header_layout.setContentsMargins(8, 6, 8, 6)
        header_layout.setHorizontalSpacing(8)
        title_label = QLabel(title, header)
        title_label.setProperty("cardRole", "fieldLabel")
        self.operator_combo.addItem("全部满足 AND", "and")
        self.operator_combo.addItem("任一满足 OR", "or")
        header_layout.addWidget(title_label, 0, 0)
        header_layout.addWidget(self.operator_combo, 0, 1)
        header_layout.addWidget(self.not_check, 1, 1)
        layout.addWidget(header)

        self._rows_layout = QVBoxLayout()
        self._rows_layout.setContentsMargins(0, 0, 0, 0)
        self._rows_layout.setSpacing(6)
        layout.addLayout(self._rows_layout)

        actions = QHBoxLayout()
        self._add_condition_button = QPushButton("添加条件", self)
        self._add_group_button = QPushButton("添加分组", self)
        self._delete_button = QPushButton("删除分组", self)
        self._up_button = QPushButton("上移", self)
        self._down_button = QPushButton("下移", self)
        self._copy_button = QPushButton("复制分组", self)
        for button in (
            self._add_condition_button,
            self._add_group_button,
            self._copy_button,
            self._delete_button,
            self._up_button,
            self._down_button,
        ):
            button.setProperty("buttonRole", "ghost")
        actions.addWidget(self._add_condition_button)
        actions.addWidget(self._add_group_button)
        actions.addStretch(1)
        if self._always_group:
            actions.addWidget(self._up_button)
            actions.addWidget(self._down_button)
            actions.addWidget(self._copy_button)
            actions.addWidget(self._delete_button)
        layout.addLayout(actions)

        self.operator_combo.currentIndexChanged.connect(self.changed.emit)
        self.not_check.toggled.connect(self.changed.emit)
        self._add_condition_button.clicked.connect(lambda: self.add_predicate_row())
        self._add_group_button.clicked.connect(lambda: self.add_group())
        self._delete_button.clicked.connect(lambda: self.delete_requested.emit(self))
        self._copy_button.clicked.connect(lambda: self.copy_requested.emit(self))
        self._up_button.clicked.connect(lambda: self.move_requested.emit(self, -1))
        self._down_button.clicked.connect(lambda: self.move_requested.emit(self, 1))

    def _append_row(self, row: _PredicateRuleRow | "_RuleGroupEditor") -> None:
        self._insert_row(row, len(self._rows))

    def _insert_row(self, row: _PredicateRuleRow | "_RuleGroupEditor", index: int) -> None:
        row.changed.connect(self.changed.emit)
        row.copy_requested.connect(self._copy_row)
        row.delete_requested.connect(self._remove_row)
        row.move_requested.connect(self._move_row)
        self._rows.insert(index, row)
        self._rows_layout.insertWidget(index, row)
        self.changed.emit()

    def _copy_row(self, row: object) -> None:
        if row not in self._rows:
            return
        target_index = self._rows.index(row) + 1  # type: ignore[arg-type]
        if isinstance(row, _PredicateRuleRow):
            self._insert_row(_PredicateRuleRow(self), target_index)
            copied = self._rows[target_index]
            if isinstance(copied, _PredicateRuleRow):
                copied.set_field_options(self._field_paths, self._value_candidates)
                predicate = row.predicate()
                if predicate is not None:
                    copied.set_predicate(predicate)
            return
        query = row.query()
        copied_group = _RuleGroupEditor(self, title="子规则组", always_group=True)
        copied_group.set_field_options(self._field_paths, self._value_candidates)
        if isinstance(query, FilterGroup):
            copied_group.set_query(query)
        else:
            copied_group.add_predicate_row(query if isinstance(query, FilterPredicate) else None)
        self._insert_row(copied_group, target_index)

    def _remove_row(self, row: object) -> None:
        if row not in self._rows:
            return
        typed_row = row  # type: ignore[assignment]
        self._rows.remove(typed_row)  # type: ignore[arg-type]
        self._rows_layout.removeWidget(typed_row)  # type: ignore[arg-type]
        typed_row.setParent(None)  # type: ignore[attr-defined]
        typed_row.deleteLater()  # type: ignore[attr-defined]
        self.changed.emit()

    def _move_row(self, row: object, offset: int) -> None:
        if row not in self._rows:
            return
        old_index = self._rows.index(row)  # type: ignore[arg-type]
        new_index = max(0, min(len(self._rows) - 1, old_index + offset))
        if new_index == old_index:
            return
        typed_row = self._rows.pop(old_index)
        self._rows.insert(new_index, typed_row)
        self._rows_layout.removeWidget(typed_row)
        self._rows_layout.insertWidget(new_index, typed_row)
        self.changed.emit()

    def _set_operator(self, value: str) -> None:
        index = self.operator_combo.findData(value)
        if index >= 0:
            self.operator_combo.setCurrentIndex(index)


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
        self._query_data_slots: tuple[str, ...] = ()
        self._query_eval_results: tuple[str, ...] = ()
        self._last_preview_count = 0
        self._last_scope_kind = "all_samples"
        self._global_busy_reason = ""

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
        splitter.setSizes([280, 1040, 240])
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
        container.setObjectName("SubsetFilterPanel")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        self._filter_panel_layout = layout
        self._build_filter_editor_dialog()
        self._build_save_dialog()

        layout.addWidget(self._build_filter_summary_section(container))

        save_box = WorkspaceSection("子集保存", container)
        self._save_summary_label = QLabel("预览命中后可保存动态子集或冻结快照。", save_box)
        self._save_summary_label.setObjectName("SubsetSaveSummaryLabel")
        self._save_summary_label.setProperty("cardRole", "status")
        self._save_summary_label.setWordWrap(True)
        save_box.body_layout().addWidget(self._save_summary_label)
        actions = QGridLayout()
        actions.setSpacing(6)
        self._preview_button = QPushButton("预览命中", container)
        self._preview_button.setObjectName("SubsetPreviewButton")
        self._preview_button.setProperty("buttonRole", "primary")
        self._preview_button.clicked.connect(self._emit_preview_request)
        self._open_save_dialog_button = QPushButton("保存子集", container)
        self._open_save_dialog_button.setObjectName("SubsetSaveDialogButton")
        self._open_save_dialog_button.setProperty("buttonRole", "secondary")
        self._open_save_dialog_button.clicked.connect(self._open_save_dialog)
        self._use_current_button = QPushButton("设为当前范围", container)
        self._use_current_button.setObjectName("SubsetUseScopeButton")
        self._use_current_button.setProperty("buttonRole", "secondary")
        self._use_current_button.clicked.connect(self._emit_use_scope_request)
        actions.addWidget(self._preview_button, 0, 0)
        actions.addWidget(self._open_save_dialog_button, 0, 1)
        actions.addWidget(self._use_current_button, 1, 0, 1, 2)
        save_box.body_layout().addLayout(actions)
        layout.addWidget(save_box)

        self._status_label = QLabel("设置条件后预览命中结果。", container)
        self._status_label.setWordWrap(True)
        self._status_label.setProperty("cardRole", "status")
        layout.addWidget(self._status_label)
        layout.addStretch(1)
        return container

    def _build_filter_editor_dialog(self) -> None:
        self._filter_dialog = QDialog(self)
        self._filter_dialog.setObjectName("SubsetFilterRulesDialog")
        self._filter_dialog.setWindowTitle("筛选规则")
        self._filter_dialog.resize(560, 760)
        self._filter_dialog.setSizeGripEnabled(True)
        self._query_dialog = self._filter_dialog

        dialog_layout = QVBoxLayout(self._filter_dialog)
        dialog_layout.setContentsMargins(10, 10, 10, 10)
        dialog_layout.setSpacing(8)
        scroll = QScrollArea(self._filter_dialog)
        scroll.setObjectName("SubsetFilterRulesScrollArea")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget(scroll)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(8)

        content_layout.addWidget(self._build_metadata_filter_section(content))
        content_layout.addWidget(self._build_query_section(content))
        content_layout.addWidget(self._build_aux_filter_section(content))
        content_layout.addStretch(1)
        scroll.setWidget(content)
        dialog_layout.addWidget(scroll, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("确定")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        buttons.accepted.connect(self._filter_dialog.accept)
        buttons.rejected.connect(self._filter_dialog.reject)
        dialog_layout.addWidget(buttons)

    def _build_save_dialog(self) -> None:
        self._save_dialog = QDialog(self)
        self._save_dialog.setObjectName("SubsetSaveDialog")
        self._save_dialog.setWindowTitle("保存子集")
        self._save_dialog.resize(480, 260)
        self._save_dialog.setSizeGripEnabled(True)
        layout = QVBoxLayout(self._save_dialog)
        section = WorkspaceSection("保存方式", self._save_dialog)
        form = QFormLayout()
        section.body_layout().addLayout(form)
        self._subset_name_edit = QLineEdit(section)
        self._subset_name_edit.setPlaceholderText("子样本集名称")
        self._note_edit = QLineEdit(section)
        self._note_edit.setPlaceholderText("说明")
        self._subset_name_edit.textChanged.connect(self._refresh_save_summary)
        self._note_edit.textChanged.connect(self._refresh_save_summary)
        form.addRow("名称", self._subset_name_edit)
        form.addRow("说明", self._note_edit)
        layout.addWidget(section)
        actions = QHBoxLayout()
        self._save_dynamic_button = QPushButton("保存为动态子集", self._save_dialog)
        self._save_dynamic_button.clicked.connect(self._accept_dynamic_save)
        self._save_frozen_button = QPushButton("保存为冻结快照", self._save_dialog)
        self._save_frozen_button.clicked.connect(self._accept_frozen_save)
        cancel_button = QPushButton("取消", self._save_dialog)
        cancel_button.clicked.connect(self._save_dialog.reject)
        actions.addWidget(self._save_dynamic_button)
        actions.addWidget(self._save_frozen_button)
        actions.addStretch(1)
        actions.addWidget(cancel_button)
        layout.addLayout(actions)

    def _open_save_dialog(self) -> None:
        values_before = self.save_editor_values()
        if self._save_dialog.exec() != QDialog.DialogCode.Accepted:
            self._subset_name_edit.setText(values_before[0])
            self._note_edit.setText(values_before[1])
            self._refresh_save_summary()

    def _build_filter_summary_section(self, parent: QWidget) -> QWidget:
        section = WorkspaceSection("筛选规则", parent)
        self._filter_summary_label = QLabel("未设置筛选规则。", section)
        self._filter_summary_label.setObjectName("SubsetFilterSummaryLabel")
        self._filter_summary_label.setProperty("cardRole", "status")
        self._filter_summary_label.setWordWrap(True)
        self._query_summary_label = self._filter_summary_label
        section.body_layout().addWidget(self._filter_summary_label)
        self._filter_edit_button = QPushButton("编辑筛选规则", section)
        self._filter_edit_button.setObjectName("SubsetFilterEditButton")
        self._filter_edit_button.setProperty("buttonRole", "secondary")
        self._filter_edit_button.clicked.connect(self._open_filter_dialog)
        self._query_edit_button = self._filter_edit_button
        section.body_layout().addWidget(self._filter_edit_button)
        self._refresh_filter_summary()
        self._refresh_save_summary()
        return section

    def _build_metadata_filter_section(self, parent: QWidget) -> QWidget:
        self._metadata_hook_group = WorkspaceSection("metadata 字段筛选", parent)
        self._metadata_hook_form = QFormLayout()
        self._metadata_hook_group.body_layout().addLayout(self._metadata_hook_form)
        self._metadata_empty_label = QLabel("当前数据没有可筛选 metadata 字段", self._metadata_hook_group)
        self._metadata_empty_label.setObjectName("SubsetMetadataEmptyStateLabel")
        self._metadata_empty_label.setProperty("cardRole", "emptyState")
        self._metadata_empty_label.setWordWrap(True)
        self._metadata_hook_group.body_layout().addWidget(self._metadata_empty_label)
        return self._metadata_hook_group

    def _build_aux_filter_section(self, parent: QWidget) -> QWidget:
        extra_box = WorkspaceSection("辅助条件", parent)
        extra_form = QFormLayout()
        extra_box.body_layout().addLayout(extra_form)
        self._keyword_edit = QLineEdit(extra_box)
        self._keyword_edit.setPlaceholderText("匹配 UID 或 alias")
        self._data_categories_edit = QLineEdit(extra_box)
        self._data_categories_edit.setPlaceholderText("例如 accel,freqspec")
        self._result_categories_edit = QLineEdit(extra_box)
        self._result_categories_edit.setPlaceholderText("例如 zvl,otovl")
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
        for widget in (
            self._keyword_edit,
            self._data_categories_edit,
            self._result_categories_edit,
            self._sort_by_edit,
            self._limit_edit,
            self._offset_edit,
        ):
            widget.textChanged.connect(self._refresh_filter_summary)
        self._sort_desc_combo.currentIndexChanged.connect(self._refresh_filter_summary)
        return extra_box

    def _build_query_section(self, parent: QWidget) -> QWidget:
        section = WorkspaceSection("布尔筛选", parent)
        self._rule_editor = _RuleGroupEditor(section, title="组合方式")
        self._rule_editor.setObjectName("SubsetBooleanRuleEditor")
        self._rule_editor.add_predicate_row()
        self._rule_editor.changed.connect(self._refresh_query_summary)
        self._query_operator_combo = self._rule_editor.operator_combo
        self._query_operator_combo.setObjectName("SubsetBooleanRootOperatorCombo")
        self._query_not_check = self._rule_editor.not_check
        self._query_not_check.setObjectName("SubsetBooleanRootNotCheck")
        section.body_layout().addWidget(self._rule_editor)
        return section

    def _open_query_dialog(self) -> None:
        self._open_filter_dialog()

    def _open_filter_dialog(self) -> None:
        filter_before = self.scope_editor_values()
        if self._filter_dialog.exec() == QDialog.DialogCode.Accepted:
            self._refresh_filter_summary()
            return
        self._apply_filter_spec(filter_before)
        self._refresh_filter_summary()

    def _refresh_query_summary(self, *_: object) -> None:
        self._refresh_filter_summary()

    def _refresh_filter_summary(self, *_: object) -> None:
        if not hasattr(self, "_filter_summary_label"):
            return
        parts: list[str] = []
        query_summary = self._describe_query(self._query_from_editor())
        if query_summary:
            parts.append(f"布尔：{query_summary}")
        hook_count = self._active_metadata_hook_count()
        if hook_count:
            parts.append(f"metadata 条件：{hook_count} 项")
        keyword = getattr(self, "_keyword_edit", None)
        if isinstance(keyword, QLineEdit) and keyword.text().strip():
            parts.append(f"关键词：{keyword.text().strip()}")
        data_slots = getattr(self, "_data_categories_edit", None)
        if isinstance(data_slots, QLineEdit) and data_slots.text().strip():
            parts.append(f"原始数据：{data_slots.text().strip()}")
        result_slots = getattr(self, "_result_categories_edit", None)
        if isinstance(result_slots, QLineEdit) and result_slots.text().strip():
            parts.append(f"分析结果：{result_slots.text().strip()}")
        sort_by = getattr(self, "_sort_by_edit", None)
        if isinstance(sort_by, QLineEdit) and sort_by.text().strip():
            direction = "降序" if bool(self._sort_desc_combo.currentData()) else "升序"
            parts.append(f"排序：{sort_by.text().strip()} {direction}")
        summary = "；".join(parts) if parts else "未设置筛选规则。"
        self._filter_summary_label.setText(summary)

    def _refresh_save_summary(self, *_: object) -> None:
        if not hasattr(self, "_save_summary_label"):
            return
        name = self._subset_name_edit.text().strip() or "未命名子集"
        note = self._note_edit.text().strip()
        parts = [f"名称：{name}", "保存方式：动态子集或冻结快照"]
        if note:
            parts.append(f"说明：{note}")
        self._save_summary_label.setText("；".join(parts))

    def _active_metadata_hook_count(self) -> int:
        count = 0
        for widget in self._hook_widgets.values():
            if isinstance(widget, QComboBox) and widget.currentText().strip():
                count += 1
            elif isinstance(widget, tuple):
                min_edit, max_edit = widget
                if min_edit.text().strip() or max_edit.text().strip():
                    count += 1
            elif isinstance(widget, QLineEdit) and widget.text().strip():
                count += 1
        return count

    def _describe_query(self, query: FilterGroup | FilterPredicate | None) -> str:
        if query is None:
            return ""
        if isinstance(query, FilterPredicate):
            return self._describe_predicate(query)
        if query.operator == "not" and query.children:
            child = self._describe_query(query.children[0])
            return f"NOT ({child})" if child else "NOT"
        joiner = " AND " if query.operator == "and" else " OR "
        children = tuple(filter(None, (self._describe_query(child) for child in query.children)))
        if not children:
            return ""
        return joiner.join(children)

    def _describe_predicate(self, predicate: FilterPredicate) -> str:
        operator_label = {
            "not_in": "not in",
            "not_contains": "not contains",
            "not_exists": "not exists",
        }.get(predicate.operator, predicate.operator)
        if predicate.operator in {"exists", "not_exists"}:
            return f"{predicate.field_path} {operator_label}"
        if isinstance(predicate.value, tuple):
            value_text = ",".join(str(item) for item in predicate.value)
        else:
            value_text = str(predicate.value)
        return f"{predicate.field_path} {operator_label} {value_text}".strip()

    def _build_preview_panel(self) -> QWidget:
        container = QWidget(self)
        container.setObjectName("SubsetPreviewRegion")
        container.setProperty("surfaceRole", "resultPanel")
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
        self._saved_panel_container.setProperty("surfaceRole", "summaryPanel")
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
        self._saved_table.itemSelectionChanged.connect(self._refresh_button_states)
        layout.addWidget(self._saved_table, 1)
        buttons = QHBoxLayout()
        self._recalc_button = QPushButton("重算动态子集", container)
        self._recalc_button.setObjectName("SubsetRecalculateButton")
        self._recalc_button.setProperty("buttonRole", "secondary")
        self._recalc_button.clicked.connect(self._emit_recalculate_request)
        self._delete_button = QPushButton("删除", container)
        self._delete_button.setObjectName("SubsetDeleteButton")
        self._delete_button.setProperty("buttonRole", "ghost")
        self._delete_button.clicked.connect(self._emit_delete_request)
        self._reset_scope_button = QPushButton("回到全部样本", container)
        self._reset_scope_button.setObjectName("SubsetResetScopeButton")
        self._reset_scope_button.setProperty("buttonRole", "ghost")
        self._reset_scope_button.clicked.connect(self.reset_scope_requested.emit)
        buttons.addWidget(self._recalc_button)
        buttons.addWidget(self._delete_button)
        buttons.addWidget(self._reset_scope_button)
        layout.addLayout(buttons)
        return container

    def load_session(self, session: ProjectSession) -> None:
        """根据会话刷新页面。"""

        state = session.subset_state
        self._last_preview_count = state.preview_count
        self._last_scope_kind = session.current_scope.scope_kind
        self._query_data_slots = tuple(session.capability_snapshot.data_slots)
        self._query_eval_results = tuple(session.capability_snapshot.eval_results)
        self._set_hook_specs(state.metadata_hook_specs)
        self._set_query_field_options()
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
        self._refresh_filter_summary()
        self._refresh_button_states()

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
            query=self._query_from_editor(),
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
        self._metadata_empty_label.setVisible(not specs)
        for spec in specs:
            widget = self._build_hook_editor(spec)
            self._hook_widgets[spec.field_name] = widget
            self._connect_hook_editor(widget)
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
        self._set_query_field_options()
        self._refresh_filter_summary()

    def _connect_hook_editor(self, widget: object) -> None:
        if isinstance(widget, QComboBox):
            widget.currentTextChanged.connect(self._refresh_filter_summary)
            return
        if isinstance(widget, tuple):
            min_edit, max_edit = widget
            min_edit.textChanged.connect(self._refresh_filter_summary)
            max_edit.textChanged.connect(self._refresh_filter_summary)
            return
        if isinstance(widget, QLineEdit):
            widget.textChanged.connect(self._refresh_filter_summary)

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
        self._apply_query(filter_spec.query)
        self._refresh_filter_summary()

    def _set_query_field_options(self) -> None:
        result_slots = tuple(
            dict.fromkeys(
                (
                    *self._query_eval_results,
                    *(slot for slot in self._query_data_slots if slot in {"zvl", "otovl", "fdmvl", "fpvdv"}),
                )
            )
        )
        field_paths = (
            "uid",
            "alias",
            *(f"metadata.{spec.field_name}" for spec in self._hook_specs),
            *(f"data.{slot}" for slot in self._query_data_slots if slot not in {"zvl", "otovl", "fdmvl", "fpvdv"}),
            *(f"result.{slot}" for slot in result_slots),
        )
        value_candidates = {
            f"metadata.{spec.field_name}": tuple(spec.candidate_values)
            for spec in self._hook_specs
            if spec.candidate_values
        }
        self._rule_editor.set_field_options(tuple(dict.fromkeys(field_paths)), value_candidates)

    def _query_from_editor(self) -> FilterGroup | FilterPredicate | None:
        return self._rule_editor.query()

    def _apply_query(self, query: FilterGroup | FilterPredicate | None) -> None:
        self._rule_editor.set_query(query)
        self._refresh_filter_summary()

    def _set_combo_value(self, combo: QComboBox, value: str) -> None:
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)

    def _emit_preview_request(self) -> None:
        self.preview_requested.emit(self.scope_editor_values())

    def _emit_save_dynamic_request(self) -> None:
        self.save_requested.emit(self._subset_name_edit.text().strip(), self._note_edit.text().strip(), False)

    def _emit_save_frozen_request(self) -> None:
        self.save_requested.emit(self._subset_name_edit.text().strip(), self._note_edit.text().strip(), True)

    def _accept_dynamic_save(self) -> None:
        self._emit_save_dynamic_request()
        self._save_dialog.accept()

    def _accept_frozen_save(self) -> None:
        self._emit_save_frozen_request()
        self._save_dialog.accept()

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
        if not self._saved_table.selectedRanges():
            return ""
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

    def set_global_task_state(self, *, busy: bool, reason: str = "") -> None:
        """同步 GUI 全局任务状态到子集页主入口。"""

        self._global_busy_reason = reason if busy else ""
        self._refresh_button_states()

    def _refresh_button_states(self) -> None:
        if self._global_busy_reason:
            for button in (
                self._preview_button,
                self._open_save_dialog_button,
                self._use_current_button,
                self._recalc_button,
                self._delete_button,
                self._reset_scope_button,
                self._filter_edit_button,
            ):
                self._set_button_available(button, False, self._global_busy_reason)
            return

        has_selection = bool(self._selected_subset_id())
        has_preview = self._last_preview_count > 0
        self._set_button_available(self._preview_button, True, "")
        self._set_button_available(self._open_save_dialog_button, has_preview, "请先预览命中结果。")
        self._set_button_available(self._use_current_button, has_selection, "请先选择已保存子集。")
        self._set_button_available(self._recalc_button, has_selection, "请先选择已保存子集。")
        self._set_button_available(self._delete_button, has_selection, "请先选择已保存子集。")
        self._set_button_available(
            self._reset_scope_button, self._last_scope_kind != "all_samples", "当前已经是全部样本。"
        )
        self._set_button_available(self._filter_edit_button, True, "")

    def _set_button_available(self, button: QPushButton, enabled: bool, reason: str) -> None:
        button.setEnabled(enabled)
        button.setToolTip("" if enabled else reason)
        button.setStatusTip("" if enabled else reason)

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
