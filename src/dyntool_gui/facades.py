"""GUI 导入 facade。"""

from __future__ import annotations

import csv
from collections import Counter
from dataclasses import dataclass
import json
from pathlib import Path
from time import perf_counter
import sqlite3
from typing import Any, Callable, Iterator

from dyntool import AccelSeries, DefaultSample, DefaultSampleSet, SampleDomain, StorageScheme
from dyntool.infrastructure.storage_constants import (
    DEFAULT_SQLITE_INDEX_FILENAME,
    H5_ATTR_METADATA_JSON,
    META_COL_METADATA_JSON,
    METADATA_JSON_FILENAME,
    METADATA_TABLE_FILENAME,
)
from dyntool.storage import SampleLoadMode
import dyntool.storage as dt_storage

from .import_runtime import ImportOperationController
from .runtime_bridge import GuiRuntimeBridge
from .session import ImportKind, SampleSetSummary

ProgressCallback = Callable[[str, str, str, int | None, int | None, str], None]

_CATEGORY_LABELS = {
    "accel": "加速度",
    "vel": "速度",
    "disp": "位移",
    "force": "力",
}
_SERIES_CATEGORIES = ("accel", "vel", "disp", "force")

_SCHEME_LABELS = {
    StorageScheme.SET_H5: "单 H5 文件（SET_H5）",
    StorageScheme.SET_SQLITE_H5: "SQLite + H5 仓库（SET_SQLITE_H5）",
    StorageScheme.SET_DIR: "目录仓库（SET_DIR）",
    StorageScheme.SET_ATTR_TABLE: "属性表仓库（SET_ATTR_TABLE）",
}

_LOAD_MODE_LABELS = {
    SampleLoadMode.METADATA_ONLY: "仅元数据（METADATA_ONLY）",
    SampleLoadMode.LAZY: "按需加载（LAZY）",
    SampleLoadMode.EAGER: "全部加载（EAGER）",
}

_RUNTIME_BRIDGE = GuiRuntimeBridge()


@dataclass(slots=True)
class SampleSetImportRequest:
    """样本集导入请求。"""

    source_path: Path
    requested_scheme: StorageScheme | None = None
    load_mode: SampleLoadMode = SampleLoadMode.LAZY
    workers: int = 1
    strict: bool = True


@dataclass(slots=True)
class SampleBatchImportRequest:
    """样本批量导入请求。"""

    source_paths: tuple[Path, ...] = ()
    source_directory: Path | None = None
    csv_read_options: dict[str, Any] | None = None


@dataclass(slots=True)
class ImportPreview:
    """导入预览结果。"""

    source_path: Path
    preview_lines: tuple[str, ...]
    unit_lines: tuple[str, ...]
    parameter_lines: tuple[str, ...]
    timing_lines: tuple[str, ...] = ()
    available_series_categories: tuple[str, ...] = ()
    metadata_mode_text: str = "-"
    detected_scheme: str = ""
    allow_execute: bool = False
    prepared_runtime: object | None = None


@dataclass(slots=True)
class ImportResult:
    """导入执行结果。"""

    primary_summary: SampleSetSummary
    recent_lines: tuple[str, ...]
    success_message: str
    task_title: str
    preview_lines: tuple[str, ...]
    unit_lines: tuple[str, ...]
    parameter_lines: tuple[str, ...]
    timing_lines: tuple[str, ...] = ()
    cleanup_message: str = ""
    cancelled: bool = False
    detected_scheme: str = ""
    primary_runtime: object | None = None


@dataclass(slots=True)
class _SampleSetDomainInspection:
    """仓库级样本领域推断结果。"""

    sample_domain: SampleDomain | None
    schema_names: tuple[str, ...]
    error_message: str = ""


