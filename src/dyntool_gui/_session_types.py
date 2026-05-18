"""GUI 会话状态数据类型与公共辅助函数。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol

from dyntool import StorageScheme
from dyntool.storage import SampleLoadMode


class ModuleKey(StrEnum):
    """主模块标识。"""

    PROJECT = "project"
    IMPORT = "import"
    SUBSET = "subset"
    PROCESSING = "processing"
    PLOTTING = "plotting"
    EXPORT = "export"


MODULE_LABELS: dict[ModuleKey, str] = {
    ModuleKey.PROJECT: "总览",
    ModuleKey.IMPORT: "导入与筛选",
    ModuleKey.SUBSET: "筛选与子集",
    ModuleKey.PROCESSING: "数据处理",
    ModuleKey.PLOTTING: "图形绘制",
    ModuleKey.EXPORT: "交付",
}


class ImportKind(StrEnum):
    """导入类型。"""

    SAMPLE = "sample"
    SAMPLE_SET = "sample_set"


class ImportStep(StrEnum):
    """导入工作流步骤。"""

    PROJECT_DIRECTORY = "project_directory"
    IMPORT_SOURCE = "import_source"
    PREVIEW = "preview"
    EXECUTE_IMPORT = "execute_import"


@dataclass(slots=True)
class SampleSetSummary:
    """样本集摘要。"""

    name: str
    class_name: str
    sample_type: str
    sample_domain: str
    metadata_type: str
    metadata_fields: tuple[str, ...]
    supported_categories: tuple[str, ...]
    storable_categories: tuple[str, ...]
    supported_fields: tuple[str, ...]
    sample_count: int
    loaded_count: int
    unloaded_count: int
    storage_binding: str
    strict: bool
    storage_dirty: bool


@dataclass(slots=True)
class TaskRecord:
    """任务记录。"""

    title: str
    status: str
    progress_text: str
    detail: str


@dataclass(slots=True)
class LogRecord:
    """日志记录。"""

    level: str
    logger_name: str
    message: str
    timestamp: str


@dataclass(slots=True)
class IssueRecord:
    """问题记录。"""

    status: str
    title: str
    detail: str


@dataclass(slots=True)
class ExportRecord:
    """导出记录。"""

    name: str
    target: str
    status: str
    timestamp: str


@dataclass(slots=True)
class ReviewRecord:
    """审查记录。"""

    title: str
    status: str
    summary: str


@dataclass(slots=True)
class PlotNode:
    """绘图任务树节点。"""

    title: str
    children: tuple["PlotNode", ...] = ()


@dataclass(slots=True)
class PlotRecord:
    """图形记录。"""

    id: str
    title: str
    plot_mode: str
    source_name: str
    sample_count: int
    saved_path: str
    created_at: str


@dataclass(slots=True)
class ImportState:
    """导入工作流状态。"""

    import_kind: ImportKind = ImportKind.SAMPLE_SET
    current_step: ImportStep = ImportStep.PROJECT_DIRECTORY
    project_directory_selected: bool = False
    source_path: Path | None = None
    sample_batch_paths: tuple[Path, ...] = ()
    preview_lines: tuple[str, ...] = ()
    unit_lines: tuple[str, ...] = ()
    parameter_lines: tuple[str, ...] = ()
    timing_lines: tuple[str, ...] = ()
    available_series_categories: tuple[str, ...] = ()
    metadata_mode_text: str = "-"
    detected_scheme: str = ""
    requested_scheme: StorageScheme | None = None
    load_mode: SampleLoadMode = SampleLoadMode.LAZY
    workers: int = 1
    strict: bool = True
    recent_sample_source_dir: Path | None = None
    recent_sampleset_source_dir: Path | None = None
    last_success: str = ""
    last_error: str = ""
    can_execute: bool = False
    csv_sep: str = ","
    csv_header: str = "0"
    csv_index_col: str = "0"
    csv_encoding: str = "utf-8"
    csv_skiprows: str = "0"
    csv_decimal: str = "."
    advanced_expanded: bool = False
    busy: bool = False
    active_task_title: str = ""
    busy_title: str = ""
    busy_detail: str = ""
    operation_id: str = ""
    phase_code: str = ""
    phase_label: str = ""
    progress_current: int | None = None
    progress_total: int | None = None
    progress_percent: int | None = None
    progress_prefix: str = ""
    cancellable: bool = False
    cancel_requested: bool = False
    rollback_pending: bool = False
    close_guard_active: bool = False
    last_cleanup_status: str = ""
    rollback_primary_summary: SampleSetSummary | None = None

    @property
    def csv_read_options(self) -> dict[str, Any]:
        """返回标准 CSV 读取参数。"""

        return {
            "sep": self.csv_sep,
            "header": _parse_optional_int(self.csv_header),
            "index_col": _parse_optional_int(self.csv_index_col),
            "encoding": self.csv_encoding,
            "skiprows": _parse_optional_int(self.csv_skiprows, default=0),
            "decimal": self.csv_decimal,
        }

    @property
    def has_import_source(self) -> bool:
        """返回当前是否已设置导入来源。"""

        return self.source_path is not None or bool(self.sample_batch_paths)

    @property
    def progress_text(self) -> str:
        """返回当前进度文案。"""

        if self.progress_prefix:
            if self.progress_current is not None and self.progress_total not in {None, 0}:
                return f"{self.progress_prefix} {self.progress_current}/{self.progress_total}"
            return f"{self.progress_prefix}..."
        if self.busy_title:
            return self.busy_title
        return "准备就绪"


@dataclass(slots=True)
class CapabilitySnapshot:
    """当前主样本集能力快照。"""

    data_slots: tuple[str, ...] = ()
    eval_results: tuple[str, ...] = ()
    scalar_frame: bool = False
    series_frame: bool = False
    peaks_frame: bool = False


@dataclass(slots=True)
class MetadataFilterClause:
    """metadata 字段筛选子句。"""

    field_name: str
    field_kind: str = "text"
    match_mode: str = "text"
    values: tuple[str, ...] = ()
    min_value: float | None = None
    max_value: float | None = None
    text_value: str = ""


@dataclass(slots=True)
class MetadataHookSpec:
    """metadata 字段 hook 描述。"""

    field_name: str
    field_kind: str
    display_name: str
    candidate_values: tuple[str, ...] = ()


@dataclass(slots=True)
class FilterSpec:
    """结构化筛选条件。"""

    metadata_clauses: tuple[MetadataFilterClause, ...] = ()
    keyword: str = ""
    data_categories: tuple[str, ...] = ()
    result_categories: tuple[str, ...] = ()
    sort_by: str = ""
    sort_desc: bool = False
    limit: int | None = None
    offset: int = 0

    @property
    def metadata_filters(self) -> tuple[tuple[str, tuple[str, ...]], ...]:
        """兼容旧的单字段值匹配结构。"""

        return tuple(
            (clause.field_name, clause.values) for clause in self.metadata_clauses if clause.match_mode == "values"
        )


@dataclass(slots=True)
class SubsetDefinition:
    """已保存子样本集定义。"""

    id: str
    name: str
    filter_spec: FilterSpec
    resolved_uids: tuple[str, ...]
    sample_count: int
    created_at: str
    updated_at: str
    note: str = ""
    mode: str = "dynamic"
    frozen: bool = False

    def __post_init__(self) -> None:
        """同步新旧子集类型字段。"""

        if self.mode == "frozen":
            self.frozen = True
        elif self.frozen:
            self.mode = "frozen"
        else:
            self.mode = "dynamic"


@dataclass(slots=True)
class ScopeSelection:
    """当前工作范围。"""

    scope_kind: str = "all_samples"
    subset_ids: tuple[str, ...] = ()
    sample_uids: tuple[str, ...] = ()
    note: str = ""


@dataclass(slots=True)
class SubsetState:
    """筛选与子样本集页状态。"""

    filter_spec: FilterSpec = field(default_factory=FilterSpec)
    metadata_hook_specs: tuple[MetadataHookSpec, ...] = ()
    preview_columns: tuple[str, ...] = ("UID", "Alias")
    preview_rows: tuple[tuple[str, ...], ...] = ()
    preview_count: int = 0
    current_condition_summary: str = ""
    selected_subset_id: str = ""
    last_message: str = ""
    last_failure_message: str = ""
    subsets: tuple[SubsetDefinition, ...] = ()


@dataclass(slots=True)
class ProcessingRequestSnapshot:
    """处理动作请求快照。"""

    action_name: str
    scope_kind: str = "all_samples"
    scope_target: str = ""
    uids_text: str = ""
    strict: bool = True
    overwrite: bool = True
    action_params: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class ProcessingPreviewRequestSnapshot:
    """处理预览请求快照。"""

    preview_kind: str = "scalar_frame"
    preview_scope: str = "subset"
    uids_text: str = ""
    metadata_fields: tuple[str, ...] = ()
    features: tuple[str, ...] = ()
    data_var: str = "freqspec"
    peak_source: str = "accel"


@dataclass(slots=True)
class ProcessingParameterSpec:
    """处理参数描述。"""

    key: str
    label: str
    editor_kind: str = "text"
    options: tuple[tuple[str, str], ...] = ()
    placeholder: str = ""
    default_value: str = ""


@dataclass(slots=True)
class ProcessingActionSpec:
    """处理动作规格。"""

    action_name: str
    label: str
    specific_params: tuple[ProcessingParameterSpec, ...] = ()


@dataclass(slots=True)
class ProcessingState:
    """处理页状态。"""

    busy: bool = False
    current_action: str = ""
    last_message: str = ""
    preview_title: str = ""
    preview_kind: str = "scalar_frame"
    preview_scope: str = "subset"
    preview_row_limit: int = 200
    auto_preview_enabled: bool = False
    last_action_count: int = 0
    last_duration_ms: int = 0
    last_failure_message: str = ""
    current_request: ProcessingRequestSnapshot | None = None
    scalar_rows: tuple[tuple[str, ...], ...] = ()
    series_rows: tuple[tuple[str, ...], ...] = ()
    peaks_rows: tuple[tuple[str, ...], ...] = ()


@dataclass(slots=True)
class PlotState:
    """绘图页状态。"""

    busy: bool = False
    plot_mode: str = "single_sample"
    source_kind: str = "sample_model"
    source_name: str = "accel"
    selected_uid: str = ""
    selected_uids: tuple[str, ...] = ()
    last_message: str = ""
    last_saved_path: str = ""
    missing_reason: str = ""
    render_requested: bool = False
    render_complete: bool = False
    point_limit: int = 20000
    save_mode: str = "preview"
    last_duration_ms: int = 0
    last_failure_message: str = ""


@dataclass(slots=True)
class ExportState:
    """导出页状态。"""

    busy: bool = False
    export_kind: str = "scalar_frame"
    output_path: str = ""
    last_message: str = ""
    last_output_path: str = ""
    missing_reason: str = ""
    validated: bool = False
    missing_requirements: tuple[str, ...] = ()
    pending_generation_action: str = ""
    last_duration_ms: int = 0
    last_failure_message: str = ""


class ImportPreviewLike(Protocol):
    """导入预览协议。"""

    source_path: Path
    preview_lines: tuple[str, ...]
    unit_lines: tuple[str, ...]
    parameter_lines: tuple[str, ...]
    timing_lines: tuple[str, ...]
    available_series_categories: tuple[str, ...]
    metadata_mode_text: str
    detected_scheme: str
    allow_execute: bool
    prepared_runtime: object | None


class ImportResultLike(Protocol):
    """导入结果协议。"""

    primary_summary: SampleSetSummary
    recent_lines: tuple[str, ...]
    success_message: str
    task_title: str
    preview_lines: tuple[str, ...]
    unit_lines: tuple[str, ...]
    parameter_lines: tuple[str, ...]
    timing_lines: tuple[str, ...]
    cleanup_message: str
    detected_scheme: str
    primary_runtime: object | None


def now_text() -> str:
    """返回当前时间的显示文字。"""

    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def slugify_subset_name(name: str) -> str:
    """将子集名称转换为稳定 ID。"""

    compact = "".join(char.lower() if char.isalnum() else "." for char in name.strip())
    compact = ".".join(part for part in compact.split(".") if part)
    return compact or f"subset.{datetime.now().strftime('%H%M%S')}"


def parse_optional_int(value: str, *, default: int | None = None) -> int | None:
    """将字符串解析为可选整数。"""

    text = value.strip()
    if text == "":
        return default
    return int(text)


def build_capability_snapshot(sample_set: object) -> CapabilitySnapshot:
    """从真实样本集构造能力快照。"""

    data_slots = tuple(sorted({name for _, sample in sample_set.items() for name in _sample_slot_names(sample)}))  # type: ignore[attr-defined]
    eval_results = tuple(name for name in ("zvl", "otovl", "fdmvl", "fpvdv") if name in data_slots)
    return CapabilitySnapshot(
        data_slots=data_slots,
        eval_results=eval_results,
        scalar_frame=True,
        series_frame=bool(data_slots),
        peaks_frame=any(name in data_slots for name in ("accel", "vel", "disp", "force")),
    )


def build_capability_snapshot_from_summary(summary: SampleSetSummary) -> CapabilitySnapshot:
    """从已计算摘要构造能力快照，避免 GUI 写回阶段触发按需加载。"""

    raw_slots = summary.supported_categories or summary.storable_categories
    data_slots = tuple(dict.fromkeys(str(item) for item in raw_slots if str(item)))
    eval_results = tuple(name for name in ("zvl", "otovl", "fdmvl", "fpvdv") if name in data_slots)
    return CapabilitySnapshot(
        data_slots=data_slots,
        eval_results=eval_results,
        scalar_frame=True,
        series_frame=bool(data_slots),
        peaks_frame=any(name in data_slots for name in ("accel", "vel", "disp", "force")),
    )


def summarize_runtime_sample_set(
    sample_set: object,
    *,
    name: str,
    storage_binding: str,
) -> SampleSetSummary:
    """从真实样本集对象构造摘要。"""

    first_sample = next(iter(sample_set.values()), None)  # type: ignore[attr-defined]
    metadata_fields: tuple[str, ...] = ()
    metadata_type = "Metadata"
    sample_type = "Sample"
    sample_domain = "default"
    if first_sample is not None:
        metadata_fields = tuple(str(item) for item in getattr(type(first_sample.metadata), "model_fields", {}).keys())
        metadata_type = type(first_sample.metadata).__name__
        sample_type = type(first_sample).__name__
        sample_domain = str(getattr(first_sample, "sample_domain", None) or "default")
    supported_categories = tuple(str(item) for item in sample_set.supported_categories())  # type: ignore[attr-defined]
    storable_categories = tuple(str(item) for item in sample_set.storable_categories())  # type: ignore[attr-defined]
    supported_fields = tuple(str(item) for item in sample_set.supported_fields())  # type: ignore[attr-defined]
    loaded_count = sum(1 for _, sample in sample_set.items() if _sample_has_any_data(sample))  # type: ignore[attr-defined]
    sample_count = len(sample_set)  # type: ignore[arg-type]
    return SampleSetSummary(
        name=name,
        class_name=type(sample_set).__name__,
        sample_type=sample_type,
        sample_domain=sample_domain,
        metadata_type=metadata_type,
        metadata_fields=metadata_fields,
        supported_categories=supported_categories,
        storable_categories=storable_categories,
        supported_fields=supported_fields,
        sample_count=sample_count,
        loaded_count=loaded_count,
        unloaded_count=max(sample_count - loaded_count, 0),
        storage_binding=storage_binding,
        strict=bool(getattr(sample_set, "strict", True)),
        storage_dirty=bool(getattr(sample_set, "storage_dirty", False)),
    )


def build_metadata_hook_specs(
    primary_sampleset: SampleSetSummary,
    primary_runtime: object | None,
) -> tuple[MetadataHookSpec, ...]:
    """根据样本集元数据构造 hook 规格。"""

    fields = tuple(str(f) for f in primary_sampleset.metadata_fields)
    if primary_runtime is None:
        return tuple(MetadataHookSpec(field_name=f, field_kind="text", display_name=f) for f in fields)

    field_values: dict[str, list[object]] = {f: [] for f in fields}
    for _, sample in primary_runtime.items():  # type: ignore[attr-defined]
        metadata = getattr(sample, "metadata", None)
        for field_name in fields:
            value = getattr(metadata, field_name, None)
            if value is not None:
                field_values[field_name].append(value)

    specs: list[MetadataHookSpec] = []
    for field_name in fields:
        values = field_values[field_name]
        if not values:
            specs.append(MetadataHookSpec(field_name=field_name, field_kind="text", display_name=field_name))
            continue
        if all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in values):
            specs.append(MetadataHookSpec(field_name=field_name, field_kind="numeric", display_name=field_name))
            continue
        unique_values = tuple(dict.fromkeys(str(v) for v in values if str(v).strip()))
        if 0 < len(unique_values) <= 16:
            specs.append(
                MetadataHookSpec(
                    field_name=field_name,
                    field_kind="categorical",
                    display_name=field_name,
                    candidate_values=unique_values,
                )
            )
            continue
        specs.append(MetadataHookSpec(field_name=field_name, field_kind="text", display_name=field_name))
    return tuple(specs)


def build_metadata_preview_columns(primary_sampleset: SampleSetSummary) -> tuple[str, ...]:
    """构造预览表列头。"""

    return ("UID", "Alias", *(str(f) for f in primary_sampleset.metadata_fields))


def build_metadata_preview_row(
    *,
    uid: str,
    sample: object,
    metadata_fields: tuple[str, ...],
) -> tuple[str, ...]:
    """构造单行预览数据。"""

    metadata = getattr(sample, "metadata", None)
    values = tuple(
        "" if getattr(metadata, field, None) is None else str(getattr(metadata, field, None))
        for field in metadata_fields
    )
    return (uid, str(getattr(sample, "alias", uid)), *values)


def describe_filter_spec(filter_spec: FilterSpec) -> str:
    """将筛选条件转换为中文摘要。"""

    parts: list[str] = []
    for clause in filter_spec.metadata_clauses:
        if clause.match_mode == "values" and clause.values:
            parts.append(f"{clause.field_name}={'/'.join(clause.values)}")
        elif clause.match_mode == "range":
            parts.append(f"{clause.field_name}={clause.min_value or '-'}~{clause.max_value or '-'}")
        elif clause.match_mode == "text" and clause.text_value.strip():
            parts.append(f"{clause.field_name}~{clause.text_value.strip()}")
    if filter_spec.keyword.strip():
        parts.append(f"关键词={filter_spec.keyword.strip()}")
    if filter_spec.data_categories:
        parts.append(f"原始数据={','.join(filter_spec.data_categories)}")
    if filter_spec.result_categories:
        parts.append(f"结果={','.join(filter_spec.result_categories)}")
    return "；".join(parts) if parts else "未设置筛选条件"


def sample_matches_filter(sample: object, *, uid: str, filter_spec: FilterSpec) -> bool:
    """判断样本是否匹配筛选条件。"""

    keyword = filter_spec.keyword.strip().lower()
    alias_text = str(getattr(sample, "alias", uid))
    if keyword and keyword not in uid.lower() and keyword not in alias_text.lower():
        return False
    metadata = getattr(sample, "metadata", None)
    for clause in filter_spec.metadata_clauses:
        current = getattr(metadata, clause.field_name, None)
        current_text = "" if current is None else str(current)
        if clause.match_mode == "values":
            if clause.values and current_text not in clause.values:
                return False
            continue
        if clause.match_mode == "range":
            if current is None:
                return False
            try:
                numeric_value = float(current)
            except (TypeError, ValueError):
                return False
            if clause.min_value is not None and numeric_value < clause.min_value:
                return False
            if clause.max_value is not None and numeric_value > clause.max_value:
                return False
            continue
        if clause.text_value.strip() and clause.text_value.strip().lower() not in current_text.lower():
            return False
    for category in filter_spec.data_categories:
        if getattr(sample, category, None) is None:
            return False
    for category in filter_spec.result_categories:
        if getattr(sample, category, None) is None:
            return False
    return True


def metadata_sort_value(sample: object, field_name: str) -> object:
    """取样本的 metadata 排序键值。"""

    metadata = getattr(sample, "metadata", None)
    if field_name == "uid":
        return str(getattr(sample, "uid", ""))
    if field_name == "alias":
        return str(getattr(sample, "alias", ""))
    value = getattr(metadata, field_name, None)
    if value is None:
        return ""
    return value


def _sample_slot_names(sample: object) -> tuple[str, ...]:
    slots: list[str] = []
    for name in ("accel", "vel", "disp", "force", "freqspec", "respspec", "otovl", "zvl", "fdmvl", "fpvdv"):
        if getattr(sample, name, None) is not None:
            slots.append(name)
    return tuple(slots)


def _sample_has_any_data(sample: object) -> bool:
    return bool(_sample_slot_names(sample))


# 保留向后兼容的私有名称（session.py 内部曾使用）
_now_text = now_text
_slugify_subset_name = slugify_subset_name
_parse_optional_int = parse_optional_int
_build_capability_snapshot = build_capability_snapshot
_build_capability_snapshot_from_summary = build_capability_snapshot_from_summary
_summarize_runtime_sample_set = summarize_runtime_sample_set


def _build_metadata_hook_specs(session: object) -> object:
    return build_metadata_hook_specs(session.primary_sampleset, session.primary_runtime)  # type: ignore[attr-defined]


def _build_metadata_preview_columns(session: object) -> object:
    return build_metadata_preview_columns(session.primary_sampleset)  # type: ignore[attr-defined]


_build_metadata_preview_row = build_metadata_preview_row
_describe_filter_spec = describe_filter_spec
_sample_matches_filter = sample_matches_filter
_metadata_sort_value = metadata_sort_value

# suppress unused-import F401 for re-export consumers
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
    "now_text",
    "slugify_subset_name",
    "parse_optional_int",
    "build_capability_snapshot",
    "build_capability_snapshot_from_summary",
    "summarize_runtime_sample_set",
    "build_metadata_hook_specs",
    "build_metadata_preview_columns",
    "build_metadata_preview_row",
    "describe_filter_spec",
    "sample_matches_filter",
    "metadata_sort_value",
]
