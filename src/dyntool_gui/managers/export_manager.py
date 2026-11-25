"""导出能力协调器。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Any

from PySide6.QtCore import QObject, QThread, Signal, Slot

from .._scope import _ResolvedSampleScope
from ..session import ExportRecord, ProjectSession


@dataclass(slots=True)
class ExportValidationResult:
    """导出前置校验结果。"""

    valid: bool
    missing_requirements: tuple[str, ...]
    pending_generation_action: str
    message: str
    duration_ms: int


@dataclass(slots=True)
class ExportResult:
    """导出结果。"""

    export_kind: str
    output_path: Path
    message: str
    duration_ms: int


@dataclass(slots=True)
class _ExportScopeRuntime:
    """导出命令冻结范围对应的运行态视图。"""

    sample_set: Any
    scoped_uids: tuple[str, ...]
    fallback_slots: tuple[str, ...]

    def export_sample_set(self) -> Any:
        """返回导出实际使用的样本集视图。"""

        return _scoped_sample_set(self.sample_set, list(self.scoped_uids))

    def has_series_frame(self, data_var: str) -> bool:
        """检查当前范围是否能生成指定序列表。"""

        if not self.scoped_uids:
            return False
        if not data_var:
            return True
        if data_var in self.fallback_slots:
            return True
        try:
            frame = self.sample_set.series_frame(data_var, uids=self._uids_or_none(), strict=False)
        except (AttributeError, KeyError, TypeError, ValueError):
            return False
        return not frame.empty

    def has_peaks_frame(self, source: str) -> bool:
        """检查当前范围是否能生成指定峰值表。"""

        if not self.scoped_uids:
            return False
        if not source:
            return True
        if source in self.fallback_slots:
            return True
        try:
            frame = self.sample_set.peaks_frame(source=source, uids=self._uids_or_none(), strict=False)
        except (AttributeError, KeyError, TypeError, ValueError):
            return False
        return not frame.empty

    def _uids_or_none(self) -> tuple[str, ...]:
        return self.scoped_uids


class _ExportWorker(QObject):
    """后台导出 worker。"""

    succeeded = Signal(object)
    failed = Signal(str)
    finished = Signal()

    def __init__(self, manager: "ExportManager", kwargs: dict[str, Any]) -> None:
        super().__init__()
        self._manager = manager
        self._kwargs = kwargs

    @Slot()
    def run(self) -> None:
        try:
            self.succeeded.emit(self._manager.execute_sync(**self._kwargs))
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))
        finally:
            self.finished.emit()


class ExportManager(QObject):
    """当前主样本集导出协调器。"""

    succeeded = Signal(object)
    failed = Signal(str)
    state_changed = Signal()

    def __init__(self, session: ProjectSession, parent: object | None = None) -> None:
        super().__init__(parent)
        self._session = session
        self._thread: QThread | None = None
        self._worker: _ExportWorker | None = None

    @property
    def busy(self) -> bool:
        """返回当前是否有活动导出任务。"""

        return self._thread is not None

    def start(self, **kwargs: Any) -> None:
        """启动后台导出任务。"""

        if self._thread is not None:
            raise ValueError("当前已有导出任务正在运行。")
        self._session.export_state.busy = True
        self._session._upsert_task("导出当前主样本集", "进行中", "0 / 1", "正在执行导出。")
        self._session._prepend_log("INFO", "gui.export", "正在执行导出。")
        self._session.bus.export_state_changed.emit()
        self._session.bus.task_changed.emit()
        self._session.bus.logs_changed.emit()
        self._thread = QThread(self)
        self._worker = _ExportWorker(self, kwargs)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.succeeded.connect(self.succeeded.emit)
        self._worker.failed.connect(self.failed.emit)
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.finished.connect(self._cleanup)
        self._thread.start()
        self.state_changed.emit()

    def validate_sync(
        self,
        *,
        export_kind: str,
        output_path: str | Path,
        data_var: str,
        source: str,
        scoped_uids: tuple[str, ...] | None = None,
    ) -> ExportValidationResult:
        """同步校验导出前置条件。"""

        sample_set = self._require_runtime()
        export_scope = _ExportScopeRuntime(
            sample_set,
            _ResolvedSampleScope.resolve(self._session, scoped_uids).uids,
            self._session.capability_snapshot.data_slots,
        )
        started = perf_counter()
        missing: list[str] = []
        if not export_scope.scoped_uids:
            missing.append("当前范围没有可导出样本")
        pending_generation_action = ""

        target_text = str(output_path).strip()
        if not target_text:
            missing.append("输出路径不能为空")

        if export_kind == "series_frame" and not export_scope.has_series_frame(data_var):
            missing.append(f"缺少序列表来源：{data_var}")
            pending_generation_action = _required_action(data_var)
        elif export_kind == "peaks_frame" and not export_scope.has_peaks_frame(source):
            missing.append(f"缺少峰值来源：{source}")
            pending_generation_action = _required_action(source)
        elif export_kind == "report_package":
            if not export_scope.has_series_frame(data_var):
                missing.append(f"缺少序列表来源：{data_var}")
                pending_generation_action = _required_action(data_var)
            if not export_scope.has_peaks_frame(source):
                missing.append(f"缺少峰值来源：{source}")
                pending_generation_action = pending_generation_action or _required_action(source)

        duration_ms = int((perf_counter() - started) * 1000)
        valid = not missing
        message = "导出前置校验通过。" if valid else "导出前置校验未通过。"
        state = self._session.export_state
        state.validated = valid
        state.missing_requirements = tuple(missing)
        state.pending_generation_action = pending_generation_action
        state.output_path = target_text
        state.last_duration_ms = duration_ms
        state.missing_reason = "" if valid else "；".join(missing)
        state.last_failure_message = ""
        self._session.bus.export_state_changed.emit()
        return ExportValidationResult(
            valid=valid,
            missing_requirements=tuple(missing),
            pending_generation_action=pending_generation_action,
            message=message,
            duration_ms=duration_ms,
        )

    def execute_sync(
        self,
        *,
        export_kind: str,
        output_path: str | Path,
        format_name: str,
        metadata_fields: tuple[str, ...],
        features: tuple[str, ...],
        data_var: str,
        source: str,
        include_plots: bool,
        include_eval_summary: bool,
        scoped_uids: tuple[str, ...] | None = None,
    ) -> ExportResult:
        """同步执行导出动作。"""

        scoped_uids = _ResolvedSampleScope.resolve(self._session, scoped_uids).uids
        validation = self.validate_sync(
            export_kind=export_kind,
            output_path=output_path,
            data_var=data_var,
            source=source,
            scoped_uids=scoped_uids,
        )
        if not validation.valid:
            raise ValueError("；".join(validation.missing_requirements))

        export_scope = _ExportScopeRuntime(
            self._require_runtime(),
            scoped_uids,
            self._session.capability_snapshot.data_slots,
        )
        sample_set = export_scope.export_sample_set()
        started = perf_counter()
        target_path: Path
        if export_kind == "scalar_frame":
            target_path = sample_set.export_scalar_frame(
                output_path,
                features=features or ("max",),
                format=format_name,
                metadata_fields=metadata_fields or None,
            )
        elif export_kind == "series_frame":
            target_path = sample_set.export_series_frame(
                output_path,
                data_var=data_var,
                metadata_fields=metadata_fields or None,
                format=format_name,
            )
        elif export_kind == "peaks_frame":
            target_path = sample_set.export_peaks_frame(
                output_path,
                source=source,
                metadata_fields=metadata_fields or None,
                format=format_name,
            )
        elif export_kind == "report_package":
            target_path = sample_set.export_report_package(
                output_path,
                features=features or None,
                series_vars=(data_var,) if data_var else (),
                peak_sources=(source,) if source else (),
                include_plots=include_plots,
                include_eval_summary=include_eval_summary,
            )
        else:
            raise ValueError(f"不支持的导出类型：{export_kind}")

        duration_ms = int((perf_counter() - started) * 1000)
        message = f"已导出：{export_kind}"
        self._session.exports.insert(0, ExportRecord(export_kind, str(target_path), "成功", _now_text()))
        state = self._session.export_state
        state.last_duration_ms = duration_ms
        state.last_failure_message = ""
        self._session.set_export_message(message=message, output_path=str(target_path))
        self._session._upsert_task("导出当前主样本集", "已完成", "1 / 1", message)
        self._session._prepend_log("INFO", "gui.export", f"{message} -> {target_path}，耗时={duration_ms} ms")
        self._session.bus.task_changed.emit()
        self._session.bus.logs_changed.emit()
        self._session.bus.project_changed.emit()
        return ExportResult(
            export_kind=export_kind,
            output_path=Path(target_path),
            message=message,
            duration_ms=duration_ms,
        )

    @Slot()
    def _cleanup(self) -> None:
        self._session.export_state.busy = False
        self._session.bus.export_state_changed.emit()
        self._thread = None
        self._worker = None
        self.state_changed.emit()

    def _require_runtime(self) -> object:
        sample_set = self._session.primary_runtime
        if sample_set is None:
            raise ValueError("当前没有可导出的主样本集。")
        return sample_set


def _required_action(name: str) -> str:
    return {
        "freqspec": "calc_freqspec",
        "respspec": "calc_respspec",
        "zvl": "eval_zvl",
        "otovl": "eval_otovl",
        "fdmvl": "eval_fdmvl",
        "fpvdv": "eval_fpvdv",
    }.get(name, "")


def _now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _scoped_sample_set(sample_set: Any, scoped_uids: list[str]) -> Any:
    if not scoped_uids:
        raise ValueError("当前范围没有可导出样本。")
    keys = getattr(sample_set, "keys", None)
    if callable(keys) and set(scoped_uids) == {str(uid) for uid in keys()}:
        return sample_set
    finder = getattr(sample_set, "find_many", None)
    if callable(finder):
        return finder(uids=tuple(scoped_uids))
    selected = {uid: sample for uid, sample in sample_set.items() if str(uid) in set(scoped_uids)}
    return type(sample_set)(selected)