class GuiImportFacade:
    """GUI 导入薄适配层。"""

    def preview_sample_csv(
        self,
        path: str | Path,
        csv_read_options: dict[str, Any],
        *,
        controller: ImportOperationController | None = None,
    ) -> ImportPreview:
        """兼容保留的单文件 CSV 预览入口。"""

        return self.preview_sample_csv_batch(
            SampleBatchImportRequest(
                source_paths=(Path(path).resolve(),),
                csv_read_options=csv_read_options,
            ),
            controller=controller,
        )

    def import_sample_csv(
        self,
        path: str | Path,
        csv_read_options: dict[str, Any],
        *,
        controller: ImportOperationController | None = None,
    ) -> ImportResult:
        """兼容保留的单文件 CSV 导入入口。"""

        return self.execute_sample_csv_batch(
            SampleBatchImportRequest(
                source_paths=(Path(path).resolve(),),
                csv_read_options=csv_read_options,
            ),
            controller=controller,
        )

    def import_sample_csv_batch(
        self,
        request: SampleBatchImportRequest,
        *,
        controller: ImportOperationController | None = None,
    ) -> ImportResult:
        """兼容保留的批量 CSV 导入入口。"""

        return self.execute_sample_csv_batch(request, controller=controller)

    def preview_sample_csv_batch(
        self,
        request: SampleBatchImportRequest,
        *,
        controller: ImportOperationController | None = None,
    ) -> ImportPreview:
        """预览批量 CSV 导入。"""

        started = perf_counter()
        csv_paths = _resolve_csv_batch_paths(request)
        csv_read_options = dict(request.csv_read_options or {})
        successes: list[tuple[Path, dict[str, str]]] = []
        failures: list[tuple[Path, str]] = []
        source_root = request.source_directory.resolve() if request.source_directory is not None else csv_paths[0]
        total = len(csv_paths)
        _report_phase(
            controller,
            "check_csv_batch",
            "检查批量文件",
            progress_prefix="检查批量文件",
            current=0,
            total=total,
            detail=f"共 {total} 个 CSV 文件。",
        )
        for index, path in enumerate(csv_paths, start=1):
            _checkpoint(controller)
            try:
                AccelSeries.from_csv(path, csv_read_options=csv_read_options)
                units = AccelSeries.inspect_units(path, fmt="csv", csv_read_options=csv_read_options)
                successes.append((path, units))
            except Exception as exc:  # noqa: BLE001
                failures.append((path, str(exc)))
            _report_phase(
                controller,
                "check_csv_batch",
                "检查批量文件",
                progress_prefix="检查批量文件",
                current=index,
                total=total,
                detail=path.name,
            )

        preview_lines = [
            f"来源位置：{source_root}",
            f"来源类型：{'目录扫描' if request.source_directory is not None else '多文件'}",
            f"命中 CSV 数量：{len(csv_paths)}",
            f"成功解析数量：{len(successes)}",
            f"失败数量：{len(failures)}",
        ]
        preview_lines.extend(f"文件：{path.name}" for path in csv_paths[:5])
        preview_lines.extend(f"失败文件：{path.name} -> {message}" for path, message in failures[:5])
        parameter_lines = _csv_parameter_lines(csv_read_options)
        timing_lines = (f"批量检查耗时：{perf_counter() - started:.3f} 秒",)
        return ImportPreview(
            source_path=request.source_directory or csv_paths[0],
            preview_lines=tuple(preview_lines),
            unit_lines=_summarize_batch_units([item[1] for item in successes]),
            parameter_lines=parameter_lines,
            timing_lines=timing_lines,
            available_series_categories=("accel",) if successes else (),
            metadata_mode_text="-",
            allow_execute=bool(successes) and not failures,
        )

    def execute_sample_csv_batch(
        self,
        request: SampleBatchImportRequest,
        *,
        controller: ImportOperationController | None = None,
    ) -> ImportResult:
        """执行批量 CSV 导入。"""

        preview = self.preview_sample_csv_batch(request, controller=controller)
        if not preview.allow_execute:
            raise ValueError("批量 CSV 预览存在失败文件，请先修正后再导入。")

        started = perf_counter()
        csv_paths = _resolve_csv_batch_paths(request)
        csv_read_options = dict(request.csv_read_options or {})
        samples = []
        total = len(csv_paths)
        for index, path in enumerate(csv_paths, start=1):
            _checkpoint(controller)
            _report_phase(
                controller,
                "load_csv_batch",
                "加载样本",
                progress_prefix="加载样本",
                current=index - 1,
                total=total,
                detail=path.name,
            )
            accel = AccelSeries.from_csv(path, csv_read_options=csv_read_options)
            sample = DefaultSample.from_models(accel=accel)
            sample.patch_metadata(extra={"source_file": path.name})
            sample.set_alias(path.stem)
            samples.append(sample)
            _report_phase(
                controller,
                "load_csv_batch",
                "加载样本",
                progress_prefix="加载样本",
                current=index,
                total=total,
                detail=path.name,
            )

        _report_phase(
            controller,
            "commit_primary",
            "写回主集",
            progress_prefix="写回主集",
            current=1,
            total=1,
            detail="组装新的主样本集摘要。",
        )
        sample_set = DefaultSampleSet.from_samples(samples)
        summary = _build_sample_set_summary(
            sample_set,
            name="主样本集 / 批量 CSV",
            storage_binding="内存 / 未保存",
            storage_dirty=True,
        )
        return ImportResult(
            primary_summary=summary,
            recent_lines=(
                f"最近导入：批量 CSV {len(csv_paths)} 个文件",
                f"来源：{csv_paths[0].parent}",
                "绑定结果：已写成当前主样本集",
            ),
            success_message=f"已将 {len(csv_paths)} 个 CSV 样本导入为当前主集。",
            task_title="批量导入样本",
            preview_lines=preview.preview_lines,
            unit_lines=preview.unit_lines,
            parameter_lines=preview.parameter_lines,
            timing_lines=(f"批量导入耗时：{perf_counter() - started:.3f} 秒",),
            cleanup_message="已建立当前主集的运行态对象。",
            primary_runtime=sample_set,
        )

    def preview_sample_set_storage(
        self,
        path: str | Path,
        *,
        controller: ImportOperationController | None = None,
    ) -> ImportPreview:
        """兼容保留的样本集预览入口。"""

        return self.preview_sample_set_repository_light(
            SampleSetImportRequest(
                source_path=Path(path).resolve(),
                requested_scheme=None,
            ),
            controller=controller,
        )

    def import_sample_set_storage(
        self,
        path: str | Path,
        *,
        controller: ImportOperationController | None = None,
    ) -> ImportResult:
        """兼容保留的样本集导入入口。"""

        return self.execute_sample_set_repository(
            SampleSetImportRequest(
                source_path=Path(path).resolve(),
                requested_scheme=None,
            ),
            controller=controller,
        )

    def preview_sample_set_repository(
        self,
        request: SampleSetImportRequest,
        *,
        controller: ImportOperationController | None = None,
    ) -> ImportPreview:
        """兼容保留的样本集轻量预览入口。"""

        return self.preview_sample_set_repository_light(request, controller=controller)

    def import_sample_set_repository(
        self,
        request: SampleSetImportRequest,
        *,
        controller: ImportOperationController | None = None,
    ) -> ImportResult:
        """兼容保留的样本集执行入口。"""

        return self.execute_sample_set_repository(request, controller=controller)

    def preview_sample_set_repository_light(
        self,
        request: SampleSetImportRequest,
        *,
        controller: ImportOperationController | None = None,
        keep_runtime: bool = False,
    ) -> ImportPreview:
        """执行样本集轻量检查。"""

        started = perf_counter()
        prepared = self._prepare_lightweight_sampleset(request, controller=controller)
        preview_lines = (
            prepared.preview_lines + _sample_set_summary_lines(prepared.sample_set)
            if prepared.allow_execute
            else prepared.preview_lines
        )
        unit_lines = (
            ("默认只执行轻量检查。深度单位检查请点击“深度检查单位”。",)
            if prepared.allow_execute
            else ("轻量检查未通过，已阻止导入。",)
        )
        timing_lines = (f"轻量检查耗时：{perf_counter() - started:.3f} 秒",)
        try:
            return ImportPreview(
                source_path=prepared.source_path,
                preview_lines=preview_lines,
                unit_lines=unit_lines,
                parameter_lines=prepared.parameter_lines,
                timing_lines=timing_lines,
                available_series_categories=prepared.available_series_categories,
                metadata_mode_text=prepared.metadata_mode_text,
                detected_scheme=prepared.detected_scheme,
                allow_execute=prepared.allow_execute,
                prepared_runtime=(
                    prepared.sample_set
                    if keep_runtime and prepared.allow_execute and request.load_mode is SampleLoadMode.LAZY
                    else None
                ),
            )
        finally:
            if not (keep_runtime and prepared.allow_execute and request.load_mode is SampleLoadMode.LAZY):
                _cleanup_temporary_sample_set(prepared.sample_set)

    def preview_sample_set_repository_deep_units(
        self,
        request: SampleSetImportRequest,
        *,
        controller: ImportOperationController | None = None,
    ) -> ImportPreview:
        """执行样本集深度单位检查。"""

        started = perf_counter()
        prepared = self._prepare_lightweight_sampleset(request, controller=controller)
        sample_set = prepared.sample_set
        try:
            unit_lines = _summarize_sample_set_units_deep(
                sample_set,
                available_categories=prepared.available_series_categories,
                request=request,
                controller=controller,
            )
            preview_lines = prepared.preview_lines + _sample_set_summary_lines(sample_set)
            timing_lines = (
                f"轻量检查耗时：{prepared.light_seconds:.3f} 秒",
                f"深度检查耗时：{perf_counter() - started:.3f} 秒",
            )
            return ImportPreview(
                source_path=prepared.source_path,
                preview_lines=preview_lines,
                unit_lines=unit_lines,
                parameter_lines=prepared.parameter_lines,
                timing_lines=timing_lines,
                available_series_categories=prepared.available_series_categories,
                metadata_mode_text=prepared.metadata_mode_text,
                detected_scheme=prepared.detected_scheme,
                allow_execute=prepared.allow_execute,
            )
        finally:
            _cleanup_temporary_sample_set(sample_set)

    def execute_sample_set_repository(
        self,
        request: SampleSetImportRequest,
        *,
        controller: ImportOperationController | None = None,
    ) -> ImportResult:
        """执行样本集仓库导入。"""

        preview_started = perf_counter()
        prepared = self._prepare_lightweight_sampleset(request, controller=controller)
        sample_set: DefaultSampleSet | None = None
        try:
            _checkpoint(controller)
            _report_phase(
                controller,
                "load_sampleset",
                "加载样本集",
                progress_prefix="加载样本集",
                current=0,
                total=max(prepared.sample_count, 1),
                detail=f"加载方式：{_LOAD_MODE_LABELS[request.load_mode]}",
            )
            sample_set = _load_sampleset_runtime(
                source_path=prepared.source_path,
                sample_domain=prepared.domain_inspection.sample_domain,
                request=request,
                controller=controller,
                load_mode=request.load_mode,
                phase_code="load_sampleset",
                phase_label="加载样本集",
                progress_prefix="加载样本集",
            )
            summary = _build_sample_set_summary(
                sample_set,
                name=f"主样本集 / {prepared.source_path.stem}",
                storage_binding=f"{prepared.detected_scheme} / 已加载",
                storage_dirty=bool(getattr(sample_set, "storage_dirty", False)),
            )
            _report_phase(
                controller,
                "commit_primary",
                "写回主集",
                progress_prefix="写回主集",
                current=1,
                total=1,
                detail="刷新主样本集摘要。",
            )
            warning_lines = [line for line in prepared.preview_lines if line.startswith("警告：")]
            return ImportResult(
                primary_summary=summary,
                recent_lines=(
                    f"最近导入：样本集仓库 {prepared.source_path.name}",
                    f"存储方式：{_format_scheme(prepared.scheme)}",
                    f"样本数量：{summary.sample_count}",
                    warning_lines[0] if warning_lines else "警告：无",
                ),
                success_message=f"已从 {prepared.source_path.name} 加载当前主集。",
                task_title="导入样本集",
                preview_lines=prepared.preview_lines + _sample_set_summary_lines(sample_set),
                unit_lines=(),
                parameter_lines=prepared.parameter_lines,
                timing_lines=(
                    f"轻量检查耗时：{prepared.light_seconds:.3f} 秒",
                    f"执行导入耗时：{perf_counter() - preview_started:.3f} 秒",
                ),
                cleanup_message="已建立当前主集的运行态对象。",
                detected_scheme=prepared.detected_scheme,
                primary_runtime=sample_set,
            )
        finally:
            _cleanup_temporary_sample_set(prepared.sample_set)
            if sample_set is prepared.sample_set:
                _cleanup_temporary_sample_set(sample_set)

    def execute_sample_set_repository_from_preview(
        self,
        request: SampleSetImportRequest,
        preview: ImportPreview,
        *,
        controller: ImportOperationController | None = None,
    ) -> ImportResult:
        """复用轻量预览阶段保留的运行态绑定当前主样本集。"""

        sample_set = preview.prepared_runtime
        if sample_set is None:
            return self.execute_sample_set_repository(request, controller=controller)
        if not _is_sample_set_runtime(sample_set):
            raise ValueError("轻量预览缓存无效，请重新执行预览。")
        started = perf_counter()
        _checkpoint(controller)
        _report_phase(
            controller,
            "commit_primary",
            "写回主集",
            progress_prefix="写回主集",
            current=1,
            total=1,
            detail="复用轻量预览结果刷新主样本集摘要。",
        )
        summary = _build_sample_set_summary(
            sample_set,
            name=f"主样本集 / {preview.source_path.stem}",
            storage_binding=f"{preview.detected_scheme} / 已加载",
            storage_dirty=bool(getattr(sample_set, "storage_dirty", False)),
        )
        warning_lines = [line for line in preview.preview_lines if line.startswith("警告：")]
        return ImportResult(
            primary_summary=summary,
            recent_lines=(
                f"最近导入：样本集仓库 {preview.source_path.name}",
                f"存储方式：{preview.detected_scheme or '-'}",
                f"样本数量：{summary.sample_count}",
                warning_lines[0] if warning_lines else "警告：无",
            ),
            success_message=f"已复用轻量预览结果绑定 {preview.source_path.name}。",
            task_title="导入样本集",
            preview_lines=preview.preview_lines + _sample_set_summary_lines(sample_set),
            unit_lines=preview.unit_lines,
            parameter_lines=preview.parameter_lines,
            timing_lines=preview.timing_lines + (f"绑定主集耗时：{perf_counter() - started:.3f} 秒",),
            cleanup_message="已复用轻量预览阶段的运行态对象。",
            detected_scheme=preview.detected_scheme,
            primary_runtime=sample_set,
        )

    def _prepare_lightweight_sampleset(
        self,
        request: SampleSetImportRequest,
        *,
        controller: ImportOperationController | None = None,
    ) -> "_PreparedSampleSetPreview":
        source_path = request.source_path.resolve()
        started = perf_counter()
        scheme = self._resolve_sample_set_scheme(source_path, request.requested_scheme)
        _checkpoint(controller)
        _report_phase(
            controller,
            "inspect_repository",
            "检查仓库",
            progress_prefix="检查仓库",
            current=1,
            total=4,
            detail=str(source_path),
        )
        report = dt_storage.inspect_storage_repository(
            source_path,
            storage_scheme=scheme if request.requested_scheme is not None else None,
            level="quick",
        )
        preview_lines = [
            f"来源路径：{source_path}",
            f"请求存储方式：{_format_scheme(request.requested_scheme)}",
            f"识别存储方式：{_format_scheme(report.detected_scheme)}",
            f"仓库检查：{'通过' if report.is_valid else '失败'}",
            f"样本数量：{report.sample_count if report.sample_count is not None else '-'}",
            f"警告：{' | '.join(report.warnings) if report.warnings else '无'}",
            f"问题：{' | '.join(report.issues) if report.issues else '无'}",
        ]
        parameter_lines = (
            f"存储方式：{_format_scheme(scheme)}",
            f"加载方式：{_LOAD_MODE_LABELS[request.load_mode]}",
            f"并行任务数：{request.workers}",
            f"严格校验：{'开启' if request.strict else '关闭'}",
        )
        if not report.is_valid:
            return _PreparedSampleSetPreview(
                source_path=source_path,
                scheme=scheme,
                detected_scheme=scheme.value,
                sample_count=report.sample_count or 0,
                preview_lines=tuple(preview_lines),
                parameter_lines=parameter_lines,
                metadata_mode_text="-",
                available_series_categories=(),
                domain_inspection=_SampleSetDomainInspection(sample_domain=None, schema_names=()),
                sample_set=DefaultSampleSet.from_samples(None),
                allow_execute=False,
                light_seconds=perf_counter() - started,
            )

        _checkpoint(controller)
        _report_phase(
            controller,
            "infer_domain",
            "推断样本领域",
            progress_prefix="推断样本领域",
            current=2,
            total=4,
            detail="根据元数据模式自动推断。",
        )
        domain_inspection = _inspect_sample_set_domain(source_path, scheme)
        preview_lines.append(
            f"元数据模式：{', '.join(domain_inspection.schema_names) if domain_inspection.schema_names else '-'}"
        )
        if domain_inspection.error_message:
            preview_lines.append(f"样本领域错误：{domain_inspection.error_message}")
            return _PreparedSampleSetPreview(
                source_path=source_path,
                scheme=scheme,
                detected_scheme=scheme.value,
                sample_count=report.sample_count or 0,
                preview_lines=tuple(preview_lines),
                parameter_lines=parameter_lines,
                metadata_mode_text=", ".join(domain_inspection.schema_names) if domain_inspection.schema_names else "-",
                available_series_categories=(),
                domain_inspection=domain_inspection,
                sample_set=DefaultSampleSet.from_samples(None),
                allow_execute=False,
                light_seconds=perf_counter() - started,
            )

        preview_lines.append(f"样本领域：{domain_inspection.sample_domain.value}")
        _checkpoint(controller)
        _report_phase(
            controller,
            "light_preview",
            "轻量检查",
            progress_prefix="轻量检查",
            current=3,
            total=4,
            detail="仅读取索引、元数据和存在性信息。",
        )
        sample_set = _load_sampleset_runtime(
            source_path=source_path,
            sample_domain=domain_inspection.sample_domain,
            request=request,
            controller=controller,
            load_mode=SampleLoadMode.LAZY,
            phase_code="light_preview",
            phase_label="轻量检查",
            progress_prefix="轻量检查",
        )
        available_series_categories = _available_series_categories(sample_set)
        preview_lines.append(
            f"已声明数据分类：{'、'.join(_category_label(name) for name in available_series_categories) if available_series_categories else '无'}"
        )
        _report_phase(
            controller,
            "build_summary",
            "整理预览摘要",
            progress_prefix="整理预览摘要",
            current=4,
            total=4,
            detail="生成主样本集基础信息。",
        )
        return _PreparedSampleSetPreview(
            source_path=source_path,
            scheme=scheme,
            detected_scheme=scheme.value,
            sample_count=report.sample_count or len(sample_set),
            preview_lines=tuple(preview_lines),
            parameter_lines=parameter_lines,
            metadata_mode_text=", ".join(domain_inspection.schema_names),
            available_series_categories=available_series_categories,
            domain_inspection=domain_inspection,
            sample_set=sample_set,
            allow_execute=True,
            light_seconds=perf_counter() - started,
        )

    def restore_runtime(
        self,
        source_path: Path,
        *,
        requested_scheme: StorageScheme | None = None,
        load_mode: SampleLoadMode = SampleLoadMode.LAZY,
        strict: bool = True,
        workers: int = 1,
    ) -> DefaultSampleSet:
        """从来源路径恢复运行时样本集对象。

        处理/绘图/导出页在 ``primary_runtime`` 缺失时统一调用此方法。
        """

        resolved = source_path.resolve()
        scheme = self._resolve_sample_set_scheme(resolved, requested_scheme)
        domain_inspection = _inspect_sample_set_domain(resolved, scheme)
        return _load_sampleset_runtime(
            source_path=resolved,
            sample_domain=domain_inspection.sample_domain,
            request=SampleSetImportRequest(
                source_path=resolved,
                requested_scheme=scheme,
                load_mode=load_mode,
                workers=workers,
                strict=strict,
            ),
            controller=None,
            load_mode=load_mode,
            phase_code="restore_runtime",
            phase_label="恢复运行时",
            progress_prefix="恢复运行时",
        )

    def _resolve_sample_set_scheme(self, source_path: Path, requested_scheme: StorageScheme | None) -> StorageScheme:
        if requested_scheme is StorageScheme.SET_SQLITE_H5 and source_path.is_file():
            if source_path.name.lower() == "payload.h5":
                raise ValueError("路径不是仓库根目录。请选择包含 index.sqlite 与 payload.h5 的目录。")
        if requested_scheme is None:
            return dt_storage.detect_storage_scheme(source_path, kind="sample_set")
        if requested_scheme is StorageScheme.SET_SQLITE_H5 and not source_path.is_dir():
            raise ValueError("SET_SQLITE_H5 必须选择仓库目录。请选择包含 index.sqlite 与 payload.h5 的目录。")
        return requested_scheme


