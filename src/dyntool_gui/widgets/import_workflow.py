"""数据接入工作页。"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from dyntool import StorageScheme
from dyntool.storage import SampleLoadMode

from ..layout import LANDSCAPE_2K_PROFILE
from ..session import ImportKind, ImportState, ProjectSession


class ImportWorkflowWidget(QWidget):
    """数据接入配置面板（左侧窄列）。"""

    project_directory_requested = Signal()
    source_file_requested = Signal()
    source_directory_requested = Signal()
    preview_requested = Signal()
    deep_check_requested = Signal()
    execute_requested = Signal()
    cancel_requested = Signal()
    kind_changed = Signal(str)

    def __init__(self, parent: object | None = None) -> None:
        super().__init__(parent)
        self.setMaximumWidth(LANDSCAPE_2K_PROFILE.import_workflow_max_width)
        self._current_source_path: Path | None = None
        self._sample_batch_paths: tuple[Path, ...] = ()

        self._project_directory_edit = QLineEdit()
        self._project_directory_edit.setReadOnly(True)
        self._project_status = QLabel("请选择项目目录，确认后即可继续接入。")
        self._project_status.setWordWrap(True)

        self._kind_combo = QComboBox()
        self._kind_combo.addItem("打开样本集仓库", ImportKind.SAMPLE_SET)
        self._kind_combo.addItem("批量 CSV 生成新样本集", ImportKind.SAMPLE)
        self._kind_combo.currentIndexChanged.connect(self._emit_kind_changed)

        self._source_path_edit = QLineEdit()
        self._source_hint = QLabel("选择文件或目录后可检查并绑定。")
        self._source_hint.setWordWrap(True)
        self._source_file_button = QPushButton("选择文件")
        self._source_file_button.clicked.connect(self.source_file_requested.emit)
        self._source_dir_button = QPushButton("选择目录")
        self._source_dir_button.clicked.connect(self.source_directory_requested.emit)

        self._sample_set_group = self._build_sample_set_group()
        self._sample_csv_group = self._build_csv_basic_group()

        self._preview_text = QPlainTextEdit(self)
        self._preview_text.setReadOnly(True)
        self._preview_text.setMinimumHeight(72)
        self._preview_text.setMaximumHeight(88)
        self._units_text = QPlainTextEdit(self)
        self._units_text.setReadOnly(True)
        self._units_text.setMinimumHeight(72)
        self._units_text.setMaximumHeight(88)
        self._parameter_text = QPlainTextEdit(self)
        self._parameter_text.setReadOnly(True)
        self._parameter_text.setMinimumHeight(46)
        self._parameter_text.setMaximumHeight(60)

        self._advanced_toggle = QToolButton()
        self._advanced_toggle.setCheckable(True)
        self._advanced_toggle.setText("显示高级参数")
        self._advanced_toggle.toggled.connect(self._toggle_advanced_group)
        self._advanced_group = self._build_advanced_group()
        self._advanced_group.hide()

        self._busy_status = QLabel("", self)
        self._busy_status.setWordWrap(True)
        self._busy_status.hide()
        self._busy_progress = QProgressBar(self)
        self._busy_progress.hide()

        self._result_label = QLabel("绑定结果：绑定后会显示当前主样本集更新摘要。", self)
        self._result_label.setWordWrap(True)
        self._preview_button = QPushButton("轻量预览")
        self._preview_button.clicked.connect(self.preview_requested.emit)
        self._deep_check_button = QPushButton("深度检查单位")
        self._deep_check_button.clicked.connect(self.deep_check_requested.emit)
        self._execute_button = QPushButton("绑定为当前主样本集")
        self._execute_button.clicked.connect(self.execute_requested.emit)
        self._cancel_button = QPushButton("中止")
        self._cancel_button.clicked.connect(self.cancel_requested.emit)
        self._cancel_button.hide()

        self._stage_bar = self._build_stage_bar()

        self._preview_group = self._build_preview_card()
        self._result_card = self._build_result_card()

        project_card = self._build_project_card()
        source_card = self._build_source_card()

        source_column = QWidget(self)
        source_layout = QVBoxLayout(source_column)
        source_layout.setContentsMargins(6, 6, 6, 6)
        source_layout.setSpacing(6)
        source_layout.addWidget(self._stage_bar)
        source_layout.addWidget(project_card)
        source_layout.addWidget(source_card)
        source_layout.addStretch(1)
        source_layout.addWidget(self._busy_status)
        source_layout.addWidget(self._busy_progress)

        self._source_scroll = QScrollArea(self)
        self._source_scroll.setObjectName("ImportSourceScrollArea")
        self._source_scroll.setWidgetResizable(True)
        self._source_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._source_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._source_scroll.setWidget(source_column)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._source_scroll)

        self._sync_kind_ui()

    @property
    def import_kind(self) -> ImportKind:
        """返回当前导入类型。"""

        return ImportKind(self._kind_combo.currentData())

    @property
    def source_path(self) -> Path | None:
        """返回当前单一路径来源。"""

        text = self._source_path_edit.text().strip()
        if self._sample_batch_paths:
            return None
        if self._current_source_path is not None and (not text or text.startswith("已选择 ")):
            return self._current_source_path
        return Path(text).resolve() if text else self._current_source_path

    @property
    def sample_batch_paths(self) -> tuple[Path, ...]:
        """返回当前批量 CSV 文件列表。"""

        return self._sample_batch_paths

    @property
    def csv_read_options(self) -> dict[str, object]:
        """返回 CSV 读取参数。"""

        return {
            "sep": self._csv_sep.text() or ",",
            "header": _parse_optional_int(self._csv_header.text(), default=0),
            "index_col": _parse_optional_int(self._csv_index_col.text(), default=0),
            "encoding": self._csv_encoding.text() or "utf-8",
            "skiprows": _parse_optional_int(self._csv_skiprows.text(), default=0),
            "decimal": self._csv_decimal.text() or ".",
        }

    @property
    def requested_scheme(self) -> StorageScheme | None:
        """返回当前请求的存储方式。"""

        return self._scheme_combo.currentData()

    @property
    def load_mode(self) -> SampleLoadMode:
        """返回当前加载方式。"""

        return SampleLoadMode(self._load_mode_combo.currentData())

    @property
    def workers(self) -> int:
        """返回当前并行任务数。"""

        return max(1, int(self._workers_edit.text().strip() or "1"))

    @property
    def strict(self) -> bool:
        """返回严格校验开关。"""

        return self._strict_check.isChecked()

    @property
    def advanced_expanded(self) -> bool:
        """返回高级参数区展开状态。"""

        return self._advanced_toggle.isChecked()

    def set_import_kind(self, kind: ImportKind) -> None:
        """设置导入类型。"""

        index = self._kind_combo.findData(kind)
        if index >= 0:
            self._kind_combo.blockSignals(True)
            self._kind_combo.setCurrentIndex(index)
            self._kind_combo.blockSignals(False)
        self._sync_kind_ui()

    def set_project_directory(self, path: str | Path) -> None:
        """更新项目目录。"""

        self._project_directory_edit.setText(str(Path(path)))

    def set_source_path(self, path: str | Path | None) -> None:
        """更新单一路径来源。"""

        self._sample_batch_paths = ()
        self._current_source_path = None if path is None else Path(path).resolve()
        self._source_path_edit.setText("" if self._current_source_path is None else str(self._current_source_path))

    def set_sample_batch_paths(self, paths: list[str | Path] | tuple[str | Path, ...]) -> None:
        """更新批量 CSV 来源。"""

        self._sample_batch_paths = tuple(Path(path).resolve() for path in paths)
        self._current_source_path = None
        if not self._sample_batch_paths:
            self._source_path_edit.clear()
            return
        first_parent = self._sample_batch_paths[0].parent
        self._source_path_edit.setText(f"已选择 {len(self._sample_batch_paths)} 个 CSV 文件，目录：{first_parent}")

    def load_session(self, session: ProjectSession) -> None:
        """根据会话刷新工作流页。"""

        state = session.import_state
        self.set_import_kind(state.import_kind)
        self._project_directory_edit.setText(str(session.workdir) if state.project_directory_selected else "")
        project_directory_ready = state.project_directory_selected and not session.demo_key
        self._project_status.setText(
            "项目目录已确认，可以继续检查并绑定。"
            if project_directory_ready
            else "请选择项目目录，确认后即可继续接入。"
        )
        if state.sample_batch_paths:
            self.set_sample_batch_paths(state.sample_batch_paths)
        elif not self._source_path_edit.hasFocus():
            self.set_source_path(state.source_path)

        self._csv_sep.setText(state.csv_sep)
        self._csv_header.setText(state.csv_header)
        self._csv_index_col.setText(state.csv_index_col)
        self._csv_encoding.setText(state.csv_encoding)
        self._csv_skiprows.setText(state.csv_skiprows)
        self._csv_decimal.setText(state.csv_decimal)
        self._workers_edit.setText(str(state.workers))
        self._strict_check.setChecked(state.strict)
        self._set_combo_value(self._scheme_combo, state.requested_scheme)
        self._set_combo_value(self._load_mode_combo, state.load_mode.value)
        self._update_stage_bar(state)

        self._advanced_toggle.blockSignals(True)
        self._advanced_toggle.setChecked(state.advanced_expanded)
        self._advanced_toggle.setText("隐藏高级参数" if state.advanced_expanded else "显示高级参数")
        self._advanced_toggle.blockSignals(False)
        self._advanced_group.setVisible(state.advanced_expanded and state.import_kind is ImportKind.SAMPLE)

        preview_lines = () if session.demo_key else state.preview_lines
        unit_lines = () if session.demo_key else state.unit_lines
        parameter_lines = () if session.demo_key else state.parameter_lines
        self._preview_text.setPlainText("\n".join(preview_lines or ("执行预览后显示摘要。",)))
        self._units_text.setPlainText("\n".join(unit_lines or ("需要时可执行单位检查。",)))
        parameter_lines = (
            parameter_lines + state.timing_lines if state.timing_lines and not session.demo_key else parameter_lines
        )
        self._parameter_text.setPlainText("\n".join(parameter_lines or ("检查后显示参数与耗时。",)))

        busy_text = state.progress_text
        if state.busy_detail:
            busy_text = f"{busy_text}：{state.busy_detail}"
        self._busy_status.setText(busy_text)
        self._busy_status.setVisible(state.busy)
        self._busy_progress.setVisible(state.busy)
        if state.busy:
            if state.progress_total in {None, 0}:
                self._busy_progress.setRange(0, 0)
            else:
                self._busy_progress.setRange(0, state.progress_total)
                self._busy_progress.setValue(state.progress_current or 0)

        result_message = "绑定后会显示当前主样本集更新摘要。"
        if not session.demo_key:
            result_message = state.last_success or state.last_error or result_message
        result_parts = [result_message]
        if state.last_cleanup_status:
            result_parts.append(state.last_cleanup_status)
        self._result_label.setText(f"绑定结果：{'；'.join(result_parts)}")

        self._set_busy_enabled(not state.busy)
        self._preview_button.setEnabled(
            (not state.busy) and state.project_directory_selected and state.has_import_source
        )
        self._deep_check_button.setEnabled(
            (not state.busy)
            and state.import_kind is ImportKind.SAMPLE_SET
            and state.project_directory_selected
            and state.has_import_source
            and bool(state.preview_lines)
        )
        self._execute_button.setEnabled((not state.busy) and state.can_execute)
        self._cancel_button.setText("中止" if state.cancellable else "收尾中不可中止")
        self._cancel_button.setVisible(state.busy)
        self._cancel_button.setEnabled(state.busy and state.cancellable and not state.cancel_requested)
        self._sync_kind_ui()

    def _build_stage_bar(self) -> QWidget:
        container = QWidget(self)
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self._stage_summary = QLabel("项目待确认 / 来源待选择 / 检查后可绑定", container)
        self._stage_summary.setWordWrap(True)
        self._stage_summary.setProperty("cardRole", "heroSummary")
        layout.addWidget(self._stage_summary, 1)
        return container

    def _build_project_card(self) -> QGroupBox:
        box = QGroupBox("项目上下文")
        layout = QVBoxLayout(box)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        row = QHBoxLayout()
        row.addWidget(self._project_directory_edit, 1)
        button = QPushButton("选择项目目录")
        button.clicked.connect(self.project_directory_requested.emit)
        row.addWidget(button)
        layout.addLayout(row)
        layout.addWidget(self._project_status)
        return box

    def _build_source_card(self) -> QGroupBox:
        box = QGroupBox("接入来源")
        layout = QVBoxLayout(box)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form.addRow("接入模式", self._kind_combo)
        form.addRow("来源路径", self._source_path_edit)
        layout.addLayout(form)

        button_row = QHBoxLayout()
        button_row.addWidget(self._source_file_button)
        button_row.addWidget(self._source_dir_button)
        layout.addLayout(button_row)

        parameter_layout = QVBoxLayout()
        parameter_layout.setSpacing(6)
        parameter_layout.addWidget(self._sample_set_group)
        parameter_layout.addWidget(self._sample_csv_group)
        layout.addLayout(parameter_layout)
        layout.addWidget(self._advanced_toggle)
        layout.addWidget(self._advanced_group)
        layout.addWidget(self._source_hint)
        return box

    def _build_preview_card(self) -> QGroupBox:
        self._preview_group = QGroupBox("检查结果", self)
        layout = QVBoxLayout(self._preview_group)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        layout.addWidget(self._build_text_card("预览摘要", self._preview_text))
        layout.addWidget(self._build_text_card("单位检查", self._units_text))
        layout.addWidget(self._build_text_card("参数与耗时", self._parameter_text))
        return self._preview_group

    def _build_result_card(self) -> QGroupBox:
        box = QGroupBox("绑定结果", self)
        layout = QVBoxLayout(box)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        layout.addWidget(QLabel("目标绑定：当前项目主样本集"))
        layout.addWidget(self._busy_status)
        layout.addWidget(self._busy_progress)
        buttons = QHBoxLayout()
        buttons.setSpacing(6)
        buttons.addWidget(self._preview_button)
        buttons.addWidget(self._deep_check_button)
        buttons.addWidget(self._execute_button)
        buttons.addWidget(self._cancel_button)
        layout.addLayout(buttons)
        layout.addWidget(self._result_label)
        return box

    def _update_stage_bar(self, state: ImportState) -> None:
        has_check = bool(state.preview_lines) or bool(state.unit_lines) or bool(state.parameter_lines)
        bind_ready = state.can_execute or bool(state.last_success)
        parts = (
            "项目已确认" if state.project_directory_selected else "项目待确认",
            "来源已选择" if state.has_import_source else "来源待选择",
            "检查已完成" if has_check else "尚未检查",
            "可绑定" if bind_ready else "尚不可绑定",
        )
        self._stage_summary.setText(" / ".join(parts))

    def _build_sample_set_group(self) -> QGroupBox:
        box = QGroupBox("样本集来源参数")
        form = QFormLayout(box)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self._scheme_combo = QComboBox()
        self._scheme_combo.addItem("自动识别", None)
        self._scheme_combo.addItem("单 H5 文件（SET_H5）", StorageScheme.SET_H5)
        self._scheme_combo.addItem("SQLite + H5 仓库（SET_SQLITE_H5）", StorageScheme.SET_SQLITE_H5)
        self._scheme_combo.addItem("目录仓库（SET_DIR）", StorageScheme.SET_DIR)
        self._scheme_combo.addItem("属性表仓库（SET_ATTR_TABLE）", StorageScheme.SET_ATTR_TABLE)
        self._load_mode_combo = QComboBox()
        self._load_mode_combo.addItem("仅元数据（METADATA_ONLY）", SampleLoadMode.METADATA_ONLY.value)
        self._load_mode_combo.addItem("按需加载（LAZY）", SampleLoadMode.LAZY.value)
        self._load_mode_combo.addItem("全部加载（EAGER）", SampleLoadMode.EAGER.value)
        self._workers_edit = QLineEdit("1")
        self._strict_check = QCheckBox("启用严格校验")
        self._strict_check.setChecked(True)
        form.addRow("存储方式", self._scheme_combo)
        form.addRow("加载方式", self._load_mode_combo)
        form.addRow("并行任务数", self._workers_edit)
        form.addRow("严格校验", self._strict_check)
        return box

    def _build_csv_basic_group(self) -> QGroupBox:
        box = QGroupBox("样本来源参数")
        form = QFormLayout(box)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self._csv_sep = QLineEdit(",")
        self._csv_header = QLineEdit("0")
        self._csv_index_col = QLineEdit("0")
        self._csv_encoding = QLineEdit("utf-8")
        form.addRow("分隔符", self._csv_sep)
        form.addRow("表头行", self._csv_header)
        form.addRow("索引列", self._csv_index_col)
        form.addRow("编码", self._csv_encoding)
        return box

    def _build_advanced_group(self) -> QGroupBox:
        box = QGroupBox("高级参数")
        layout = QVBoxLayout(box)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        self._advanced_stack = QStackedWidget()
        self._advanced_stack.addWidget(QWidget())
        self._advanced_stack.addWidget(self._build_sample_advanced_page())
        layout.addWidget(self._advanced_stack)
        return box

    def _build_sample_advanced_page(self) -> QWidget:
        page = QWidget()
        layout = QFormLayout(page)
        layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self._csv_skiprows = QLineEdit("0")
        self._csv_decimal = QLineEdit(".")
        layout.addRow("跳过行数", self._csv_skiprows)
        layout.addRow("小数点符号", self._csv_decimal)
        return page

    def _build_text_card(self, title: str, editor: QPlainTextEdit) -> QGroupBox:
        box = QGroupBox(title)
        layout = QVBoxLayout(box)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.addWidget(editor)
        return box

    def _toggle_advanced_group(self, checked: bool) -> None:
        sample_mode = self.import_kind is ImportKind.SAMPLE
        self._advanced_group.setVisible(checked and sample_mode)
        self._advanced_toggle.setText("隐藏高级参数" if checked else "显示高级参数")

    def _emit_kind_changed(self) -> None:
        self._sync_kind_ui()
        self.kind_changed.emit(self.import_kind.value)

    def _sync_kind_ui(self) -> None:
        sample_mode = self.import_kind is ImportKind.SAMPLE
        self._sample_set_group.setVisible(not sample_mode)
        self._sample_csv_group.setVisible(sample_mode)
        self._advanced_toggle.setVisible(sample_mode)
        self._advanced_group.setVisible(sample_mode and self._advanced_toggle.isChecked())
        self._advanced_stack.setCurrentIndex(1 if sample_mode else 0)
        self._source_file_button.setText("选择 CSV 文件" if sample_mode else "选择文件")
        self._source_dir_button.setText("选择 CSV 目录" if sample_mode else "选择目录")
        self._deep_check_button.setVisible(not sample_mode)
        self._source_hint.setText(
            "选择 CSV 文件或目录后可预览并绑定。" if sample_mode else "选择文件或目录后可检查并绑定。"
        )

    def _set_busy_enabled(self, enabled: bool) -> None:
        for widget in (
            self._kind_combo,
            self._source_path_edit,
            self._source_file_button,
            self._source_dir_button,
            self._scheme_combo,
            self._load_mode_combo,
            self._workers_edit,
            self._strict_check,
            self._csv_sep,
            self._csv_header,
            self._csv_index_col,
            self._csv_encoding,
            self._csv_skiprows,
            self._csv_decimal,
            self._advanced_toggle,
        ):
            widget.setEnabled(enabled)

    def _set_combo_value(self, combo: QComboBox, value: object) -> None:
        index = combo.findData(value)
        combo.setCurrentIndex(index if index >= 0 else 0)


def _parse_optional_int(value: str, *, default: int | None = None) -> int | None:
    text = value.strip()
    if text == "":
        return default
    return int(text)
