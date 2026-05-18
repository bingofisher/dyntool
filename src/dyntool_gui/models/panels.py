"""右侧信息区与底部表格模型。"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt

from ..session import MODULE_LABELS, ImportKind, ImportStep, ModuleKey, ProjectSession, describe_scope


@dataclass(slots=True)
class PanelSection:
    """信息区段落。"""

    key: str
    title: str
    lines: tuple[str, ...]


@dataclass(slots=True)
class InfoPanelSnapshot:
    """信息区快照。"""

    sections: tuple[PanelSection, ...]


@dataclass(slots=True)
class BottomPanelSnapshot:
    """底部多表快照。"""

    tasks: tuple[tuple[str, ...], ...]
    logs: tuple[tuple[str, ...], ...]
    issues: tuple[tuple[str, ...], ...]
    exports: tuple[tuple[str, ...], ...]
    reviews: tuple[tuple[str, ...], ...]


class PanelDataBuilder:
    """面板数据构造器。"""

    def build_info_snapshot(self, session: ProjectSession) -> InfoPanelSnapshot:
        """构造右侧信息区快照。"""

        return InfoPanelSnapshot(sections=tuple(self.build_info_sections(session)))

    def build_info_sections(self, session: ProjectSession) -> list[PanelSection]:
        """构造右侧信息区四卡。"""

        if session.current_module is ModuleKey.IMPORT:
            return self._build_import_sections(session)
        if session.current_module is ModuleKey.SUBSET:
            return self._build_subset_sections(session)
        if session.current_module is ModuleKey.PROCESSING:
            return self._build_processing_sections(session)
        if session.current_module is ModuleKey.PLOTTING:
            return self._build_plot_sections(session)
        if session.current_module is ModuleKey.EXPORT:
            return self._build_export_sections(session)
        return self._build_overview_sections(session)

    def build_bottom_snapshot(self, session: ProjectSession) -> BottomPanelSnapshot:
        """构造底部多表快照。"""

        rows = self.build_bottom_rows(session)
        return BottomPanelSnapshot(
            tasks=tuple(rows["任务队列"]),
            logs=tuple(rows["运行日志"]),
            issues=tuple(rows["问题列表"]),
            exports=tuple(rows["导出记录"]),
            reviews=tuple(rows["审查结论"]),
        )

    def build_bottom_rows(self, session: ProjectSession) -> dict[str, list[tuple[str, ...]]]:
        """构造底部表格数据。"""

        tasks = list(session.tasks)
        logs = list(session.logs)
        issues = list(session.issues)

        if session.current_module is ModuleKey.IMPORT:
            tasks = [
                item
                for item in session.tasks
                if any(keyword in item.title for keyword in ("导入", "预览", "深度检查", "主集", "项目"))
            ]
            logs = [item for item in session.logs if item.logger_name in {"gui.import", "gui.project", "gui.session"}]
            issues = [
                item
                for item in session.issues
                if any(keyword in item.title for keyword in ("导入", "预览", "深度检查", "项目"))
            ]
        elif session.current_module is ModuleKey.SUBSET:
            tasks = [
                item for item in session.tasks if any(keyword in item.title for keyword in ("子样本集", "筛选", "范围"))
            ]
            logs = [item for item in session.logs if item.logger_name in {"gui.subset", "gui.session"}]
            issues = [
                item
                for item in session.issues
                if "子样本集" in item.title or "筛选" in item.title or "范围" in item.title
            ]
        elif session.current_module is ModuleKey.PROCESSING:
            tasks = [
                item
                for item in session.tasks
                if any(
                    keyword in item.title for keyword in ("处理", "频谱", "响应谱", "ZVL", "OTOVL", "FDMVL", "FPVDV")
                )
            ]
            logs = [
                item for item in session.logs if item.logger_name in {"gui.processing", "gui.session", "gui.project"}
            ]
            issues = [item for item in session.issues if "处理" in item.title]
        elif session.current_module is ModuleKey.PLOTTING:
            tasks = [
                item for item in session.tasks if any(keyword in item.title for keyword in ("绘制", "图形", "图片"))
            ]
            logs = [item for item in session.logs if item.logger_name in {"gui.plot", "gui.session"}]
            issues = [item for item in session.issues if "绘图" in item.title or "图形" in item.title]
        elif session.current_module is ModuleKey.EXPORT:
            tasks = [item for item in session.tasks if "导出" in item.title or "交付" in item.title]
            logs = [item for item in session.logs if item.logger_name in {"gui.export", "gui.session"}]
            issues = [item for item in session.issues if "导出" in item.title or "交付" in item.title]

        return {
            "任务队列": [(item.title, item.status, item.progress_text, item.detail) for item in tasks],
            "运行日志": [(item.timestamp, item.level, item.logger_name, item.message) for item in logs],
            "问题列表": [(item.status, item.title, item.detail) for item in issues],
            "导出记录": [(item.timestamp, item.name, item.status, item.target) for item in session.exports],
            "审查结论": [(item.status, item.title, item.summary) for item in session.reviews],
        }

    def _build_overview_sections(self, session: ProjectSession) -> list[PanelSection]:
        sample_set = session.primary_sampleset
        categories = "、".join(sample_set.supported_categories) or "-"
        results = "、".join(session.capability_snapshot.eval_results) or "尚未生成"
        return [
            PanelSection(
                "overview_status",
                "当前状态",
                (
                    f"模块：{MODULE_LABELS[session.current_module]}",
                    f"项目：{session.project_name}",
                    f"当前主样本集：{sample_set.name}",
                    f"当前选中：{session.current_selection}",
                ),
            ),
            PanelSection(
                "overview_scope",
                "当前范围",
                (
                    f"范围说明：{describe_scope(session)}",
                    f"元数据模式：{sample_set.metadata_type}",
                    f"支持数据类型：{categories}",
                    f"已生成结果：{results}",
                ),
            ),
            PanelSection(
                "overview_gap",
                "当前缺口",
                (
                    "尚未接入真实主样本集" if session.primary_runtime is None else "主样本集已就绪",
                    "尚未生成分析结果" if not session.capability_snapshot.eval_results else "已生成部分分析结果",
                    f"最近导入：{session.recent_import_lines[0] if session.recent_import_lines else '无'}",
                ),
            ),
            PanelSection(
                "overview_next",
                "推荐下一步",
                (
                    "先接入主样本集" if session.primary_runtime is None else "继续分析当前主样本集",
                    "需要限定范围时：转到导入与筛选页中的子集工作区",
                    "需要出图或导出时：进入图形页或打开导出预检",
                ),
            ),
        ]

    def _build_import_sections(self, session: ProjectSession) -> list[PanelSection]:
        state = session.import_state
        source_path = str(state.source_path) if state.source_path is not None else "-"
        batch_count = len(state.sample_batch_paths)
        scheme_text = state.requested_scheme.value if state.requested_scheme is not None else "自动识别"
        step_text = {
            ImportStep.PROJECT_DIRECTORY: "先确认项目目录。",
            ImportStep.IMPORT_SOURCE: "继续设置接入来源。",
            ImportStep.PREVIEW: "先做轻量检查，再决定是否深度检查。",
            ImportStep.EXECUTE_IMPORT: "检查通过后可以绑定当前主样本集。",
        }[state.current_step]
        check_summary = state.preview_lines[0] if state.preview_lines else "执行预览后会生成检查摘要。"
        unit_summary = state.unit_lines[0] if state.unit_lines else "需要时可继续执行单位检查。"
        result_summary = state.last_success or state.last_error or "检查通过后可绑定当前主样本集。"
        return [
            PanelSection(
                "import_status",
                "当前状态",
                (
                    f"当前阶段：{state.phase_label or state.current_step.value}",
                    f"项目目录已选：{'是' if state.project_directory_selected else '否'}",
                    f"可绑定主样本集：{'是' if state.can_execute else '否'}",
                    f"后台忙碌：{'是' if state.busy else '否'}",
                    step_text,
                ),
            ),
            PanelSection(
                "import_scope",
                "当前范围",
                (
                    f"接入模式：{'批量样本 CSV' if state.import_kind is ImportKind.SAMPLE else '样本集仓库'}",
                    f"项目目录：{session.workdir}",
                    f"来源路径：{source_path}",
                    f"批量文件数：{batch_count}",
                    f"请求存储方式：{scheme_text}",
                    f"元数据模式：{state.metadata_mode_text or '-'}",
                ),
            ),
            PanelSection(
                "import_gap",
                "当前缺口",
                (
                    f"进度：{state.progress_text}",
                    f"检查摘要：{check_summary}",
                    f"单位检查：{unit_summary}",
                    f"绑定结果：{result_summary}",
                    f"缺口说明：{state.busy_detail or '按当前模式完成检查后即可绑定'}",
                    f"可检测数据分类：{'、'.join(state.available_series_categories) if state.available_series_categories else '无'}",
                ),
            ),
            PanelSection(
                "import_next",
                "推荐下一步",
                (
                    "先做轻量检查",
                    "需要精确单位时：深度检查单位",
                    "检查通过后：绑定为当前主样本集",
                ),
            ),
        ]

    def _build_subset_sections(self, session: ProjectSession) -> list[PanelSection]:
        state = session.subset_state
        return [
            PanelSection(
                "subset_status",
                "当前状态",
                (
                    f"模块：{MODULE_LABELS[session.current_module]}",
                    f"主样本集：{session.primary_sampleset.name}",
                    f"已保存子样本集：{len(state.subsets)}",
                    f"预览命中：{state.preview_count}",
                ),
            ),
            PanelSection(
                "subset_scope",
                "当前范围",
                (
                    f"范围类型：{session.current_scope.scope_kind}",
                    f"范围说明：{session.current_scope.note or describe_scope(session)}",
                    f"选中子样本集：{state.selected_subset_id or '-'}",
                    f"最近状态：{state.last_message or '设置条件后可预览命中'}",
                ),
            ),
            PanelSection(
                "subset_gap",
                "当前缺口",
                (state.last_failure_message or "可以继续预览、保存、重算或设为当前工作范围",),
            ),
            PanelSection(
                "subset_next",
                "推荐下一步",
                (
                    "先预览筛选命中",
                    "需要复用时：保存子样本集",
                    "范围确认后：去分析或图形页",
                ),
            ),
        ]

    def _build_processing_sections(self, session: ProjectSession) -> list[PanelSection]:
        state = session.processing_state
        capability = "、".join(session.capability_snapshot.data_slots) or "无"
        missing_lines: list[str] = []
        if not state.current_action:
            missing_lines.append("请选择分析动作后执行")
        if not any((state.scalar_rows, state.series_rows, state.peaks_rows)):
            missing_lines.append("生成预览表后可查看结果明细")
        if state.last_failure_message:
            missing_lines.append(state.last_failure_message)
        return [
            PanelSection(
                "processing_status",
                "当前状态",
                (
                    f"模块：{MODULE_LABELS[session.current_module]}",
                    f"主样本集：{session.primary_sampleset.name}",
                    f"可用数据：{capability}",
                    f"最近动作：{state.current_action or '-'}",
                    f"影响样本数：{state.last_action_count}",
                ),
            ),
            PanelSection(
                "processing_scope",
                "当前范围",
                (
                    f"范围说明：{describe_scope(session)}",
                    f"分析摘要：{state.last_message or '选择动作后即可开始分析'}",
                    f"预览标题：{state.preview_title or '生成预览表后在这里显示'}",
                    f"预览类型：{state.preview_kind or '-'}",
                    f"预览范围：{'当前 UID 子集' if state.preview_scope == 'subset' else '全部已生成结果'}",
                    f"预览行上限：{state.preview_row_limit}",
                    f"最近耗时：{state.last_duration_ms} ms",
                ),
            ),
            PanelSection(
                "processing_gap",
                "当前缺口",
                tuple(missing_lines) or ("当前分析页无缺口",),
            ),
            PanelSection(
                "processing_next",
                "推荐下一步",
                (
                    "需要细看结果时：生成预览表",
                    "已有可用结果时：转到图形页",
                    "准备形成交付物时：打开导出预检或导出工作区",
                ),
            ),
        ]

    def _build_plot_sections(self, session: ProjectSession) -> list[PanelSection]:
        state = session.plot_state
        missing_lines: list[str] = []
        if state.missing_reason:
            missing_lines.append(state.missing_reason)
        if state.last_failure_message:
            missing_lines.append(state.last_failure_message)
        if not missing_lines:
            missing_lines.append("当前图形页无缺口")
        return [
            PanelSection(
                "plot_status",
                "当前状态",
                (
                    f"模块：{MODULE_LABELS[session.current_module]}",
                    f"渲染完成：{'是' if state.render_complete else '否'}",
                    f"来源类型：{state.source_kind}",
                    f"来源名称：{state.source_name}",
                    f"目标样本：{state.selected_uid or '首个样本'}",
                ),
            ),
            PanelSection(
                "plot_scope",
                "当前范围",
                (
                    f"范围说明：{describe_scope(session)}",
                    f"最近状态：{state.last_message or '尚未渲染图形'}",
                    f"点数上限：{state.point_limit}",
                    f"保存模式：{state.save_mode}",
                    f"保存路径：{state.last_saved_path or '-'}",
                    f"最近耗时：{state.last_duration_ms} ms",
                ),
            ),
            PanelSection("plot_gap", "当前缺口", tuple(missing_lines)),
            PanelSection(
                "plot_next",
                "推荐下一步",
                (
                    "缺少结果时：计算所需结果",
                    "图形满意后：保存图片",
                    "需要正式输出时：打开导出预检或导出工作区",
                ),
            ),
        ]

    def _build_export_sections(self, session: ProjectSession) -> list[PanelSection]:
        state = session.export_state
        missing_lines = state.missing_requirements or (state.last_failure_message or "当前导出链路无缺口",)
        return [
            PanelSection(
                "export_status",
                "当前状态",
                (
                    f"模块：{MODULE_LABELS[session.current_module]}",
                    f"主样本集：{session.primary_sampleset.name}",
                    f"默认导出目录：{session.export_dir}",
                    f"导出类型：{state.export_kind}",
                    f"校验通过：{'是' if state.validated else '否'}",
                ),
            ),
            PanelSection(
                "export_scope",
                "当前范围",
                (
                    f"范围说明：{describe_scope(session)}",
                    f"目标路径：{state.output_path or '-'}",
                    f"最近结果：{state.last_message or '确认参数后可执行导出'}",
                    f"补算动作：{state.pending_generation_action or '-'}",
                    f"最近耗时：{state.last_duration_ms} ms",
                ),
            ),
            PanelSection(
                "export_gap",
                "当前缺口",
                (
                    f"输出路径：{state.last_output_path or '-'}",
                    *tuple(missing_lines[:3]),
                ),
            ),
            PanelSection(
                "export_next",
                "推荐下一步",
                (
                    "缺少前置时：计算所需结果",
                    "校验通过后：执行导出",
                    "导出完成后：回到总览查看记录",
                ),
            ),
        ]


class _BaseTableModel(QAbstractTableModel):
    """底部区域通用表模型。"""

    def __init__(self, headers: tuple[str, ...], parent: object | None = None) -> None:
        super().__init__(parent)
        self._headers = headers
        self._rows: list[tuple[str, ...]] = []

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        if parent.isValid():
            return 0
        return len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        if parent.isValid():
            return 0
        return len(self._headers)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> str | None:  # noqa: N802
        if not index.isValid():
            return None
        if role == Qt.ItemDataRole.DisplayRole:
            return self._rows[index.row()][index.column()]
        return None

    def headerData(  # noqa: N802
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> str | None:
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            return self._headers[section]
        return str(section + 1)

    def set_rows(self, rows: tuple[tuple[str, ...], ...]) -> None:
        """批量更新表格行。"""

        if len(rows) != len(self._rows):
            self.beginResetModel()
            self._rows = list(rows)
            self.endResetModel()
            return
        changed_rows = [index for index, row in enumerate(rows) if row != self._rows[index]]
        if not changed_rows:
            return
        self._rows = list(rows)
        start = changed_rows[0]
        end = changed_rows[0]
        for row_index in changed_rows[1:]:
            if row_index == end + 1:
                end = row_index
                continue
            self.dataChanged.emit(self.index(start, 0), self.index(end, len(self._headers) - 1))
            start = row_index
            end = row_index
        self.dataChanged.emit(self.index(start, 0), self.index(end, len(self._headers) - 1))


class TaskTableModel(_BaseTableModel):
    """任务表模型。"""

    def __init__(self, parent: object | None = None) -> None:
        super().__init__(("任务", "状态", "进度", "说明"), parent)


class LogTableModel(_BaseTableModel):
    """日志表模型。"""

    def __init__(self, parent: object | None = None) -> None:
        super().__init__(("时间", "级别", "来源", "消息"), parent)


class IssueTableModel(_BaseTableModel):
    """问题表模型。"""

    def __init__(self, parent: object | None = None) -> None:
        super().__init__(("状态", "主题", "说明"), parent)


class ExportTableModel(_BaseTableModel):
    """导出记录表模型。"""

    def __init__(self, parent: object | None = None) -> None:
        super().__init__(("时间", "名称", "状态", "目标"), parent)


class ReviewTableModel(_BaseTableModel):
    """审查表模型。"""

    def __init__(self, parent: object | None = None) -> None:
        super().__init__(("状态", "标题", "摘要"), parent)