@dataclass(slots=True)
class _PreparedSampleSetPreview:
    """样本集轻量预览的中间结果。"""

    source_path: Path
    scheme: StorageScheme
    detected_scheme: str
    sample_count: int
    preview_lines: tuple[str, ...]
    parameter_lines: tuple[str, ...]
    metadata_mode_text: str
    available_series_categories: tuple[str, ...]
    domain_inspection: _SampleSetDomainInspection
    sample_set: DefaultSampleSet
    allow_execute: bool
    light_seconds: float


def _resolve_csv_batch_paths(request: SampleBatchImportRequest) -> tuple[Path, ...]:
    if request.source_paths:
        return tuple(path.resolve() for path in request.source_paths)
    if request.source_directory is not None:
        directory = request.source_directory.resolve()
        if directory.is_file():
            return (directory,)
        return tuple(sorted(item.resolve() for item in directory.glob("*.csv")))
    raise ValueError("请先选择一个或多个 CSV 文件，或选择包含 CSV 的目录。")


def _inspect_sample_set_domain(source_path: Path, scheme: StorageScheme) -> _SampleSetDomainInspection:
    schema_names: set[str] = set()
    try:
        for payload in _iter_repository_metadata_payloads(source_path, scheme):
            schema_name = str(payload.get("schema_name", "")).strip()
            if not schema_name:
                return _SampleSetDomainInspection(
                    sample_domain=None,
                    schema_names=tuple(sorted(schema_names)),
                    error_message="仓库中存在缺少 schema_name 的元数据，无法自动推断 sample_domain。",
                )
            schema_names.add(schema_name)
    except Exception as exc:  # noqa: BLE001
        return _SampleSetDomainInspection(
            sample_domain=None,
            schema_names=tuple(sorted(schema_names)),
            error_message=f"元数据模式检查失败：{exc}",
        )

    ordered_schema_names = tuple(sorted(schema_names))
    if not ordered_schema_names:
        return _SampleSetDomainInspection(
            sample_domain=None,
            schema_names=(),
            error_message="当前仓库未检测到元数据模式，无法自动推断 sample_domain。",
        )

    inferred_domains = {
        domain
        for schema_name in ordered_schema_names
        if (domain := _sample_domain_from_schema_name(schema_name)) is not None
    }
    unknown_schema_names = tuple(
        schema_name for schema_name in ordered_schema_names if _sample_domain_from_schema_name(schema_name) is None
    )
    if unknown_schema_names:
        return _SampleSetDomainInspection(
            sample_domain=None,
            schema_names=ordered_schema_names,
            error_message=f"发现未识别的元数据模式：{', '.join(unknown_schema_names)}",
        )
    if len(ordered_schema_names) > 1 or len(inferred_domains) != 1:
        return _SampleSetDomainInspection(
            sample_domain=None,
            schema_names=ordered_schema_names,
            error_message=f"仓库包含混合元数据模式：{', '.join(ordered_schema_names)}",
        )

    return _SampleSetDomainInspection(
        sample_domain=next(iter(inferred_domains)),
        schema_names=ordered_schema_names,
    )


