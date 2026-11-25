"""分析数据保存任务及主线程状态收口。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QObject, QThread, Signal, Slot

from dyntool import BatchOperationReport, DefaultSampleSet, StorageScheme
import dyntool.storage as dt_storage

from .._session_types import build_capability_snapshot, now_text, summarize_runtime_sample_set
from ..session import ProjectSession


@dataclass(frozen=True, slots=True)
class AnalysisSaveResult:
    """保存事实与核心逐样本报告。"""

    path: Path
    total: int
    report: BatchOperationReport[object] | None
    error: str = ""

    @property
    def complete(self) -> bool:
        """返回本次是否已成功提交全部样本。"""

        return (
            not self.error
            and self.report is not None
            and self.report.stats.failed == 0
            and self.report.stats.succeeded == self.total
        )

    @property
    def detail(self) -> str:
        """生成准确的保存数量与错误说明。"""

        succeeded = 0 if self.report is None else self.report.stats.succeeded
        failed = 0 if self.report is None else self.report.stats.failed
        attempted = 0 if self.report is None else self.report.stats.total
        detail = f"成功 {succeeded}，失败 {failed}，未执行 {self.total - attempted}。"
        if failed and self.report is not None:
            failures = [
                f"{uid}: {item.message}" for uid, item in self.report.results.items() if item.status == "failed"
            ]
            detail = f"{detail} {'；'.join(failures[:3])}"
        if self.error:
            return f"{detail} {self.error}"
        return detail


@dataclass(frozen=True, slots=True)
class _AnalysisSaveJob:
    """只在后台执行核心 I/O，不修改 Qt 会话或界面。"""

    runtime: DefaultSampleSet
    target: Path
    strict: bool

    def execute(self, progress: Callable[[int, int], None]) -> AnalysisSaveResult:
        """保存完整主集，捕获失败并保留真实提交报告。"""

        previous_report = self.runtime.last_operation_report
        error = ""
        try:
            dt_storage.save_sample_set(
                self.runtime,
                self.target,
                scheme=StorageScheme.SET_SQLITE_H5,
                strict=self.strict,
                workers=1,
                progress_callback=progress,
                show_progress=False,
            )
        except Exception as exc:  # noqa: BLE001
            error = str(exc)
        report = self.runtime.last_operation_report
        if report is previous_report:
            report = None
        result = AnalysisSaveResult(self.target, len(self.runtime), report, error)
        if not result.complete:
            self.runtime.storage_dirty = True
        return result


class _AnalysisSaveWorker(QObject):
    """将保存结果送回主线程。"""

    progress = Signal(int, int)
    completed = Signal(object)
    finished = Signal()

    def __init__(self, job: _AnalysisSaveJob) -> None:
        super().__init__()
        self._job = job

    @Slot()
    def run(self) -> None:
        """执行任务并保证线程收到退出通知。"""

        try:
            self.completed.emit(self._job.execute(self.progress.emit))
        finally:
            self.finished.emit()


class AnalysisSaveManager(QObject):
    """管理保存线程，并在主线程更新项目引用和反馈。"""

    completed = Signal(object)
    state_changed = Signal()

    def __init__(self, session: ProjectSession, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._session = session
        self._thread: QThread | None = None
        self._worker: _AnalysisSaveWorker | None = None
        self._result_received = False

    @property
    def busy(self) -> bool:
        """返回保存任务或线程收尾是否仍在进行。"""

        return self._thread is not None

    def start(self, target: Path, *, strict: bool | None = None) -> None:
        """保存全部主集数据，首次目标不得覆盖无关仓库。"""

        if self.busy:
            raise ValueError("分析数据保存任务正在进行或收尾，请等待完成。")
        runtime = self._session.primary_runtime
        if runtime is None or not len(runtime):
            raise ValueError("当前没有可保存的主样本集，请先导入数据。")
        target = target.resolve()
        source = self._session.import_state.source_path
        if source is not None and target == source.resolve():
            raise ValueError("分析数据须另存到独立目录，不能覆盖原始导入来源。")
        state = self._session.analysis_data
        binding = runtime.storage
        if target not in (state.path, state.retry_path) and binding is not None:
            if target == Path(binding.base_dir).resolve():
                raise ValueError("分析数据须另存到独立目录，不能覆盖原始运行态仓库。")
        if target not in (state.path, state.retry_path) and target.exists() and any(target.iterdir()):
            raise ValueError("首次保存请选择空目录，不能合并或覆盖其他项目的数据仓库。")
        state.retry_path = target
        state.last_error = ""
        self._result_received = False
        self._session._upsert_task("保存分析数据", "运行中", f"0 / {len(runtime)}", str(target))
        self._session.bus.task_changed.emit()
        self._thread = QThread(self)
        self._worker = _AnalysisSaveWorker(
            _AnalysisSaveJob(runtime, target, self._session.import_state.strict if strict is None else strict)
        )
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._handle_progress)
        self._worker.completed.connect(self._handle_result)
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.finished.connect(self._cleanup)
        self._thread.start()
        self.state_changed.emit()

    @Slot(int, int)
    def _handle_progress(self, current: int, total: int) -> None:
        if self._result_received:
            return
        self._session._upsert_task("保存分析数据", "运行中", f"{current} / {total}", "逐样本提交中。")
        self._session.bus.task_changed.emit()
        self.state_changed.emit()

    @Slot(object)
    def _handle_result(self, result: AnalysisSaveResult) -> None:
        self._result_received = True
        session = self._session
        state = session.analysis_data
        state.last_report = result.report
        state.last_error = "" if result.complete else result.detail
        if result.complete:
            state.path = result.path
            state.retry_path = None
            state.last_saved = now_text()
            session.dirty = True
        runtime = session.primary_runtime
        session.primary_sampleset = summarize_runtime_sample_set(
            runtime,
            name=session.primary_sampleset.name,
            storage_binding="SET_SQLITE_H5 / read_write",
        )
        session.capability_snapshot = build_capability_snapshot(runtime)
        succeeded = 0 if result.report is None else result.report.stats.succeeded
        session._upsert_task(
            "保存分析数据",
            "已完成" if result.complete else "保存未完成",
            f"{succeeded} / {result.total}",
            result.detail,
        )
        session._prepend_log("INFO" if result.complete else "ERROR", "gui.storage", result.detail)
        if not result.complete:
            session._prepend_issue("失败", "保存分析数据", result.detail)
            session.bus.issues_changed.emit()
        session.bus.primary_changed.emit()
        session.bus.project_changed.emit()
        session.bus.task_changed.emit()
        session.bus.logs_changed.emit()
        self.completed.emit(result)
        self.state_changed.emit()

    @Slot()
    def _cleanup(self) -> None:
        self._thread = None
        self._worker = None
        self.state_changed.emit()
