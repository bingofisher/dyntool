"""GUI 项目文件持久化。"""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
import json
from pathlib import Path
from typing import Any

from ..session import (
    FilterSpec,
    ImportKind,
    ImportState,
    ImportStep,
    MetadataFilterClause,
    MetadataHookSpec,
    ModuleKey,
    ProjectSession,
    SampleSetSummary,
    ScopeSelection,
    SubsetDefinition,
    SubsetState,
)


class ProjectFileStore:
    """负责读写 GUI 项目文件。"""

    def save(self, session: ProjectSession, path: str | Path) -> Path:
        """保存 GUI 项目状态到 JSON 文件。"""

        target = Path(path).resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "project_name": session.project_name,
            "workdir": str(session.workdir),
            "export_dir": str(session.export_dir),
            "note": session.note,
            "last_saved": session.last_saved,
            "current_module": session.current_module.value,
            "current_selection": session.current_selection,
            "dirty": session.dirty,
            "demo_key": session.demo_key,
            "primary_sampleset": self._to_jsonable(session.primary_sampleset),
            "compare_sampleset": self._to_jsonable(session.compare_sampleset),
            "other_samplesets": [self._to_jsonable(item) for item in session.other_samplesets],
            "recent_import_lines": list(session.recent_import_lines),
            "import_state": self._dump_import_state(session.import_state),
            "subset_state": self._dump_subset_state(session.subset_state),
            "current_scope": self._to_jsonable(session.current_scope),
        }
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return target

    def load(self, path: str | Path) -> ProjectSession:
        """从 JSON 文件加载 GUI 项目状态。"""

        source = Path(path).resolve()
        payload = json.loads(source.read_text(encoding="utf-8"))
        session = ProjectSession(
            project_name=str(payload["project_name"]),
            workdir=Path(str(payload["workdir"])),
            export_dir=Path(str(payload["export_dir"])),
            note=str(payload["note"]),
            last_saved=str(payload["last_saved"]),
            primary_sampleset=self._load_summary(payload["primary_sampleset"]),
            compare_sampleset=self._load_optional_summary(payload.get("compare_sampleset")),
            other_samplesets=tuple(self._load_summary(item) for item in payload.get("other_samplesets", [])),
            current_module=ModuleKey(str(payload.get("current_module", ModuleKey.PROJECT.value))),
            current_selection=str(payload.get("current_selection", "当前项目")),
            dirty=bool(payload.get("dirty", False)),
            demo_key=str(payload.get("demo_key", "loaded")),
            recent_import_lines=tuple(str(item) for item in payload.get("recent_import_lines", [])),
            import_state=self._load_import_state(payload.get("import_state", {})),
            subset_state=self._load_subset_state(payload.get("subset_state", {})),
            current_scope=self._load_scope_selection(payload.get("current_scope", {})),
        )
        session.mark_saved(str(payload.get("last_saved", session.last_saved)))
        return session

    def _dump_import_state(self, state: ImportState) -> dict[str, Any]:
        return {
            "import_kind": state.import_kind.value,
            "current_step": state.current_step.value,
            "project_directory_selected": state.project_directory_selected,
            "source_path": None if state.source_path is None else str(state.source_path),
            "sample_batch_paths": [str(path) for path in state.sample_batch_paths],
            "requested_scheme": None if state.requested_scheme is None else state.requested_scheme.value,
            "load_mode": state.load_mode.value,
            "workers": state.workers,
            "strict": state.strict,
            "recent_sample_source_dir": None
            if state.recent_sample_source_dir is None
            else str(state.recent_sample_source_dir),
            "recent_sampleset_source_dir": None
            if state.recent_sampleset_source_dir is None
            else str(state.recent_sampleset_source_dir),
            "last_success": state.last_success,
            "last_error": state.last_error,
            "last_cleanup_status": state.last_cleanup_status,
            "preview_lines": list(state.preview_lines),
            "unit_lines": list(state.unit_lines),
            "parameter_lines": list(state.parameter_lines),
            "timing_lines": list(state.timing_lines),
            "available_series_categories": list(state.available_series_categories),
            "metadata_mode_text": state.metadata_mode_text,
            "detected_scheme": state.detected_scheme,
            "can_execute": state.can_execute,
            "csv_sep": state.csv_sep,
            "csv_header": state.csv_header,
            "csv_index_col": state.csv_index_col,
            "csv_encoding": state.csv_encoding,
            "csv_skiprows": state.csv_skiprows,
            "csv_decimal": state.csv_decimal,
            "advanced_expanded": state.advanced_expanded,
        }

    def _dump_subset_state(self, state: SubsetState) -> dict[str, Any]:
        return {
            "filter_spec": self._to_jsonable(state.filter_spec),
            "metadata_hook_specs": [self._to_jsonable(item) for item in state.metadata_hook_specs],
            "preview_columns": list(state.preview_columns),
            "preview_rows": [list(row) for row in state.preview_rows],
            "preview_count": state.preview_count,
            "current_condition_summary": state.current_condition_summary,
            "selected_subset_id": state.selected_subset_id,
            "last_message": state.last_message,
            "last_failure_message": state.last_failure_message,
            "subsets": [self._to_jsonable(item) for item in state.subsets],
        }

    def _load_import_state(self, payload: dict[str, Any]) -> ImportState:
        state = ImportState(
            import_kind=ImportKind(str(payload.get("import_kind", ImportKind.SAMPLE_SET.value))),
            current_step=ImportStep(str(payload.get("current_step", ImportStep.PROJECT_DIRECTORY.value))),
            project_directory_selected=bool(payload.get("project_directory_selected", False)),
            source_path=self._load_optional_path(payload.get("source_path")),
            sample_batch_paths=tuple(Path(str(item)).resolve() for item in payload.get("sample_batch_paths", [])),
            load_mode=self._load_mode(payload.get("load_mode")),
            workers=int(payload.get("workers", 1)),
            strict=bool(payload.get("strict", True)),
            recent_sample_source_dir=self._load_optional_path(payload.get("recent_sample_source_dir")),
            recent_sampleset_source_dir=self._load_optional_path(payload.get("recent_sampleset_source_dir")),
            last_success=str(payload.get("last_success", "")),
            last_error=str(payload.get("last_error", "")),
            last_cleanup_status=str(payload.get("last_cleanup_status", "")),
            preview_lines=tuple(str(item) for item in payload.get("preview_lines", [])),
            unit_lines=tuple(str(item) for item in payload.get("unit_lines", [])),
            parameter_lines=tuple(str(item) for item in payload.get("parameter_lines", [])),
            timing_lines=tuple(str(item) for item in payload.get("timing_lines", [])),
            available_series_categories=tuple(str(item) for item in payload.get("available_series_categories", [])),
            metadata_mode_text=str(payload.get("metadata_mode_text", "-")),
            detected_scheme=str(payload.get("detected_scheme", "")),
            can_execute=bool(payload.get("can_execute", False)),
            csv_sep=str(payload.get("csv_sep", ",")),
            csv_header=str(payload.get("csv_header", "0")),
            csv_index_col=str(payload.get("csv_index_col", "0")),
            csv_encoding=str(payload.get("csv_encoding", "utf-8")),
            csv_skiprows=str(payload.get("csv_skiprows", "0")),
            csv_decimal=str(payload.get("csv_decimal", ".")),
            advanced_expanded=bool(payload.get("advanced_expanded", False)),
        )
        return state

    def _load_subset_state(self, payload: dict[str, Any]) -> SubsetState:
        return SubsetState(
            filter_spec=self._load_filter_spec(payload.get("filter_spec", {})),
            metadata_hook_specs=tuple(
                self._load_metadata_hook_spec(item) for item in payload.get("metadata_hook_specs", [])
            ),
            preview_columns=tuple(str(item) for item in payload.get("preview_columns", ["UID", "Alias"])),
            preview_rows=tuple(tuple(str(value) for value in row) for row in payload.get("preview_rows", [])),
            preview_count=int(payload.get("preview_count", 0)),
            current_condition_summary=str(payload.get("current_condition_summary", "")),
            selected_subset_id=str(payload.get("selected_subset_id", "")),
            last_message=str(payload.get("last_message", "")),
            last_failure_message=str(payload.get("last_failure_message", "")),
            subsets=tuple(self._load_subset_definition(item) for item in payload.get("subsets", [])),
        )

    def _load_filter_spec(self, payload: dict[str, Any]) -> FilterSpec:
        clauses = payload.get("metadata_clauses")
        if clauses is None:
            clauses = [
                {
                    "field_name": str(field),
                    "field_kind": "categorical",
                    "match_mode": "values",
                    "values": list(values),
                }
                for field, values in payload.get("metadata_filters", [])
            ]
        return FilterSpec(
            metadata_clauses=tuple(self._load_metadata_filter_clause(item) for item in clauses),
            keyword=str(payload.get("keyword", "")),
            data_categories=tuple(str(item) for item in payload.get("data_categories", [])),
            result_categories=tuple(str(item) for item in payload.get("result_categories", [])),
            sort_by=str(payload.get("sort_by", "")),
            sort_desc=bool(payload.get("sort_desc", False)),
            limit=self._load_optional_int(payload.get("limit")),
            offset=int(payload.get("offset", 0)),
        )

    def _load_metadata_filter_clause(self, payload: dict[str, Any]) -> MetadataFilterClause:
        return MetadataFilterClause(
            field_name=str(payload.get("field_name", "")),
            field_kind=str(payload.get("field_kind", "text")),
            match_mode=str(payload.get("match_mode", "text")),
            values=tuple(str(item) for item in payload.get("values", [])),
            min_value=self._load_optional_float(payload.get("min_value")),
            max_value=self._load_optional_float(payload.get("max_value")),
            text_value=str(payload.get("text_value", "")),
        )

    def _load_metadata_hook_spec(self, payload: dict[str, Any]) -> MetadataHookSpec:
        return MetadataHookSpec(
            field_name=str(payload.get("field_name", "")),
            field_kind=str(payload.get("field_kind", "text")),
            display_name=str(payload.get("display_name", payload.get("field_name", ""))),
            candidate_values=tuple(str(item) for item in payload.get("candidate_values", [])),
        )

    def _load_subset_definition(self, payload: dict[str, Any]) -> SubsetDefinition:
        return SubsetDefinition(
            id=str(payload["id"]),
            name=str(payload["name"]),
            filter_spec=self._load_filter_spec(payload.get("filter_spec", {})),
            resolved_uids=tuple(str(item) for item in payload.get("resolved_uids", [])),
            sample_count=int(payload.get("sample_count", 0)),
            created_at=str(payload.get("created_at", "")),
            updated_at=str(payload.get("updated_at", "")),
            note=str(payload.get("note", "")),
            frozen=bool(payload.get("frozen", False)),
        )

    def _load_scope_selection(self, payload: dict[str, Any]) -> ScopeSelection:
        return ScopeSelection(
            scope_kind=str(payload.get("scope_kind", "all_samples")),
            subset_ids=tuple(str(item) for item in payload.get("subset_ids", [])),
            sample_uids=tuple(str(item) for item in payload.get("sample_uids", [])),
            note=str(payload.get("note", "")),
        )

    def _load_mode(self, value: Any) -> Any:
        from dyntool.storage import SampleLoadMode

        return SampleLoadMode(str(value or SampleLoadMode.LAZY.value))

    def _load_summary(self, payload: dict[str, Any]) -> SampleSetSummary:
        return SampleSetSummary(**payload)

    def _load_optional_summary(self, payload: Any) -> SampleSetSummary | None:
        if payload is None:
            return None
        return self._load_summary(payload)

    def _load_optional_path(self, value: Any) -> Path | None:
        if value in {None, ""}:
            return None
        return Path(str(value)).resolve()

    def _load_optional_float(self, value: Any) -> float | None:
        if value in {None, ""}:
            return None
        return float(value)

    def _load_optional_int(self, value: Any) -> int | None:
        if value in {None, ""}:
            return None
        return int(value)

    def _to_jsonable(self, value: Any) -> Any:
        if value is None:
            return None
        if is_dataclass(value):
            return asdict(value)
        return value
