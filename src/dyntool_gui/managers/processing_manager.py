"""分析页协调器。"""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any, Callable

import numpy as np
from PySide6.QtCore import QObject, QThread, Signal, Slot
from dyntool.compute.solvers import SDOFSolveMethod, WeightType
from dyntool.compute.units import UnitSystem

from .._session_types import CapabilitySnapshot, build_capability_snapshot, summarize_runtime_sample_set
from ..session import ProcessingRequestSnapshot, ProjectSession, resolve_scope_uids


@dataclass(slots=True)
class ProcessingResult:
    """处理动作结果。"""

    action_name: str
    message: str
    affected_count: int
    duration_ms: int
    skipped_count: int = 0


@dataclass(slots=True)
class ProcessingPreviewResult:
    """处理预览结果。"""

    preview_kind: str
    preview_scope: str
    preview_title: str
    message: str
    scalar_rows: tuple[tuple[str, ...], ...]
    series_rows: tuple[tuple[str, ...], ...]
    peaks_rows: tuple[tuple[str, ...], ...]
    duration_ms: int


@dataclass(frozen=True, slots=True)
class ProcessingProgressUpdate:
    """处理任务进度更新。"""

    title: str
    current: int
    total: int
    detail: str


class ProcessingCancelledError(RuntimeError):
    """处理任务被用户中止。"""


@dataclass(frozen=True, slots=True)
class _ProcessingActionRequirement:
    """处理动作的数据前置要求。"""

    source_slot: str
    source_label: str


@dataclass(frozen=True, slots=True)
class _ProcessingExecutionPlan:
    """处理动作执行范围。"""

    target_uids: tuple[str, ...]
    runnable_uids: tuple[str, ...]
    skipped_uids: tuple[str, ...]
    requirement: _ProcessingActionRequirement | None

    @classmethod
    def build(
        cls,
        sample_set: object,
        target_uids: tuple[str, ...],
        requirement: _ProcessingActionRequirement | None,
    ) -> "_ProcessingExecutionPlan":
        """根据动作前置要求划分可执行与跳过样本。"""

        if requirement is None or not target_uids:
            return cls(target_uids, target_uids, (), requirement)
        getter = getattr(sample_set, "get", None)
        if not callable(getter):
            return cls(target_uids, target_uids, (), requirement)

        runnable: list[str] = []
        skipped: list[str] = []
        for uid in target_uids:
            sample = getter(uid)
            if cls._sample_has_required_source(sample, requirement.source_slot):
                runnable.append(uid)
            else:
                skipped.append(uid)
        return cls(target_uids, tuple(runnable), tuple(skipped), requirement)

    @property
    def skipped_count(self) -> int:
        """返回跳过样本数量。"""

        return len(self.skipped_uids)

    @property
    def total_count(self) -> int:
        """返回原始目标样本数量。"""

        return len(self.target_uids)

    @staticmethod
    def _sample_has_required_source(sample: object | None, source_slot: str) -> bool:
        if sample is None:
            return True
        schema = getattr(sample, "sample_schema", None)
        field = None
        resolve_field = getattr(schema, "resolve_field", None)
        if callable(resolve_field):
            try:
                field = resolve_field(source_slot)
            except Exception:  # noqa: BLE001
                field = None
        presence = getattr(sample, "_storage_presence", None)
        if field is not None and isinstance(presence, dict) and presence.get(field) is False:
            return False
        getter = getattr(sample, "get_data_var", None)
        try:
            if callable(getter):
                return getter(source_slot) is not None
            return getattr(sample, source_slot, None) is not None
        except Exception:  # noqa: BLE001
            return False


_ACTION_REQUIREMENTS: dict[str, _ProcessingActionRequirement] = {
    "calc_vel": _ProcessingActionRequirement("accel", "加速度"),
    "calc_disp": _ProcessingActionRequirement("accel", "加速度"),
    "calc_freqspec": _ProcessingActionRequirement("accel", "加速度"),
    "calc_respspec": _ProcessingActionRequirement("accel", "加速度"),
    "eval_zvl": _ProcessingActionRequirement("accel", "加速度"),
    "eval_otovl": _ProcessingActionRequirement("accel", "加速度"),
    "eval_fdmvl": _ProcessingActionRequirement("accel", "加速度"),
    "eval_fpvdv": _ProcessingActionRequirement("accel", "加速度"),
}

