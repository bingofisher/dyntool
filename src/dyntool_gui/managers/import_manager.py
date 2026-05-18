"""导入任务协调器。"""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QObject, QThread, Signal, Slot

from ..import_runtime import ImportCancelledError, ImportOperationController, ImportProgressUpdate
from ..session import ProjectSession


class _ImportOperationWorker(QObject):
    """后台导入任务执行器。"""

    progress = Signal(object)  # PySide6 limitation: no generic signals
    succeeded = Signal(object)  # PySide6 limitation: no generic signals
    failed = Signal(str, bool)
    finished = Signal()

    def __init__(
        self,
        operation: Callable[[ImportOperationController], object],
        controller: ImportOperationController,
    ) -> None:
        super().__init__()
        self._operation = operation
        self._controller = controller
        self._controller.set_progress_reporter(self.progress.emit)

    @Slot()
    def run(self) -> None:
        try:
            self.succeeded.emit(self._operation(self._controller))
        except ImportCancelledError as exc:
            self.failed.emit(str(exc), True)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc), False)
        finally:
            self.finished.emit()


class ImportManager(QObject):
    """负责导入线程、进度、中止与回调分发。"""

    progress = Signal(object)  # PySide6 limitation: no generic signals
    succeeded = Signal(object)  # PySide6 limitation: no generic signals
    failed = Signal(str, bool)
    state_changed = Signal()

    def __init__(self, session: ProjectSession, parent: object | None = None) -> None:
        super().__init__(parent)
        self._session = session
        self._thread: QThread | None = None
        self._worker: _ImportOperationWorker | None = None
        self._controller: ImportOperationController | None = None
        self._mode: str | None = None
        self._task_title = ""

    @property
    def busy(self) -> bool:
        """返回当前是否有活动导入任务。"""

        return self._thread is not None

    @property
    def mode(self) -> str | None:
        """返回当前运行模式。"""

        return self._mode

    @property
    def task_title(self) -> str:
        """返回当前任务标题。"""

        return self._task_title

    def start_operation(
        self,
        *,
        task_title: str,
        detail: str,
        mode: str,
        operation: Callable[[ImportOperationController], object],
    ) -> None:
        """启动新的导入后台任务。"""

        controller = ImportOperationController()
        self._session.begin_import_activity(
            task_title,
            detail,
            operation_id=controller.operation_id,
            phase_label=task_title,
            progress_prefix=task_title,
            cancellable=True,
        )
        self._controller = controller
        self._mode = mode
        self._task_title = task_title
        self._thread = QThread(self)
        self._worker = _ImportOperationWorker(operation, controller)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._handle_progress)
        self._worker.succeeded.connect(self._handle_success)
        self._worker.failed.connect(self._handle_failure)
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.finished.connect(self._cleanup)
        self._thread.start()
        self.state_changed.emit()

    def request_cancel(self, message: str = "已请求中止，正在等待安全检查点并释放资源。") -> None:
        """请求中止当前导入任务。"""

        if self._controller is None or not self._session.import_state.busy:
            return
        self._session.mark_import_cancel_requested(message)
        self._controller.request_cancel()
        self.state_changed.emit()

    @Slot(object)
    def _handle_progress(self, payload: object) -> None:
        if not isinstance(payload, ImportProgressUpdate):
            return
        self._session.update_import_progress(
            operation_id=payload.operation_id,
            phase_code=payload.phase_code,
            phase_label=payload.phase_label,
            progress_prefix=payload.progress_prefix,
            detail=payload.detail,
            current=payload.current,
            total=payload.total,
        )
        self.progress.emit(payload)
        self.state_changed.emit()

    @Slot(object)
    def _handle_success(self, payload: object) -> None:
        self.succeeded.emit(payload)
        self.state_changed.emit()

    @Slot(str, bool)
    def _handle_failure(self, message: str, cancelled: bool) -> None:
        self.failed.emit(message, cancelled)
        self.state_changed.emit()

    @Slot()
    def _cleanup(self) -> None:
        self._thread = None
        self._worker = None
        self._controller = None
        self._mode = None
        self._task_title = ""
        self.state_changed.emit()