def _iter_repository_metadata_payloads(source_path: Path, scheme: StorageScheme) -> Iterator[dict[str, Any]]:
    if scheme is StorageScheme.SET_SQLITE_H5:
        yield from _iter_sqlite_h5_metadata_payloads(source_path)
        return
    if scheme is StorageScheme.SET_H5:
        yield from _iter_set_h5_metadata_payloads(source_path)
        return
    if scheme is StorageScheme.SET_DIR:
        yield from _iter_set_dir_metadata_payloads(source_path)
        return
    if scheme is StorageScheme.SET_ATTR_TABLE:
        yield from _iter_attr_table_metadata_payloads(source_path)
        return
    raise ValueError(f"当前导入工作流不支持该样本集仓库类型：{scheme.value}")


def _iter_sqlite_h5_metadata_payloads(source_path: Path) -> Iterator[dict[str, Any]]:
    index_path = source_path / DEFAULT_SQLITE_INDEX_FILENAME
    conn = sqlite3.connect(index_path)
    try:
        rows = conn.execute("SELECT metadata_json FROM sample ORDER BY sample_id").fetchall()
    finally:
        conn.close()
    for row in rows:
        yield _metadata_payload_from_json_text(str(row[0]))


def _iter_set_h5_metadata_payloads(source_path: Path) -> Iterator[dict[str, Any]]:
    import h5py

    with h5py.File(source_path, "r") as h5_file:
        for key in h5_file.keys():
            node = h5_file[key]
            if not isinstance(node, h5py.Group):
                continue
            metadata_json = node.attrs.get(H5_ATTR_METADATA_JSON, "{}")
            yield _metadata_payload_from_json_text(_decode_h5_attr_text(metadata_json))