_ACTION_OUTPUT_SLOTS: dict[str, str] = {
    "calc_vel": "vel",
    "calc_disp": "disp",
    "calc_freqspec": "freqspec",
    "calc_respspec": "respspec",
    "eval_zvl": "zvl",
    "eval_otovl": "otovl",
    "eval_fdmvl": "fdmvl",
    "eval_fpvdv": "fpvdv",
}


class ProcessingTaskController:
    """处理任务控制器，用于进度上报与安全中止。"""

    def __init__(self) -> None:
        self._cancel_requested = False
        self._progress_reporter: Callable[[ProcessingProgressUpdate], None] | None = None

    def set_progress_reporter(self, reporter: Callable[[ProcessingProgressUpdate], None]) -> None:
        """设置进度上报回调。"""

        self._progress_reporter = reporter

    def request_cancel(self) -> None:
        """请求在下一个安全检查点中止。"""

        self._cancel_requested = True

    @property
    def cancel_requested(self) -> bool:
        """返回是否已经请求中止。"""

        return self._cancel_requested

    def checkpoint(self) -> None:
        """检查是否已经收到中止请求。"""

        if self._cancel_requested:
            raise ProcessingCancelledError("已中止当前处理任务。")

    def report(self, *, title: str, current: int, total: int, detail: str) -> None:
        """上报当前处理进度。"""

        if self._progress_reporter is not None:
            self._progress_reporter(ProcessingProgressUpdate(title, current, total, detail))


class _ProcessingWorker(QObject):
    """后台处理 worker。"""

    succeeded = Signal(object)
    failed = Signal(str)
    cancelled = Signal(str)
    progress = Signal(object)
    finished = Signal()

    def __init__(
        self, runner: Callable[[ProcessingTaskController], object], controller: ProcessingTaskController
    ) -> None:
        super().__init__()
        self._runner = runner
        self._controller = controller
        self._controller.set_progress_reporter(self.progress.emit)

    @Slot()
    def run(self) -> None:
        try:
            self.succeeded.emit(self._runner(self._controller))
        except ProcessingCancelledError as exc:
            self.cancelled.emit(str(exc))
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))
        finally:
            self.finished.emit()


