"""GUI 项目会话与导入状态。"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from dyntool_gui._session_types import (
    CapabilitySnapshot,
    ExportState,
    FilterSpec,
    ImportKind,
    ImportPreviewLike,
    ImportResultLike,
    ImportState,
    ImportStep,
    IssueRecord,
    LogRecord,
    MetadataFilterClause,
    MetadataHookSpec,
    ModuleKey,
    MODULE_LABELS,
    PlotNode,
    PlotRecord,
    PlotState,
    ProcessingActionSpec,
    ProcessingParameterSpec,
    ProcessingPreviewRequestSnapshot,
    ProcessingRequestSnapshot,
    ProcessingState,
    ReviewRecord,
    SampleSetSummary,
    ScopeSelection,
    SubsetDefinition,
    SubsetState,
    TaskRecord,
    ExportRecord,
    build_capability_snapshot,
    build_capability_snapshot_from_summary,
    build_metadata_hook_specs,
    build_metadata_preview_columns,
    build_metadata_preview_row,
    describe_filter_spec,
    metadata_sort_value,
    now_text,
    sample_matches_filter,
    slugify_subset_name,
    summarize_runtime_sample_set,
)
from dyntool_gui.session_bus import SessionBus

if TYPE_CHECKING:
    from dyntool import DefaultSampleSet


class ProjectSession:
    """项目 GUI 会话。

    纯数据容器，所有状态变更信号通过 ``bus`` 广播。
    """

    def __init__(
        self,
        project_name: str,
        workdir: Path,
        export_dir: Path,
        note: str,
        last_saved: str,
        primary_sampleset: SampleSetSummary,
        compare_sampleset: SampleSetSummary | None,
        other_samplesets: tuple[SampleSetSummary, ...],
        *,
        bus: SessionBus | None = None,
        tasks: list[TaskRecord] | None = None,
        logs: list[LogRecord] | None = None,
        issues: list[IssueRecord] | None = None,
        exports: list[ExportRecord] | None = None,
        reviews: list[ReviewRecord] | None = None,
        plot_tree: tuple[PlotNode, ...] = (),
        plot_records: list[PlotRecord] | None = None,
        current_module: ModuleKey = ModuleKey.PROJECT,
        current_selection: str = "当前项目",
        dirty: bool = False,
        demo_key: str = "",
        recent_import_lines: tuple[str, ...] = (),
        import_state: ImportState | None = None,
        subset_state: SubsetState | None = None,
        current_scope: ScopeSelection | None = None,
        processing_state: ProcessingState | None = None,
        plot_state: PlotState | None = None,
        export_state: ExportState | None = None,
        capability_snapshot: CapabilitySnapshot | None = None,
        primary_runtime: "DefaultSampleSet | None" = None,
    ) -> None:
        self.bus = bus or SessionBus()
        self.project_changed = self.bus.project_changed
        self.primary_changed = self.bus.primary_changed
        self.import_state_changed = self.bus.import_state_changed
        self.subset_state_changed = self.bus.subset_state_changed
        self.processing_state_changed = self.bus.processing_state_changed
        self.plot_state_changed = self.bus.plot_state_changed
        self.export_state_changed = self.bus.export_state_changed
        self.resource_tree_changed = self.bus.resource_tree_changed
        self.selection_changed = self.bus.selection_changed
        self.task_changed = self.bus.task_changed
        self.logs_changed = self.bus.logs_changed
        self.issues_changed = self.bus.issues_changed
        self.project_name = project_name
        self.workdir = Path(workdir).resolve()
        self.export_dir = Path(export_dir).resolve()
        self.note = note
        self.last_saved = last_saved
        self.primary_sampleset = primary_sampleset
        self.compare_sampleset = compare_sampleset
        self.other_samplesets = other_samplesets
        self.tasks = list(tasks or [])
        self.logs = list(logs or [])
        self.issues = list(issues or [])
        self.exports = list(exports or [])
        self.reviews = list(reviews or [])
        self.plot_tree = plot_tree
        self.plot_records = list(plot_records or [])
        if not self.plot_tree and self.plot_records:
            self._sync_plot_tree_from_records()
        self.current_module = current_module
        self.current_selection = current_selection
        self.dirty = dirty
        self.demo_key = demo_key
        self.recent_import_lines = recent_import_lines
        self.import_state = import_state or ImportState()
        self.subset_state = subset_state or SubsetState()
        self.current_scope = current_scope or ScopeSelection()
        self.processing_state = processing_state or ProcessingState()
        self.plot_state = plot_state or PlotState()
        self.export_state = export_state or ExportState()
        self.capability_snapshot = (
            capability_snapshot
            if capability_snapshot is not None
            else build_capability_snapshot_from_summary(primary_sampleset)
        )
        self.primary_runtime = primary_runtime
        self.real_data_diagnostics: tuple[str, ...] = ()
        self._repair_loaded_import_context()
        self._refresh_subset_hook_specs()

    @classmethod
    def build_empty(cls, *, bus: SessionBus | None = None) -> "ProjectSession":
        """构造默认空项目会话。"""

        root = Path.cwd()
        now = ""
        return cls(
            project_name="未命名 GUI 项目",
            workdir=root,
            export_dir=root / "exports",
            note="当前未加载主样本集，请先选择项目目录并导入数据。",
            last_saved=now,
            primary_sampleset=SampleSetSummary(
                name="主样本集 / 未加载",
                class_name="DefaultSampleSet",
                sample_type="-",
                sample_domain="-",
                metadata_type="-",
                metadata_fields=(),
                supported_categories=(),
                storable_categories=(),
                supported_fields=(),
                sample_count=0,
                loaded_count=0,
                unloaded_count=0,
                storage_binding="未绑定",
                strict=True,
                storage_dirty=False,
            ),
            compare_sampleset=None,
            other_samplesets=(),
            bus=bus,
            tasks=[TaskRecord("新建空项目", "已完成", "1 / 1", "已创建空项目会话，等待导入主样本集。")],
            logs=[LogRecord("INFO", "gui.session", "已创建空项目会话。", now_text())],
            issues=[IssueRecord("待执行", "导入主样本集", "请先选择项目目录并导入数据。")],
            exports=[],
            reviews=[],
            plot_tree=(),
            plot_records=[],
            current_module=ModuleKey.PROJECT,
            current_selection="当前项目",
            dirty=False,
            demo_key="",
            recent_import_lines=("最近导入：无",),
            subset_state=SubsetState(last_message="当前没有可用子样本集，请先导入主样本集。"),
            current_scope=ScopeSelection(scope_kind="all_samples", note="当前未加载主样本集。"),
        )

    @classmethod
    def build_demo(cls, demo_key: str = "bridge", *, bus: SessionBus | None = None) -> "ProjectSession":
        """构造演示会话（委托到 _session_demo）。"""

        from dyntool_gui._session_demo import build_demo as _build_demo

        return _build_demo(cls, demo_key, bus=bus)

    def switch_demo(self, demo_key: str) -> None:
        """切换演示数据。"""

        replacement = self.build_demo(demo_key, bus=self.bus)
        for attr in (
            "project_name",
            "workdir",
            "export_dir",
            "note",
            "last_saved",
            "primary_sampleset",
            "compare_sampleset",
            "other_samplesets",
            "tasks",
            "logs",
            "issues",
            "exports",
            "reviews",
            "plot_tree",
            "plot_records",
            "current_module",
            "current_selection",
            "dirty",
            "demo_key",
            "recent_import_lines",
            "import_state",
            "subset_state",
            "current_scope",
            "processing_state",
            "plot_state",
            "export_state",
            "capability_snapshot",
            "primary_runtime",
        ):
            setattr(self, attr, getattr(replacement, attr))
        self._refresh_subset_hook_specs()
        self.bus.emit_all()

    def set_current_module(self, module: ModuleKey) -> None:
        """切换当前模块。"""

        if module is ModuleKey.SUBSET:
            module = ModuleKey.IMPORT
        elif module is ModuleKey.EXPORT:
            module = ModuleKey.PLOTTING
        self.current_module = module
        self.bus.project_changed.emit()
        self.bus.selection_changed.emit()

    def set_current_selection(self, selection: str) -> None:
        """更新当前选中对象。"""

        self.current_selection = selection
        self.bus.selection_changed.emit()

    def set_current_scope(
        self,
        scope_kind: str,
        *,
        subset_ids: tuple[str, ...] = (),
        sample_uids: tuple[str, ...] = (),
        note: str = "",
    ) -> None:
        """更新当前工作范围。"""

        self.current_scope = ScopeSelection(
            scope_kind=scope_kind,
            subset_ids=tuple(item for item in subset_ids if item),
            sample_uids=tuple(item for item in sample_uids if item),
            note=note,
        )
        self._upsert_task("切换当前范围", "已完成", "1 / 1", note or scope_kind)
        self._prepend_log("INFO", "gui.subset", f"当前范围已切换为：{note or scope_kind}")
        self.bus.selection_changed.emit()
        self.bus.processing_state_changed.emit()
        self.bus.plot_state_changed.emit()
        self.bus.export_state_changed.emit()
        self.bus.task_changed.emit()
        self.bus.logs_changed.emit()

    def preview_subset(self, filter_spec: FilterSpec) -> tuple[tuple[str, ...], ...]:
        """预览当前筛选条件命中的样本。"""

        self._refresh_subset_hook_specs()
        rows = self._build_subset_preview_rows(filter_spec)
        self.subset_state.filter_spec = filter_spec
        self.subset_state.preview_rows = rows
        self.subset_state.preview_columns = build_metadata_preview_columns(self.primary_sampleset)
        self.subset_state.preview_count = len(rows)
        self.subset_state.current_condition_summary = describe_filter_spec(filter_spec)
        self.subset_state.last_message = f"已命中 {len(rows)} 个样本。"
        self.subset_state.last_failure_message = ""
        self._upsert_task("筛选预览", "已完成", "1 / 1", self.subset_state.last_message)
        self._prepend_log("INFO", "gui.subset", self.subset_state.last_message)
        self.bus.subset_state_changed.emit()
        self.bus.task_changed.emit()
        self.bus.logs_changed.emit()
        return rows

    def save_subset_definition(
        self,
        *,
        name: str,
        note: str = "",
        freeze: bool = False,
        subset_id: str = "",
    ) -> SubsetDefinition:
        """保存或更新子样本集定义。"""

        rows = self.subset_state.preview_rows or self._build_subset_preview_rows(self.subset_state.filter_spec)
        resolved_uids = tuple(row[0] for row in rows)
        now = now_text()
        target_id = subset_id or slugify_subset_name(name)
        definition = SubsetDefinition(
            id=target_id,
            name=name,
            filter_spec=self.subset_state.filter_spec,
            resolved_uids=resolved_uids,
            sample_count=len(resolved_uids),
            created_at=self._existing_subset_created_at(target_id, default=now),
            updated_at=now,
            note=note,
            mode="frozen" if freeze else "dynamic",
            frozen=freeze,
        )
        subsets = [item for item in self.subset_state.subsets if item.id != target_id]
        subsets.insert(0, definition)
        self.subset_state.subsets = tuple(subsets)
        self.subset_state.selected_subset_id = definition.id
        self.subset_state.last_message = f"已保存子样本集：{definition.name}"
        self._upsert_task("保存子样本集", "已完成", "1 / 1", self.subset_state.last_message)
        self._prepend_log("INFO", "gui.subset", self.subset_state.last_message)
        self.bus.subset_state_changed.emit()
        self.bus.resource_tree_changed.emit()
        self.bus.task_changed.emit()
        self.bus.logs_changed.emit()
        return definition

    def delete_subset_definition(self, subset_id: str) -> None:
        """删除子样本集定义。"""

        removed = next((item for item in self.subset_state.subsets if item.id == subset_id), None)
        self.subset_state.subsets = tuple(item for item in self.subset_state.subsets if item.id != subset_id)
        if self.subset_state.selected_subset_id == subset_id:
            self.subset_state.selected_subset_id = ""
        if (
            self.current_scope.scope_kind in {"saved_subset", "multi_subset_union"}
            and subset_id in self.current_scope.subset_ids
        ):
            self.set_current_scope("all_samples", note="已回退到全部样本")
        message = f"已删除子样本集：{removed.name}" if removed is not None else "子样本集已删除。"
        self.subset_state.last_message = message
        self._upsert_task("删除子样本集", "已完成", "1 / 1", message)
        self._prepend_log("INFO", "gui.subset", message)
        self.bus.subset_state_changed.emit()
        self.bus.resource_tree_changed.emit()
        self.bus.task_changed.emit()
        self.bus.logs_changed.emit()

    def recalculate_subset_definition(self, subset_id: str) -> SubsetDefinition:
        """按当前主样本集重算子样本集快照。"""

        definition = next((item for item in self.subset_state.subsets if item.id == subset_id), None)
        if definition is None:
            raise ValueError("未找到指定子样本集。")
        if definition.mode == "frozen":
            raise ValueError("冻结快照不能重算，请保存新的动态子集。")
        rows = self._build_subset_preview_rows(definition.filter_spec)
        updated = SubsetDefinition(
            id=definition.id,
            name=definition.name,
            filter_spec=definition.filter_spec,
            resolved_uids=tuple(row[0] for row in rows),
            sample_count=len(rows),
            created_at=definition.created_at,
            updated_at=now_text(),
            note=definition.note,
            mode=definition.mode,
            frozen=definition.frozen,
        )
        subsets = [updated if item.id == subset_id else item for item in self.subset_state.subsets]
        self.subset_state.subsets = tuple(subsets)
        self.subset_state.selected_subset_id = subset_id
        self.subset_state.preview_rows = rows
        self.subset_state.preview_count = len(rows)
        self.subset_state.last_message = f"已重算子样本集：{updated.name}"
        self._upsert_task("重算子样本集", "已完成", "1 / 1", self.subset_state.last_message)
        self._prepend_log("INFO", "gui.subset", self.subset_state.last_message)
        self.bus.subset_state_changed.emit()
        self.bus.resource_tree_changed.emit()
        self.bus.task_changed.emit()
        self.bus.logs_changed.emit()
        return updated

    def select_subset_definition(self, subset_id: str) -> None:
        """选中子样本集定义。"""

        self.subset_state.selected_subset_id = subset_id
        definition = next((item for item in self.subset_state.subsets if item.id == subset_id), None)
        if definition is not None:
            self.current_selection = definition.name
            self.subset_state.preview_columns = build_metadata_preview_columns(self.primary_sampleset)
            self.subset_state.current_condition_summary = describe_filter_spec(definition.filter_spec)
            self.subset_state.preview_rows = self._build_rows_for_uids(definition.resolved_uids[:200])
            self.subset_state.preview_count = definition.sample_count
        self.bus.subset_state_changed.emit()
        self.bus.selection_changed.emit()

    def bind_primary_runtime(
        self,
        sample_set: "DefaultSampleSet",
        *,
        name: str | None = None,
        storage_binding: str | None = None,
        recent_lines: tuple[str, ...] | None = None,
    ) -> None:
        """绑定真实主样本集并同步刷新摘要与能力快照。"""

        self.primary_runtime = sample_set
        self.primary_sampleset = summarize_runtime_sample_set(
            sample_set,
            name=name or self.primary_sampleset.name,
            storage_binding=storage_binding or self.primary_sampleset.storage_binding,
        )
        self.capability_snapshot = build_capability_snapshot(sample_set)
        if recent_lines is not None:
            self.recent_import_lines = recent_lines
        self.current_scope = ScopeSelection(scope_kind="all_samples")
        self.current_selection = self.primary_sampleset.name
        self._refresh_subset_hook_specs()
        self.bus.primary_changed.emit()
        self.bus.project_changed.emit()
        self.bus.subset_state_changed.emit()
        self.bus.resource_tree_changed.emit()
        self.bus.selection_changed.emit()

    def set_processing_preview(
        self,
        *,
        action_name: str,
        message: str,
        scalar_rows: tuple[tuple[str, ...], ...] = (),
        series_rows: tuple[tuple[str, ...], ...] = (),
        peaks_rows: tuple[tuple[str, ...], ...] = (),
    ) -> None:
        """更新处理页预览状态。"""

        self.processing_state.current_action = action_name
        self.processing_state.last_message = message
        self.processing_state.preview_title = action_name
        self.processing_state.scalar_rows = scalar_rows
        self.processing_state.series_rows = series_rows
        self.processing_state.peaks_rows = peaks_rows
        self.bus.processing_state_changed.emit()

    def _repair_loaded_import_context(self) -> None:
        """修复旧项目文件缺失的运行态恢复线索。"""

        if not self.capability_snapshot.data_slots and self.import_state.available_series_categories:
            self.capability_snapshot = build_capability_snapshot_from_summary(
                SampleSetSummary(
                    name=self.primary_sampleset.name,
                    class_name=self.primary_sampleset.class_name,
                    sample_type=self.primary_sampleset.sample_type,
                    sample_domain=self.primary_sampleset.sample_domain,
                    metadata_type=self.primary_sampleset.metadata_type,
                    metadata_fields=self.primary_sampleset.metadata_fields,
                    supported_categories=tuple(self.import_state.available_series_categories),
                    storable_categories=tuple(self.import_state.available_series_categories),
                    supported_fields=self.primary_sampleset.supported_fields,
                    sample_count=self.primary_sampleset.sample_count,
                    loaded_count=self.primary_sampleset.loaded_count,
                    unloaded_count=self.primary_sampleset.unloaded_count,
                    storage_binding=self.primary_sampleset.storage_binding,
                    strict=self.primary_sampleset.strict,
                    storage_dirty=self.primary_sampleset.storage_dirty,
                )
            )
        if self.primary_runtime is not None or self.import_state.source_path is not None:
            return
        if self.primary_sampleset.sample_count <= 0 or self.import_state.import_kind is not ImportKind.SAMPLE_SET:
            return
        for candidate in self._primary_source_candidates():
            if candidate.exists():
                self.import_state.source_path = candidate
                self.import_state.project_directory_selected = True
                self._refresh_import_step(preview_ready=bool(self.import_state.preview_lines))
                return

    def _primary_source_candidates(self) -> tuple[Path, ...]:
        """返回旧项目可推断的主集来源候选路径。"""

        names: list[str] = []
        if "/" in self.primary_sampleset.name:
            names.append(self.primary_sampleset.name.rsplit("/", maxsplit=1)[-1].strip())
        names.extend(("data", "主样本集", "sampleset"))
        candidates: list[Path] = []
        for name in names:
            if not name:
                continue
            path = (self.workdir / name).resolve()
            if path not in candidates:
                candidates.append(path)
        return tuple(candidates)

    def _refresh_subset_hook_specs(self) -> None:
        """刷新 subset 页 metadata hook 快照。"""

        # 不在会话刷新路径扫描 runtime。大型仓库常使用按需加载，遍历 items()
        # 会把导入写回阶段卡在 GUI 线程；候选值后续由预览链路按需补齐。
        self.subset_state.metadata_hook_specs = build_metadata_hook_specs(self.primary_sampleset, None)
        self.subset_state.preview_columns = build_metadata_preview_columns(self.primary_sampleset)

    def set_plot_message(self, *, message: str, saved_path: str = "", missing_reason: str = "") -> None:
        """更新绘图页状态。"""

        self.plot_state.last_message = message
        self.plot_state.last_saved_path = saved_path
        self.plot_state.missing_reason = missing_reason
        self.bus.plot_state_changed.emit()

    def add_plot_record(
        self,
        *,
        title: str,
        plot_mode: str,
        source_name: str,
        sample_count: int,
        saved_path: str = "",
    ) -> PlotRecord:
        """追加图形记录并同步资源树。"""

        record = PlotRecord(
            id=f"plot.record.{len(self.plot_records) + 1}",
            title=title,
            plot_mode=plot_mode,
            source_name=source_name,
            sample_count=sample_count,
            saved_path=saved_path,
            created_at=now_text(),
        )
        self.plot_records.insert(0, record)
        self._sync_plot_tree_from_records()
        self.bus.resource_tree_changed.emit()
        self.bus.project_changed.emit()
        return record

    def update_latest_plot_record_saved_path(self, saved_path: str) -> None:
        """更新最新图形记录的保存路径。"""

        if not self.plot_records:
            return
        self.plot_records[0].saved_path = saved_path
        self._sync_plot_tree_from_records()
        self.bus.resource_tree_changed.emit()
        self.bus.project_changed.emit()

    def set_export_message(self, *, message: str, output_path: str = "", missing_reason: str = "") -> None:
        """更新导出页状态。"""

        self.export_state.last_message = message
        self.export_state.last_output_path = output_path
        self.export_state.missing_reason = missing_reason
        self.bus.export_state_changed.emit()

    def toggle_dirty(self) -> None:
        """切换脏状态。"""

        self.dirty = not self.dirty
        self.bus.project_changed.emit()

    def mark_saved(self, timestamp: str | None = None) -> None:
        """更新保存状态。"""

        self.last_saved = timestamp or now_text()
        self.dirty = False
        self.bus.project_changed.emit()

    def set_project_directory(self, path: str | Path) -> None:
        """选择项目目录并初始化导入上下文。"""

        project_dir = Path(path).resolve()
        self.project_name = f"{project_dir.name} 项目"
        self.workdir = project_dir
        self.export_dir = project_dir / "exports"
        self.demo_key = ""
        self.current_selection = "项目目录"
        self.note = "当前项目已切换到真实项目目录，可以执行导入。"
        self.import_state.project_directory_selected = True
        self._refresh_import_step()
        self._prepend_log("INFO", "gui.project", f"已选择项目目录：{project_dir}")
        self.bus.emit_project_related()
        self.bus.logs_changed.emit()

    def get_import_start_directory(self, import_kind: ImportKind) -> Path:
        """返回导入对话框的默认起点。"""

        if import_kind is ImportKind.SAMPLE and self.import_state.recent_sample_source_dir is not None:
            return self.import_state.recent_sample_source_dir
        if import_kind is ImportKind.SAMPLE_SET and self.import_state.recent_sampleset_source_dir is not None:
            return self.import_state.recent_sampleset_source_dir
        return self.workdir

    def reset_for_import(self, import_kind: ImportKind) -> None:
        """重置导入流程。"""

        state = self.import_state
        requested_scheme = state.requested_scheme if state.import_kind is import_kind else None
        self.import_state = ImportState(
            import_kind=import_kind,
            project_directory_selected=state.project_directory_selected and not self.demo_key,
            requested_scheme=requested_scheme,
            load_mode=state.load_mode,
            workers=state.workers,
            strict=state.strict,
            recent_sample_source_dir=state.recent_sample_source_dir,
            recent_sampleset_source_dir=state.recent_sampleset_source_dir,
        )
        self.current_module = ModuleKey.IMPORT
        self.current_selection = "导入工作流"
        self._refresh_import_step()
        self.bus.import_state_changed.emit()
        self.bus.selection_changed.emit()
        self.bus.project_changed.emit()

    def set_import_source(self, path: str | Path | None) -> None:
        """设置当前导入源。"""

        resolved = Path(path).resolve() if path else None
        self.import_state.source_path = resolved
        self.import_state.sample_batch_paths = ()
        self._remember_import_source_dir(resolved)
        self._clear_import_preview_state()
        self._refresh_import_step()
        self.bus.import_state_changed.emit()
        self.bus.resource_tree_changed.emit()

    def set_import_sources(self, paths: list[str | Path] | tuple[str | Path, ...]) -> None:
        """设置当前批量导入源。"""

        resolved_paths = tuple(Path(path).resolve() for path in paths)
        self.import_state.sample_batch_paths = resolved_paths
        self.import_state.source_path = None
        if resolved_paths:
            self._remember_import_source_dir(resolved_paths[0].parent)
        self._clear_import_preview_state()
        self._refresh_import_step()
        self.bus.import_state_changed.emit()
        self.bus.resource_tree_changed.emit()

    def begin_import_activity(
        self,
        title: str,
        detail: str,
        *,
        operation_id: str,
        phase_code: str = "",
        phase_label: str = "",
        progress_prefix: str = "",
        cancellable: bool = True,
    ) -> None:
        """标记导入相关后台活动开始。"""

        state = self.import_state
        state.busy = True
        state.active_task_title = title
        state.busy_title = phase_label or title
        state.busy_detail = detail
        state.operation_id = operation_id
        state.phase_code = phase_code
        state.phase_label = phase_label or title
        state.progress_prefix = progress_prefix or phase_label or title
        state.progress_current = None
        state.progress_total = None
        state.progress_percent = None
        state.cancellable = cancellable
        state.cancel_requested = False
        state.rollback_pending = True
        state.rollback_primary_summary = self.primary_sampleset
        state.last_cleanup_status = ""
        self._upsert_task(title, "进行中", state.progress_text, detail)
        self._prepend_log("INFO", "gui.import", f"{title}：{detail}")
        self.bus.import_state_changed.emit()
        self.bus.task_changed.emit()
        self.bus.logs_changed.emit()

    def update_import_progress(
        self,
        *,
        operation_id: str,
        phase_code: str,
        phase_label: str,
        progress_prefix: str,
        detail: str = "",
        current: int | None = None,
        total: int | None = None,
    ) -> None:
        """刷新导入阶段进度。"""

        state = self.import_state
        if state.operation_id and state.operation_id != operation_id:
            return
        state.busy = True
        state.phase_code = phase_code
        state.phase_label = phase_label
        state.busy_title = phase_label
        state.busy_detail = detail or progress_prefix
        state.progress_prefix = progress_prefix
        state.progress_current = current
        state.progress_total = total
        if current is not None and total not in {None, 0}:
            state.progress_percent = int(current * 100 / total)
        else:
            state.progress_percent = None
        title = state.active_task_title or phase_label
        status = "正在中止" if state.cancel_requested else "进行中"
        self._upsert_task(title, status, state.progress_text, state.busy_detail)
        self.bus.import_state_changed.emit()
        self.bus.task_changed.emit()

    def begin_import_finalization(
        self,
        title: str,
        detail: str = "导入数据已完成，正在刷新主集摘要，暂不可中止。",
    ) -> None:
        """标记导入进入 GUI 收尾刷新阶段。"""

        state = self.import_state
        state.busy = True
        state.active_task_title = title
        state.busy_title = "刷新主集摘要"
        state.busy_detail = detail
        state.phase_code = "finalize_import"
        state.phase_label = "刷新主集摘要"
        state.progress_prefix = "刷新主集摘要"
        state.progress_current = None
        state.progress_total = None
        state.progress_percent = None
        state.cancellable = False
        state.cancel_requested = False
        self._upsert_task(title, "刷新界面", state.progress_text, detail)
        self.bus.import_state_changed.emit()
        self.bus.task_changed.emit()

    def mark_import_cancel_requested(self, cleanup_hint: str = "已请求中止，正在等待安全检查点。") -> None:
        """标记当前导入任务已请求中止。"""

        state = self.import_state
        if not state.busy:
            return
        state.cancel_requested = True
        state.busy_detail = cleanup_hint
        title = state.active_task_title or "导入任务"
        self._upsert_task(title, "正在中止", state.progress_text, cleanup_hint)
        self._prepend_log("WARNING", "gui.import", cleanup_hint)
        self.bus.import_state_changed.emit()
        self.bus.task_changed.emit()
        self.bus.logs_changed.emit()

    def apply_import_preview(self, preview: "ImportPreviewLike") -> None:
        """写入导入预览。"""

        state = self.import_state
        state.source_path = preview.source_path
        state.preview_lines = preview.preview_lines
        state.unit_lines = preview.unit_lines
        state.parameter_lines = preview.parameter_lines
        state.timing_lines = preview.timing_lines
        state.available_series_categories = preview.available_series_categories
        state.metadata_mode_text = preview.metadata_mode_text
        state.detected_scheme = preview.detected_scheme
        state.last_error = ""
        state.last_success = ""
        state.can_execute = preview.allow_execute
        self.finish_import_activity()
        self._refresh_import_step(preview_ready=preview.allow_execute)
        task_title = "预览样本" if state.import_kind is ImportKind.SAMPLE else "预览样本集"
        self._upsert_task(task_title, "已完成", "1 / 1", "已完成预览与检查。")
        self._append_timing_logs(preview.timing_lines)
        self._prepend_log("INFO", "gui.import", f"已生成导入预览：{preview.source_path}")
        self.bus.import_state_changed.emit()
        self.bus.task_changed.emit()
        self.bus.logs_changed.emit()

    def apply_import_result(self, result: "ImportResultLike") -> None:
        """应用导入结果。"""

        runtime = getattr(result, "primary_runtime", None)
        if runtime is not None:
            self.primary_runtime = runtime
        capability_snapshot = getattr(result, "capability_snapshot", None)
        self.capability_snapshot = (
            capability_snapshot
            if isinstance(capability_snapshot, CapabilitySnapshot)
            else build_capability_snapshot_from_summary(result.primary_summary)
        )
        self.primary_sampleset = result.primary_summary
        self.recent_import_lines = result.recent_lines
        self.current_selection = self.primary_sampleset.name
        state = self.import_state
        state.last_success = result.success_message
        state.last_error = ""
        state.preview_lines = result.preview_lines
        if result.unit_lines:
            state.unit_lines = result.unit_lines
        state.parameter_lines = result.parameter_lines
        state.timing_lines = result.timing_lines
        state.detected_scheme = result.detected_scheme
        state.last_cleanup_status = result.cleanup_message
        state.can_execute = True
        self.finish_import_activity()
        state.current_step = ImportStep.EXECUTE_IMPORT
        self._clear_import_issues()
        self._upsert_task(result.task_title, "已完成", "1 / 1", result.success_message)
        self._append_timing_logs(result.timing_lines)
        if result.cleanup_message:
            self._prepend_log("INFO", "gui.import", result.cleanup_message)
        self._prepend_log("INFO", "gui.import", f"导入完成：{result.success_message}")
        self._refresh_subset_hook_specs()
        self.bus.primary_changed.emit()
        self.bus.project_changed.emit()
        self.bus.import_state_changed.emit()
        self.bus.resource_tree_changed.emit()
        self.bus.task_changed.emit()
        self.bus.logs_changed.emit()
        self.bus.selection_changed.emit()

    def apply_import_cancel(self, task_title: str, message: str, cleanup_message: str = "") -> None:
        """记录导入被中止。"""

        state = self.import_state
        progress_text = state.progress_text
        state.last_error = message
        state.last_success = ""
        state.can_execute = bool(state.preview_lines)
        state.last_cleanup_status = cleanup_message
        self.finish_import_activity()
        self._prepend_issue("已中止", task_title, message)
        self._upsert_task(task_title, "已中止", progress_text, message)
        self._prepend_log("WARNING", "gui.import", message)
        if cleanup_message:
            self._prepend_log("INFO", "gui.import", cleanup_message)
        self.bus.import_state_changed.emit()
        self.bus.task_changed.emit()
        self.bus.logs_changed.emit()
        self.bus.issues_changed.emit()

    def apply_import_error(self, task_title: str, message: str) -> None:
        """记录导入失败。"""

        state = self.import_state
        state.last_error = message
        state.last_success = ""
        state.can_execute = False
        self.finish_import_activity()
        self._prepend_issue("失败", task_title, message)
        self._upsert_task(task_title, "失败", "0 / 1", message)
        self._prepend_log("ERROR", "gui.import", message)
        self.bus.import_state_changed.emit()
        self.bus.task_changed.emit()
        self.bus.logs_changed.emit()
        self.bus.issues_changed.emit()

    def finish_import_activity(self) -> None:
        """清理导入忙碌状态。"""

        state = self.import_state
        state.busy = False
        state.active_task_title = ""
        state.busy_title = ""
        state.busy_detail = ""
        state.phase_code = ""
        state.phase_label = ""
        state.progress_current = None
        state.progress_total = None
        state.progress_percent = None
        state.progress_prefix = ""
        state.cancellable = False
        state.cancel_requested = False
        state.rollback_pending = False
        state.operation_id = ""

    def arm_close_guard(self) -> None:
        """标记关闭保护已开启。"""

        self.import_state.close_guard_active = True
        self.bus.import_state_changed.emit()

    def clear_close_guard(self) -> None:
        """清理关闭保护标记。"""

        self.import_state.close_guard_active = False
        self.bus.import_state_changed.emit()

    def add_issue(self, title: str, category: str, detail: str) -> None:
        """添加问题记录。"""

        self._prepend_issue("失败", f"{category}：{title}", detail)
        self.bus.issues_changed.emit()

    def _refresh_import_step(self, *, preview_ready: bool = False) -> None:
        """刷新导入步骤状态。"""

        if not self.import_state.project_directory_selected:
            self.import_state.current_step = ImportStep.PROJECT_DIRECTORY
            self.import_state.can_execute = False
            return
        if not self.import_state.has_import_source:
            self.import_state.current_step = ImportStep.IMPORT_SOURCE
            self.import_state.can_execute = False
            return
        if preview_ready or (self.import_state.preview_lines and self.import_state.can_execute):
            self.import_state.current_step = ImportStep.EXECUTE_IMPORT
            return
        self.import_state.current_step = ImportStep.PREVIEW
        self.import_state.can_execute = False

    def _clear_import_preview_state(self) -> None:
        """清空导入预览缓存。"""

        state = self.import_state
        state.preview_lines = ()
        state.unit_lines = ()
        state.parameter_lines = ()
        state.timing_lines = ()
        state.available_series_categories = ()
        state.metadata_mode_text = "-"
        state.detected_scheme = ""
        state.last_success = ""
        state.last_error = ""
        state.last_cleanup_status = ""
        self.finish_import_activity()

    def _remember_import_source_dir(self, path: Path | None) -> None:
        """记录最近使用的导入目录。"""

        if path is None:
            return
        directory = path if path.is_dir() else path.parent
        if self.import_state.import_kind is ImportKind.SAMPLE:
            self.import_state.recent_sample_source_dir = directory
            return
        self.import_state.recent_sampleset_source_dir = directory

    def _clear_import_issues(self) -> None:
        """清除与导入相关的问题记录。"""

        blocked_titles = {"导入样本", "导入样本集", "批量导入样本", "预览样本", "预览样本集", "深度检查单位"}
        self.issues = [item for item in self.issues if item.title not in blocked_titles]

    def _build_subset_preview_rows(self, filter_spec: FilterSpec) -> tuple[tuple[str, ...], ...]:
        """构造符合筛选条件的预览行。"""

        if self.primary_runtime is None:
            return ()
        matched: list[tuple[str, object]] = []
        for uid, sample in self.primary_runtime.items():
            if sample_matches_filter(sample, uid=str(uid), filter_spec=filter_spec):
                matched.append((str(uid), sample))
        if filter_spec.sort_by:
            matched.sort(
                key=lambda item: metadata_sort_value(item[1], filter_spec.sort_by),
                reverse=filter_spec.sort_desc,
            )
        if filter_spec.offset > 0:
            matched = matched[filter_spec.offset :]
        row_limit = filter_spec.limit if filter_spec.limit is not None else 200
        row_limit = max(0, min(row_limit, 200))
        metadata_fields = self.primary_sampleset.metadata_fields
        rows: list[tuple[str, ...]] = []
        for uid, sample in matched[:row_limit]:
            rows.append(build_metadata_preview_row(uid=str(uid), sample=sample, metadata_fields=metadata_fields))
        return tuple(rows)

    def _build_rows_for_uids(self, uids: tuple[str, ...]) -> tuple[tuple[str, ...], ...]:
        """按 UID 列表构造预览行。"""

        if self.primary_runtime is None:
            return tuple((uid, uid) for uid in uids)
        metadata_fields = self.primary_sampleset.metadata_fields
        rows: list[tuple[str, ...]] = []
        for uid in uids:
            sample = self.primary_runtime.get(uid)
            if sample is None:
                rows.append((uid, uid, *("" for _ in metadata_fields)))
                continue
            rows.append(build_metadata_preview_row(uid=uid, sample=sample, metadata_fields=metadata_fields))
        return tuple(rows)

    def _existing_subset_created_at(self, subset_id: str, *, default: str) -> str:
        """返回已有子样本集的创建时间，不存在则返回默认值。"""

        definition = next((item for item in self.subset_state.subsets if item.id == subset_id), None)
        if definition is None:
            return default
        return definition.created_at

    def _append_timing_logs(self, timing_lines: tuple[str, ...]) -> None:
        """将计时行追加到日志。"""

        for line in timing_lines:
            self._prepend_log("INFO", "gui.import", line)

    def _sync_plot_tree_from_records(self) -> None:
        """从图形记录同步绘图树。"""

        self.plot_tree = tuple(
            PlotNode(
                item.title,
                (
                    PlotNode(f"模式: {item.plot_mode}"),
                    PlotNode(f"来源: {item.source_name}"),
                    PlotNode(f"样本数: {item.sample_count}"),
                    PlotNode(f"保存路径: {item.saved_path or '-'}"),
                ),
            )
            for item in self.plot_records
        )

    def _prepend_task(self, title: str, status: str, progress_text: str, detail: str) -> None:
        """在任务列表首部插入新任务。"""

        self.tasks.insert(0, TaskRecord(title, status, progress_text, detail))

    def _upsert_task(self, title: str, status: str, progress_text: str, detail: str) -> None:
        """更新或插入任务记录。"""

        for item in self.tasks:
            if item.title == title:
                item.status = status
                item.progress_text = progress_text
                item.detail = detail
                return
        self._prepend_task(title, status, progress_text, detail)

    def _prepend_log(self, level: str, logger_name: str, message: str) -> None:
        """在日志首部插入新记录。"""

        self.logs.insert(0, LogRecord(level, logger_name, message, now_text()))

    def _prepend_issue(self, status: str, title: str, detail: str) -> None:
        """在问题列表首部插入新记录。"""

        self.issues.insert(0, IssueRecord(status, title, detail))


def resolve_scope_uids(session: ProjectSession, uids_text: str = "") -> list[str]:
    """根据当前范围与附加 UID 过滤解析样本 UID。"""

    runtime = session.primary_runtime
    if runtime is None or not hasattr(runtime, "items"):
        return []
    manual_tokens = [item.strip() for item in uids_text.split(",") if item.strip()]
    alias_to_uid: dict[str, str] = {}
    needs_alias_lookup = bool(manual_tokens) or session.current_scope.scope_kind in {
        "single_sample",
        "temporary_selection",
    }
    if needs_alias_lookup:
        alias_to_uid = {str(getattr(sample, "alias", uid)): str(uid) for uid, sample in runtime.items()}
    if session.current_scope.scope_kind == "all_samples":
        base_uids = [str(uid) for uid in runtime.keys()]
    elif session.current_scope.scope_kind == "saved_subset":
        definition = next(
            (item for item in session.subset_state.subsets if item.id in session.current_scope.subset_ids), None
        )
        base_uids = list(definition.resolved_uids) if definition is not None else []
    elif session.current_scope.scope_kind == "multi_subset_union":
        ordered: list[str] = []
        seen: set[str] = set()
        for subset_id in session.current_scope.subset_ids:
            definition = next((item for item in session.subset_state.subsets if item.id == subset_id), None)
            if definition is None:
                continue
            for uid in definition.resolved_uids:
                if uid in seen:
                    continue
                seen.add(uid)
                ordered.append(uid)
        base_uids = ordered
    else:
        base_uids = [alias_to_uid.get(token, token) for token in session.current_scope.sample_uids]
    if not manual_tokens:
        return base_uids
    resolved_manual = {alias_to_uid.get(token, token) for token in manual_tokens}
    return [uid for uid in base_uids if uid in resolved_manual]


def describe_scope(session: ProjectSession) -> str:
    """返回当前范围的中文摘要。"""

    scope = session.current_scope
    if scope.scope_kind == "all_samples":
        return "全部样本"
    if scope.scope_kind == "saved_subset":
        definition = next((item for item in session.subset_state.subsets if item.id in scope.subset_ids), None)
        return definition.name if definition is not None else "当前子样本集"
    if scope.scope_kind == "multi_subset_union":
        names = [item.name for item in session.subset_state.subsets if item.id in set(scope.subset_ids)]
        return f"多子样本集（{len(names)} 个）"
    if scope.scope_kind == "single_sample":
        return f"单个样本（{scope.sample_uids[0]}）" if scope.sample_uids else "单个样本"
    if scope.scope_kind == "temporary_selection":
        return f"临时手选（{len(scope.sample_uids)} 个）"
    return scope.scope_kind


__all__ = [
    "ModuleKey",
    "MODULE_LABELS",
    "ImportKind",
    "ImportStep",
    "SampleSetSummary",
    "TaskRecord",
    "LogRecord",
    "IssueRecord",
    "ExportRecord",
    "ReviewRecord",
    "PlotNode",
    "PlotRecord",
    "ImportState",
    "CapabilitySnapshot",
    "MetadataFilterClause",
    "MetadataHookSpec",
    "FilterSpec",
    "SubsetDefinition",
    "ScopeSelection",
    "SubsetState",
    "ProcessingRequestSnapshot",
    "ProcessingPreviewRequestSnapshot",
    "ProcessingParameterSpec",
    "ProcessingActionSpec",
    "ProcessingState",
    "PlotState",
    "ExportState",
    "ImportPreviewLike",
    "ImportResultLike",
    "ProjectSession",
    "resolve_scope_uids",
    "describe_scope",
]