def _iter_set_dir_metadata_payloads(source_path: Path) -> Iterator[dict[str, Any]]:
    for child in sorted(source_path.iterdir()):
        if not child.is_dir():
            continue
        metadata_path = child / METADATA_JSON_FILENAME
        if not metadata_path.exists():
            continue
        payload = json.loads(metadata_path.read_text(encoding="utf-8"))
        metadata_payload = payload.get("metadata", payload)
        if not isinstance(metadata_payload, dict):
            raise ValueError(f"metadata.json 结构无效：{metadata_path}")
        yield metadata_payload


def _iter_attr_table_metadata_payloads(source_path: Path) -> Iterator[dict[str, Any]]:
    metadata_table_path = source_path / METADATA_TABLE_FILENAME
    with metadata_table_path.open(encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        for row in reader:
            metadata_json = row.get(META_COL_METADATA_JSON)
            if metadata_json is None:
                raise ValueError(f"{METADATA_TABLE_FILENAME} 缺少 {META_COL_METADATA_JSON} 列")
            yield _metadata_payload_from_json_text(metadata_json)


def _metadata_payload_from_json_text(raw_text: str) -> dict[str, Any]:
    payload = json.loads(raw_text)
    if not isinstance(payload, dict):
        raise ValueError("metadata_json 不是对象结构")
    return payload


def _decode_h5_attr_text(raw_value: object) -> str:
    if isinstance(raw_value, bytes):
        return raw_value.decode("utf-8")
    return str(raw_value)


def _sample_domain_from_schema_name(schema_name: str) -> SampleDomain | None:
    mapping = {
        "generic_metadata": SampleDomain.DEFAULT,
        "vibration_test_metadata": SampleDomain.VIBRATION_TEST,
    }
    return mapping.get(schema_name)


def _load_sampleset_runtime(
    *,
    source_path: Path,
    sample_domain: SampleDomain | None,
    request: SampleSetImportRequest,
    controller: ImportOperationController | None,
    load_mode: SampleLoadMode,
    phase_code: str,
    phase_label: str,
    progress_prefix: str,
) -> DefaultSampleSet:
    sample_set = DefaultSampleSet.from_samples(None, sample_domain=sample_domain)
    categories = sample_set._categories_to_fields(None, load_mode=load_mode)
    runtime_categories = [] if load_mode in {SampleLoadMode.METADATA_ONLY, SampleLoadMode.LAZY} else categories
    result = _RUNTIME_BRIDGE.resolve_sample_set_runtime(sample_set, action="load").load_sample_set(
        sample_set,
        path=source_path,
        storage_scheme=request.requested_scheme,
        progress_callback=(
            None
            if controller is None
            else controller.make_storage_progress_callback(
                phase_code=phase_code,
                phase_label=phase_label,
                progress_prefix=progress_prefix,
                detail=str(source_path.name),
            )
        ),
        show_progress=False,
        categories=runtime_categories,
        strict=request.strict,
        workers=request.workers,
    )
    for sample in result.values():
        _RUNTIME_BRIDGE.force_sample_load_mode(sample, load_mode)
    result.storage_dirty = False
    return result


def _available_series_categories(sample_set: object) -> tuple[str, ...]:
    available: list[str] = []
    for category in _SERIES_CATEGORIES:
        if _category_exists_in_sampleset(sample_set, category):
            available.append(category)
    return tuple(available)


def _category_exists_in_sampleset(sample_set: object, category: str) -> bool:
    if not sample_set.sample_schema.has_slot(category):
        return False
    field = sample_set.sample_schema.resolve_field(category)
    for sample in sample_set.values():
        if _RUNTIME_BRIDGE.has_storage_presence(sample, field):
            return True
    return False


def _sample_set_summary_lines(sample_set: object) -> tuple[str, ...]:
    first_sample = next(iter(sample_set.values()), None)
    metadata = getattr(first_sample, "metadata", None)
    supported_categories = "、".join(_normalize_text_tuple(getattr(sample_set, "supported_categories", ()))) or "-"
    supported_fields = "、".join(_normalize_text_tuple(getattr(sample_set, "supported_fields", ()))) or "-"
    sample_domain = _resolve_sample_domain(sample_set)
    loaded_count, unloaded_count = _loaded_unloaded_counts(sample_set)
    return (
        f"对象类型：{type(sample_set).__name__}",
        f"样本类型：{_resolve_sample_type_name(sample_set)}",
        f"样本领域：{sample_domain or '-'}",
        f"元数据类型：{type(metadata).__name__ if metadata is not None else '-'}",
        f"样本数量：{len(sample_set)}",
        f"已加载样本数：{loaded_count}",
        f"未加载样本数：{unloaded_count}",
        f"支持的数据类型：{supported_categories}",
        f"支持的字段：{supported_fields}",
    )


def _loaded_unloaded_counts(sample_set: object) -> tuple[int, int]:
    loaded_count = 0
    for sample in sample_set.values():
        if getattr(sample, "loaded_categories", ()):
            loaded_count += 1
    return loaded_count, max(len(sample_set) - loaded_count, 0)


def _summarize_sample_set_units_deep(
    sample_set: object,
    *,
    available_categories: tuple[str, ...],
    request: SampleSetImportRequest,
    controller: ImportOperationController | None,
) -> tuple[str, ...]:
    lines: list[str] = []
    total_samples = max(len(sample_set), 1)
    for category in _SERIES_CATEGORIES:
        label = _category_label(category)
        if not sample_set.sample_schema.has_slot(category) or category not in available_categories:
            lines.append(f"{label}：未检测到该类原始数据")
            continue
        _checkpoint(controller)
        sample_set.load_all(
            progress_callback=(
                None
                if controller is None
                else controller.make_storage_progress_callback(
                    phase_code=f"deep_units_{category}",
                    phase_label=f"深度检查单位（{label}）",
                    progress_prefix=f"深度检查单位[{label}]",
                    detail=f"正在读取 {label} 原始数据。",
                )
            ),
            show_progress=False,
            categories=[category],
            load_mode=SampleLoadMode.EAGER,
            strict=request.strict,
            workers=request.workers,
        )
        axis_counter: Counter[str] = Counter()
        value_counter: Counter[str] = Counter()
        missing_count = 0
        observed_count = 0
        for sample in sample_set.values():
            model = getattr(sample, category, None)
            if model is None:
                missing_count += 1
                continue
            observed_count += 1
            axis_counter[str(getattr(model, "axis_unit", None) or "-")] += 1
            value_counter[str(getattr(model, "value_unit", None) or "-")] += 1
        status = _unit_status(axis_counter, value_counter, missing_count, total_samples)
        if observed_count == 0:
            lines.append(f"{label}：该分类未检测到可汇总单位")
        else:
            lines.extend(
                (
                    f"{label} 轴单位：{_format_counter(axis_counter)}",
                    f"{label} 数值单位：{_format_counter(value_counter)}",
                    f"{label} 状态：{status}",
                    f"{label} 缺失数量：{missing_count}",
                )
            )
        for sample in sample_set.values():
            sample.unload(categories=[category])
    if not lines:
        return ("当前样本集未检测到可汇总单位的原始数据。",)
    return tuple(lines)


def _unit_status(
    axis_counter: Counter[str],
    value_counter: Counter[str],
    missing_count: int,
    total_samples: int,
) -> str:
    if not axis_counter or not value_counter:
        return "缺失"
    if len(axis_counter) > 1 or len(value_counter) > 1:
        return "混用"
    if "-" in axis_counter or "-" in value_counter or missing_count > 0 or sum(value_counter.values()) < total_samples:
        return "缺失"
    return "一致"


def _summarize_batch_units(items: list[dict[str, str]]) -> tuple[str, ...]:
    if not items:
        return ("当前批次未检测到可汇总单位。",)
    axis_counter: Counter[str] = Counter()
    value_counter: Counter[str] = Counter()
    for unit_map in items:
        axis_counter[str(unit_map.get("axis_unit", "-") or "-")] += 1
        value_counter[str(unit_map.get("value_unit", "-") or "-")] += 1
    return (
        "已检查数据类型：加速度",
        f"加速度 轴单位：{_format_counter(axis_counter)}",
        f"加速度 数值单位：{_format_counter(value_counter)}",
        f"加速度 状态：{_unit_status(axis_counter, value_counter, 0, len(items))}",
    )


def _format_counter(counter: Counter[str]) -> str:
    if not counter:
        return "无"
    return ", ".join(f"{key} x {value}" for key, value in sorted(counter.items()))


def _build_sample_set_summary(
    sample_set: object,
    *,
    name: str,
    storage_binding: str,
    storage_dirty: bool,
) -> SampleSetSummary:
    first_sample = next(iter(sample_set.values()), None)
    metadata = getattr(first_sample, "metadata", None)
    metadata_fields = _resolve_metadata_fields(metadata)
    supported_categories = _normalize_text_tuple(getattr(sample_set, "supported_categories", ()))
    storable_categories = _normalize_text_tuple(getattr(sample_set, "storable_categories", ()))
    supported_fields = _normalize_text_tuple(getattr(sample_set, "supported_fields", ()))
    sample_domain = _resolve_sample_domain(sample_set)
    loaded_count, unloaded_count = _loaded_unloaded_counts(sample_set)
    return SampleSetSummary(
        name=name,
        class_name=type(sample_set).__name__,
        sample_type=_resolve_sample_type_name(sample_set),
        sample_domain=str(sample_domain or "-"),
        metadata_type=type(metadata).__name__ if metadata is not None else "-",
        metadata_fields=metadata_fields,
        supported_categories=supported_categories,
        storable_categories=storable_categories,
        supported_fields=supported_fields,
        sample_count=len(sample_set),
        loaded_count=loaded_count,
        unloaded_count=unloaded_count,
        storage_binding=storage_binding,
        strict=bool(getattr(sample_set, "strict", True)),
        storage_dirty=storage_dirty,
    )


def _resolve_sample_type_name(sample_set: object) -> str:
    first_sample = next(iter(sample_set.values()), None)
    return type(first_sample).__name__ if first_sample is not None else "-"


def _resolve_sample_domain(sample_set: object) -> str:
    sample_domain = getattr(sample_set, "sample_domain", None)
    if sample_domain is None:
        sample_domain = _RUNTIME_BRIDGE.infer_domain_from_sample_set_cls(type(sample_set))
    return str(sample_domain or "-")


def _resolve_metadata_fields(metadata: object | None) -> tuple[str, ...]:
    if metadata is None:
        return ()
    if hasattr(metadata, "model_dump"):
        payload = metadata.model_dump()
        return tuple(str(key) for key in payload.keys())
    if hasattr(metadata, "__dict__"):
        return tuple(str(key) for key in vars(metadata).keys())
    return ()


def _is_sample_set_runtime(value: object) -> bool:
    """判断对象是否具备 GUI 所需的样本集运行态协议。"""

    return all(hasattr(value, attr) for attr in ("values", "items", "__len__"))


def _normalize_text_tuple(items: Any) -> tuple[str, ...]:
    if items is None:
        return ()
    if callable(items):
        items = items()
    return tuple(str(item) for item in items)


def _csv_parameter_lines(csv_read_options: dict[str, Any]) -> tuple[str, ...]:
    return (
        f"分隔符：{csv_read_options.get('sep', ',')}",
        f"表头行：{csv_read_options.get('header')}",
        f"索引列：{csv_read_options.get('index_col')}",
        f"编码：{csv_read_options.get('encoding', 'utf-8')}",
        f"跳过行数：{csv_read_options.get('skiprows', 0)}",
        f"小数点符号：{csv_read_options.get('decimal', '.')}",
    )


def _category_label(category: str) -> str:
    return _CATEGORY_LABELS.get(category, category)


def _format_scheme(scheme: StorageScheme | None) -> str:
    if scheme is None:
        return "自动识别"
    return _SCHEME_LABELS.get(scheme, scheme.value)


def _cleanup_temporary_sample_set(sample_set: DefaultSampleSet | None) -> None:
    if sample_set is None:
        return
    for sample in sample_set.values():
        sample.unload()
    _RUNTIME_BRIDGE.release_sample_set_storage(sample_set)


def _checkpoint(controller: ImportOperationController | None) -> None:
    if controller is not None:
        controller.checkpoint()


def _report_phase(
    controller: ImportOperationController | None,
    phase_code: str,
    phase_label: str,
    *,
    progress_prefix: str,
    current: int | None = None,
    total: int | None = None,
    detail: str = "",
) -> None:
    if controller is None:
        return
    controller.update_phase(
        phase_code,
        phase_label,
        progress_prefix=progress_prefix,
        current=current,
        total=total,
        detail=detail,
    )


__all__ = [
    "GuiImportFacade",
    "ImportKind",
    "ImportPreview",
    "ImportResult",
    "SampleBatchImportRequest",
    "SampleSetImportRequest",
]