class ProcessingManager(QObject):
    """当前主样本集分析协调器。"""

    succeeded = Signal(object)
    failed = Signal(str)
    state_changed = Signal()

    def __init__(self, session: ProjectSession, parent: object | None = None) -> None:
        super().__init__(parent)
        self._session = session
        self._thread: QThread | None = None
        self._worker: _ProcessingWorker | None = None
        self._controller: ProcessingTaskController | None = None

    @property
    def busy(self) -> bool:
        """返回当前是否有活动处理任务。"""

        return self._thread is not None

    def start_action(self, **kwargs: Any) -> None:
        """启动后台处理动作。"""

        self._start(
            lambda controller: self.execute_sync(**kwargs, controller=controller),
            task_title="处理当前主样本集",
            detail="正在执行处理动作。",
        )

    def start_preview(self, **kwargs: Any) -> None:
        """启动后台预览构建。"""

        self._start(
            lambda controller: self.build_preview_sync(**kwargs, controller=controller),
            task_title="生成处理预览表",
            detail="正在生成处理结果预览。",
        )

    def request_cancel(self) -> None:
        """请求中止当前处理任务。"""

        if self._controller is None or not self._session.processing_state.busy:
            return
        if self._session.processing_state.cancel_requested:
            return
        self._controller.request_cancel()
        self._session.processing_state.cancel_requested = True
        self._session.processing_state.last_message = "已请求中止，等待安全检查点。"
        self._session._upsert_task("处理当前主样本集", "正在中止", "等待安全检查点", "已请求中止当前处理任务。")
        self._session._prepend_log("WARNING", "gui.processing", "已请求中止当前处理任务，正在等待安全检查点。")
        self._session.bus.processing_state_changed.emit()
        self._session.bus.task_changed.emit()
        self._session.bus.logs_changed.emit()
        self.state_changed.emit()

    def execute_sync(
        self,
        *,
        request: ProcessingRequestSnapshot | None = None,
        action_name: str | None = None,
        uids_text: str = "",
        strict: bool = True,
        overwrite: bool = True,
        action_params: dict[str, str] | None = None,
        controller: ProcessingTaskController | None = None,
    ) -> ProcessingResult:
        """同步执行处理动作。"""

        if controller is not None:
            controller.checkpoint()
        sample_set = self._require_runtime()
        request = request or ProcessingRequestSnapshot(
            action_name=action_name or "",
            uids_text=uids_text,
            strict=strict,
            overwrite=overwrite,
            action_params=dict(action_params or {}),
        )
        resolved_uids = (
            list(request.resolved_uids)
            if request.resolved_uids
            else resolve_scope_uids(self._session, request.uids_text)
        )
        if controller is not None:
            controller.checkpoint()
        action = getattr(sample_set, request.action_name, None)
        if not callable(action):
            raise ValueError(f"当前主样本集不支持处理动作：{request.action_name}")

        if resolved_uids:
            target_uids = tuple(resolved_uids)
        else:
            keys = getattr(sample_set, "keys", None)
            if not callable(keys):
                raise ValueError("当前主样本集无法枚举 UID，GUI 不能启动不可中止的全量写任务。")
            target_uids = tuple(str(uid) for uid in keys())
        if not target_uids:
            raise ValueError("当前范围没有可处理样本。")
        started = perf_counter()
        translated_kwargs = self._translate_action_kwargs(request.action_name, request.action_params)
        if controller is not None:
            controller.checkpoint()
        plan = _ProcessingExecutionPlan.build(
            sample_set,
            target_uids,
            _ACTION_REQUIREMENTS.get(request.action_name),
        )
        if controller is not None:
            controller.checkpoint()
        if plan.target_uids and not plan.runnable_uids:
            requirement = plan.requirement
            source_label = requirement.source_label if requirement is not None else "所需"
            raise ValueError(f"当前范围没有可用于 {request.action_name} 的{source_label}数据。")

        total = len(plan.runnable_uids) if plan.runnable_uids else 1
        if controller is not None:
            detail = f"准备执行：{request.action_name}"
            if plan.skipped_count and plan.requirement is not None:
                detail += f"；将跳过 {plan.skipped_count} 个缺少{plan.requirement.source_label}数据的样本"
            controller.report(
                title="处理当前主样本集",
                current=0,
                total=total,
                detail=detail,
            )
        if plan.runnable_uids:
            for index, uid in enumerate(plan.runnable_uids, start=1):
                if controller is not None:
                    controller.checkpoint()
                action(
                    uids=(uid,),
                    strict=request.strict,
                    overwrite=request.overwrite,
                    **translated_kwargs,
                )
                if controller is not None:
                    controller.checkpoint()
                if controller is not None:
                    controller.report(
                        title="处理当前主样本集",
                        current=index,
                        total=total,
                        detail=f"已处理 {index}/{total} 个样本：{uid}",
                    )
        else:
            if controller is not None:
                controller.checkpoint()
            action(
                strict=request.strict,
                overwrite=request.overwrite,
                **translated_kwargs,
            )
            if controller is not None:
                controller.report(
                    title="处理当前主样本集",
                    current=1,
                    total=total,
                    detail="已处理当前范围。",
                )
        duration_ms = int((perf_counter() - started) * 1000)
        affected_count = len(plan.runnable_uids) if plan.runnable_uids else len(sample_set)  # type: ignore[arg-type]
        message = f"已执行处理动作：{request.action_name}"
        if plan.skipped_count and plan.requirement is not None:
            message = (
                f"{message}；处理 {affected_count} 个，"
                f"跳过 {plan.skipped_count} 个缺少{plan.requirement.source_label}数据的样本"
            )

        if controller is not None:
            controller.checkpoint()
        state = self._session.processing_state
        state.current_action = request.action_name
        state.last_message = message
        state.last_action_count = affected_count
        state.last_duration_ms = duration_ms
        state.last_failure_message = ""
        state.current_request = request
        self._refresh_session_capability(sample_set, request, tuple(resolved_uids))
        self._session.bus.processing_state_changed.emit()
        self._session.bus.primary_changed.emit()
        self._session.bus.resource_tree_changed.emit()
        progress_text = f"{affected_count} / {plan.total_count}" if plan.total_count else "1 / 1"
        self._session._upsert_task("处理当前主样本集", "已完成", progress_text, message)
        self._session._prepend_log(
            "INFO", "gui.processing", f"{message}，样本数={affected_count}，耗时={duration_ms} ms"
        )
        if plan.skipped_count and plan.requirement is not None:
            preview_uids = "、".join(plan.skipped_uids[:5])
            suffix = " 等" if plan.skipped_count > 5 else ""
            self._session._prepend_issue(
                "提示",
                "处理范围跳过",
                (
                    f"当前动作需要{plan.requirement.source_label}数据；"
                    f"当前范围 {plan.total_count} 个样本，已跳过 {plan.skipped_count} 个：{preview_uids}{suffix}"
                ),
            )
            self._session.bus.issues_changed.emit()
        self._session.bus.task_changed.emit()
        self._session.bus.logs_changed.emit()
        return ProcessingResult(
            action_name=request.action_name,
            message=message,
            affected_count=affected_count,
            duration_ms=duration_ms,
            skipped_count=plan.skipped_count,
        )

    def _refresh_session_capability(
        self,
        sample_set: object,
        request: ProcessingRequestSnapshot,
        resolved_uids: tuple[str, ...],
    ) -> None:
        """按处理范围刷新 GUI 能力摘要。"""

        if _should_rebuild_full_summary(sample_set, resolved_uids):
            self._session.capability_snapshot = build_capability_snapshot(sample_set)
            self._session.primary_sampleset = summarize_runtime_sample_set(
                sample_set,
                name=self._session.primary_sampleset.name,
                storage_binding=self._session.primary_sampleset.storage_binding,
            )
            return

        output_slot = _ACTION_OUTPUT_SLOTS.get(request.action_name)
        if not output_slot:
            return
        previous = self._session.capability_snapshot
        data_slots = tuple(dict.fromkeys((*previous.data_slots, output_slot)))
        eval_results = tuple(name for name in ("zvl", "otovl", "fdmvl", "fpvdv") if name in data_slots)
        self._session.capability_snapshot = CapabilitySnapshot(
            data_slots=data_slots,
            eval_results=eval_results,
            scalar_frame=True,
            series_frame=bool(data_slots),
            peaks_frame=previous.peaks_frame or any(name in data_slots for name in ("accel", "vel", "disp", "force")),
        )

    def build_preview_sync(
        self,
        *,
        preview_kind: str,
        preview_scope: str,
        uids_text: str,
        metadata_fields: tuple[str, ...],
        features: tuple[str, ...],
        data_var: str,
        peak_source: str,
        scoped_uids: tuple[str, ...] = (),
        controller: ProcessingTaskController | None = None,
    ) -> ProcessingPreviewResult:
        """同步构建预览表。"""

        if controller is not None:
            controller.checkpoint()
        sample_set = self._require_runtime()
        resolved_uids = (
            list(scoped_uids)
            if scoped_uids
            else resolve_scope_uids(self._session, uids_text)
            if preview_scope == "subset"
            else []
        )
        if controller is not None:
            controller.checkpoint()
        uids = resolved_uids or None
        started = perf_counter()

        scalar_rows: tuple[tuple[str, ...], ...] = ()
        series_rows: tuple[tuple[str, ...], ...] = ()
        peaks_rows: tuple[tuple[str, ...], ...] = ()
        if controller is not None:
            controller.checkpoint()
        if preview_kind == "scalar_frame":
            frame = sample_set.scalar_frame(
                metadata_fields=metadata_fields or None,
                features=features or None,
                uids=uids,
                strict=False,
            )
            scalar_rows = _frame_rows(frame, limit=self._session.processing_state.preview_row_limit)
        elif preview_kind == "series_frame":
            frame = sample_set.series_frame(
                data_var,
                metadata_fields=metadata_fields or None,
                uids=uids,
                strict=False,
            )
            series_rows = _frame_rows(frame, limit=self._session.processing_state.preview_row_limit)
        elif preview_kind == "peaks_frame":
            frame = sample_set.peaks_frame(
                source=peak_source,
                metadata_fields=metadata_fields or None,
                uids=uids,
                strict=False,
            )
            peaks_rows = _frame_rows(frame, limit=self._session.processing_state.preview_row_limit)
        else:
            raise ValueError(f"不支持的预览类型：{preview_kind}")

        if controller is not None:
            controller.checkpoint()
        duration_ms = int((perf_counter() - started) * 1000)
        preview_title = (
            f"已生成预览表：{preview_kind} ({peak_source})"
            if preview_kind == "peaks_frame"
            else f"已生成预览表：{preview_kind}"
        )
        message = f"{preview_title}，耗时={duration_ms} ms"
        state = self._session.processing_state
        if controller is not None:
            controller.checkpoint()
        state.preview_title = preview_title
        state.preview_kind = preview_kind
        state.preview_scope = preview_scope
        state.last_duration_ms = duration_ms
        state.last_failure_message = ""
        self._session.set_processing_preview(
            action_name=state.current_action,
            message=state.last_message,
            scalar_rows=scalar_rows,
            series_rows=series_rows,
            peaks_rows=peaks_rows,
        )
        self._session._upsert_task("生成处理预览表", "已完成", "1 / 1", message)
        self._session._prepend_log("INFO", "gui.processing", message)
        self._session.bus.task_changed.emit()
        self._session.bus.logs_changed.emit()
        return ProcessingPreviewResult(
            preview_kind=preview_kind,
            preview_scope=preview_scope,
            preview_title=preview_title,
            message=message,
            scalar_rows=scalar_rows,
            series_rows=series_rows,
            peaks_rows=peaks_rows,
            duration_ms=duration_ms,
        )

    @Slot()
    def _cleanup(self) -> None:
        self._session.processing_state.busy = False
        self._session.processing_state.cancel_requested = False
        self._session.bus.processing_state_changed.emit()
        self._thread = None
        self._worker = None
        self._controller = None
        self.state_changed.emit()

    def _start(self, runner: Callable[[ProcessingTaskController], object], *, task_title: str, detail: str) -> None:
        if self.busy:
            raise ValueError("当前已有处理任务正在运行。")
        self._session.processing_state.busy = True
        self._session.processing_state.cancel_requested = False
        self._session._upsert_task(task_title, "进行中", "0 / 1", detail)
        self._session._prepend_log("INFO", "gui.processing", detail)
        self._session.bus.processing_state_changed.emit()
        self._session.bus.task_changed.emit()
        self._session.bus.logs_changed.emit()
        self._thread = QThread(self)
        self._controller = ProcessingTaskController()
        self._worker = _ProcessingWorker(runner, self._controller)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._handle_progress)
        self._worker.succeeded.connect(self.succeeded.emit)
        self._worker.failed.connect(self.failed.emit)
        self._worker.cancelled.connect(self._handle_cancelled)
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.finished.connect(self._cleanup)
        self._thread.start()
        self.state_changed.emit()

    @Slot(object)
    def _handle_progress(self, payload: object) -> None:
        if not isinstance(payload, ProcessingProgressUpdate):
            return
        if self._session.processing_state.cancel_requested:
            self._session._upsert_task(
                payload.title,
                "正在中止",
                f"{payload.current} / {payload.total}",
                "已请求中止，等待安全检查点。",
            )
        else:
            self._session._upsert_task(payload.title, "进行中", f"{payload.current} / {payload.total}", payload.detail)
        self._session.bus.task_changed.emit()
        self.state_changed.emit()

    @Slot(str)
    def _handle_cancelled(self, message: str) -> None:
        self._session.processing_state.last_failure_message = message
        self._session._upsert_task("处理当前主样本集", "已中止", "中止", message)
        self._session._prepend_log("WARNING", "gui.processing", message)
        self._session.bus.processing_state_changed.emit()
        self._session.bus.task_changed.emit()
        self._session.bus.logs_changed.emit()
        self.state_changed.emit()

    def _require_runtime(self) -> object:
        sample_set = self._session.primary_runtime
        if sample_set is None:
            raise ValueError("当前没有可处理的主样本集。")
        return sample_set

    def _translate_action_kwargs(self, action_name: str, action_params: dict[str, str]) -> dict[str, Any]:
        translated: dict[str, Any] = {}
        if action_name == "calc_respspec":
            translated["method"] = SDOFSolveMethod(action_params.get("method", "nigam-jennings"))
            translated["calc_unit_system"] = _resolve_unit_system(action_params.get("calc_unit_system", ""))
            translated["output_unit_system"] = _resolve_unit_system(action_params.get("output_unit_system", ""))
            translated["periods"] = _parse_periods(action_params.get("periods", ""))
            return translated
        if action_name in {"eval_zvl", "eval_otovl", "eval_fdmvl", "eval_fpvdv"}:
            translated["freq_range"] = _parse_freq_range(
                action_params.get("freq_range_min", ""),
                action_params.get("freq_range_max", ""),
            )
            translated["calc_unit_system"] = _resolve_unit_system(action_params.get("calc_unit_system", ""))
            translated["output_unit_system"] = _resolve_unit_system(action_params.get("output_unit_system", ""))
        if action_name == "eval_zvl":
            translated["weight_type"] = WeightType(action_params.get("weight_type", "wk"))
            translated["time_windows"] = float(action_params.get("time_windows", "1") or 1.0)
        elif action_name == "eval_otovl":
            translated["time_windows"] = float(action_params.get("time_windows", "1") or 1.0)
        elif action_name == "eval_fpvdv":
            translated["nsup"] = int(action_params.get("nsup", "4") or 4)
        return {key: value for key, value in translated.items() if value is not None}


