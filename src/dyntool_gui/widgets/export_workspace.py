"""导出工作页。"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from ..session import ProjectSession


class ExportWorkspace(QWidget):
    """当前主样本集导出页。"""

    export_requested = Signal(str, str, str, object, object, str, str, bool, bool)
    compute_required = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self._build_left_panel())
        splitter.addWidget(self._build_right_panel())
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([360, 980])
        layout.addWidget(splitter)

    def _build_left_panel(self) -> QWidget:
        container = QWidget(self)
        container.setMinimumWidth(340)
        container.setMaximumWidth(420)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)
        layout.addWidget(self._build_form_group())
        self._status = QLabel("导出前先确认范围、类型与输出位置。", container)
        self._status.setWordWrap(True)
        self._status.setProperty("cardRole", "status")
        layout.addWidget(self._status)
        self._compute_button = QPushButton("计算所需结果", container)
        self._compute_button.clicked.connect(self._emit_compute_request)
        self._compute_button.hide()
        layout.addWidget(self._compute_button)
        layout.addStretch(1)
        return container

    def _build_right_panel(self) -> QWidget:
        container = QWidget(self)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)
        self._validation_label = QLabel("前置校验：确认参数后即可检查。", container)
        self._validation_label.setProperty("cardRole", "header")
        self._validation_label.setWordWrap(True)
        layout.addWidget(self._validation_label)
        self._result_label = QLabel("执行结果：导出后在这里显示。", container)
        self._result_label.setWordWrap(True)
        self._result_label.setProperty("cardRole", "status")
        layout.addWidget(self._result_label)
        layout.addStretch(1)
        return container

    def _build_form_group(self) -> QGroupBox:
        box = QGroupBox("导出参数", self)
        layout = QVBoxLayout(box)
        form = QFormLayout()
        self._scope_kind_combo = QComboBox(box)
        self._scope_kind_combo.addItem("全部样本", "all_samples")
        self._scope_kind_combo.addItem("当前子样本集", "saved_subset")
        self._scope_kind_combo.addItem("多个子样本集", "multi_subset_union")
        self._scope_kind_combo.addItem("临时手选", "temporary_selection")
        self._scope_kind_combo.addItem("单个样本", "single_sample")
        self._scope_target_edit = QLineEdit(box)
        self._scope_target_edit.setPlaceholderText("子样本集 ID 或样本 UID / alias")
        self._kind_combo = QComboBox(box)
        self._kind_combo.addItem("标量表", "scalar_frame")
        self._kind_combo.addItem("序列表", "series_frame")
        self._kind_combo.addItem("峰值表", "peaks_frame")
        self._kind_combo.addItem("当前图形", "current_plot_image")
        self._kind_combo.currentIndexChanged.connect(self._sync_format_options)
        self._output_edit = QLineEdit(box)
        self._format_combo = QComboBox(box)
        self._format_combo.addItems(("xlsx", "csv"))
        self._metadata_fields_edit = QLineEdit(box)
        self._metadata_fields_edit.setText("alias")
        self._features_edit = QLineEdit(box)
        self._features_edit.setText("max,rms")
        self._data_var_edit = QLineEdit(box)
        self._data_var_edit.setText("freqspec")
        self._source_edit = QLineEdit(box)
        self._source_edit.setText("accel")
        form.addRow("范围来源", self._scope_kind_combo)
        form.addRow("范围目标", self._scope_target_edit)
        form.addRow("导出类型", self._kind_combo)
        form.addRow("输出位置", self._output_edit)
        form.addRow("格式", self._format_combo)
        form.addRow("元数据字段", self._metadata_fields_edit)
        form.addRow("标量特征", self._features_edit)
        form.addRow("序列表来源", self._data_var_edit)
        form.addRow("峰值来源", self._source_edit)
        layout.addLayout(form)
        options = QHBoxLayout()
        self._include_plots = QCheckBox("包含图片", box)
        self._include_eval_summary = QCheckBox("包含评价摘要", box)
        self._include_eval_summary.setChecked(True)
        self._run_button = QPushButton("执行导出", box)
        self._run_button.clicked.connect(self._emit_export_request)
        options.addWidget(self._include_plots)
        options.addWidget(self._include_eval_summary)
        options.addStretch(1)
        options.addWidget(self._run_button)
        layout.addLayout(options)
        self._sync_format_options()
        return box

    def load_session(self, session: ProjectSession) -> None:
        """根据会话刷新页面。"""

        if not self._output_edit.text().strip():
            default_path = Path(session.export_dir) / "round8_export"
            self._output_edit.setText(str(default_path))

        state = session.export_state
        self._set_combo_value(self._scope_kind_combo, session.current_scope.scope_kind)
        if session.current_scope.subset_ids:
            self._scope_target_edit.setText(",".join(session.current_scope.subset_ids))
        elif session.current_scope.sample_uids:
            self._scope_target_edit.setText(",".join(session.current_scope.sample_uids))
        else:
            self._scope_target_edit.clear()
        message = state.last_message or "导出前先确认范围、类型与输出位置。"
        if state.last_output_path:
            message = f"{message}\n输出：{state.last_output_path}"
        if state.last_failure_message:
            message = f"{message}\n失败信息：{state.last_failure_message}"
        if state.missing_reason:
            message = f"{message}\n缺口说明：{state.missing_reason}"
        self._status.setText(message)

        missing_lines = "、".join(state.missing_requirements) if state.missing_requirements else "无"
        self._validation_label.setText(
            "\n".join(
                (
                    f"前置校验：{'通过' if state.validated else '未通过'}",
                    f"缺失项：{missing_lines}",
                    f"补算动作：{state.pending_generation_action or '-'}",
                    f"最近耗时：{state.last_duration_ms} ms",
                )
            )
        )
        self._result_label.setText(
            "\n".join(
                (
                    f"执行状态：{'正在执行…' if state.busy else '等待执行'}",
                    f"导出类型：{state.export_kind}",
                    f"目标路径：{state.output_path or self._output_edit.text().strip() or '-'}",
                )
            )
        )

        action_name = _required_action(
            export_kind=str(self._kind_combo.currentData()),
            data_var=self._data_var_edit.text().strip(),
            source=self._source_edit.text().strip(),
            available_slots=session.capability_snapshot.data_slots,
        )
        self._compute_button.setVisible(action_name is not None)
        if action_name is not None:
            self._compute_button.setProperty("action_name", action_name)
        self._run_button.setEnabled(session.primary_runtime is not None and not state.busy)

    def scope_selection(self) -> tuple[str, str]:
        """返回当前范围来源。"""

        return str(self._scope_kind_combo.currentData()), self._scope_target_edit.text().strip()

    def _set_combo_value(self, combo: QComboBox, value: str) -> None:
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)

    def _sync_format_options(self) -> None:
        export_kind = str(self._kind_combo.currentData())
        current_text = self._format_combo.currentText()
        options = ("png", "svg", "pdf") if export_kind == "current_plot_image" else ("xlsx", "csv")
        self._format_combo.blockSignals(True)
        self._format_combo.clear()
        self._format_combo.addItems(options)
        if current_text in options:
            self._format_combo.setCurrentText(current_text)
        self._format_combo.blockSignals(False)

    def _emit_export_request(self) -> None:
        self.export_requested.emit(
            str(self._kind_combo.currentData()),
            self._output_edit.text().strip(),
            self._format_combo.currentText(),
            _split_csv_text(self._metadata_fields_edit.text()),
            _split_csv_text(self._features_edit.text()),
            self._data_var_edit.text().strip(),
            self._source_edit.text().strip(),
            self._include_plots.isChecked(),
            self._include_eval_summary.isChecked(),
        )

    def _emit_compute_request(self) -> None:
        action_name = self._compute_button.property("action_name")
        if isinstance(action_name, str) and action_name:
            self.compute_required.emit(action_name)

    def export_request_values(self) -> tuple[str, str, str, tuple[str, ...], tuple[str, ...], str, str, bool, bool]:
        """返回当前导出动作参数。"""

        return (
            str(self._kind_combo.currentData()),
            self._output_edit.text().strip(),
            self._format_combo.currentText(),
            _split_csv_text(self._metadata_fields_edit.text()),
            _split_csv_text(self._features_edit.text()),
            self._data_var_edit.text().strip(),
            self._source_edit.text().strip(),
            self._include_plots.isChecked(),
            self._include_eval_summary.isChecked(),
        )

    def validation_request_values(self) -> tuple[str, str, str, str]:
        """返回当前导出校验参数。"""

        return (
            str(self._kind_combo.currentData()),
            self._output_edit.text().strip(),
            self._data_var_edit.text().strip(),
            self._source_edit.text().strip(),
        )


def _split_csv_text(text: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in text.split(",") if item.strip())


def _required_action(
    *,
    export_kind: str,
    data_var: str,
    source: str,
    available_slots: tuple[str, ...],
) -> str | None:
    if export_kind == "series_frame":
        return _map_data_requirement(data_var, available_slots)
    if export_kind == "peaks_frame":
        return _map_data_requirement(source, available_slots)
    return None


def _map_data_requirement(name: str, available_slots: tuple[str, ...]) -> str | None:
    if not name or name in available_slots:
        return None
    return {
        "freqspec": "calc_freqspec",
        "respspec": "calc_respspec",
        "zvl": "eval_zvl",
        "otovl": "eval_otovl",
        "fdmvl": "eval_fdmvl",
        "fpvdv": "eval_fpvdv",
    }.get(name)