def _frame_rows(frame: Any, *, limit: int) -> tuple[tuple[str, ...], ...]:
    if frame is None or frame.empty:
        return ()
    rows: list[tuple[str, ...]] = []
    head = frame.head(limit)
    for index, row in head.iterrows():
        rows.append(tuple([str(index), *(str(value) for value in row.tolist())]))
    return tuple(rows)


def _should_rebuild_full_summary(sample_set: object, resolved_uids: tuple[str, ...]) -> bool:
    if not callable(getattr(sample_set, "items", None)) or not callable(getattr(sample_set, "values", None)):
        return False
    if not resolved_uids:
        return True
    try:
        return len(resolved_uids) >= len(sample_set)  # type: ignore[arg-type]
    except TypeError:
        return False


def _resolve_unit_system(value: str) -> UnitSystem | None:
    match value.strip():
        case "":
            return None
        case "si":
            return UnitSystem.si()
        case "engineering":
            return UnitSystem.engineering()
    raise ValueError(f"不支持的单位制：{value}")


def _parse_periods(text: str) -> np.ndarray | None:
    stripped = text.strip()
    if not stripped:
        return None
    return np.asarray([float(item.strip()) for item in stripped.split(",") if item.strip()], dtype=float)


def _parse_freq_range(min_value: str, max_value: str) -> tuple[float, float] | None:
    min_text = min_value.strip()
    max_text = max_value.strip()
    if not min_text and not max_text:
        return None
    if not min_text or not max_text:
        raise ValueError("freq_range 需要同时提供最小值和最大值")
    return (float(min_text), float(max_text))
