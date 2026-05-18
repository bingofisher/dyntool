"""导入工作流运行态控制。"""

from __future__ import annotations

from dataclasses import dataclass
from threading import Event
from typing import Callable
from uuid import uuid4


@dataclass(slots=True)
class ImportProgressUpdate:
    """导入阶段进度快照。"""

    operation_id: str
    phase_code: str
    phase_label: str
    progress_prefix: str
    detail: str = ""
    current: int | None = None
    total: int | None = None


class ImportCancelledError(RuntimeError):
    """导入被请求中止时抛出的内部异常。"""


class ImportOperationController:
    """导入后台任务控制器。"""

    def __init__(
        self,
        *,
        operation_id: str | None = None,
        progress_reporter: Callable[[ImportProgressUpdate], None] | None = None,
    ) -> None:
        self.operation_id = operation_id or uuid4().hex
        self._progress_reporter = progress_reporter
        self._cancel_event = Event()

    @property
    def cancel_requested(self) -> bool:
        """返回当前是否已经请求中止。"""

        return self._cancel_event.is_set()

    def request_cancel(self) -> None:
        """请求当前后台导入任务中止。"""

        self._cancel_event.set()

    def set_progress_reporter(self, progress_reporter: Callable[[ImportProgressUpdate], None] | None) -> None:
        """更新进度上报回调。"""

        self._progress_reporter = progress_reporter

    def checkpoint(self, message: str = "导入已中止。") -> None:
        """在安全检查点判断是否应中止当前流程。"""

        if self.cancel_requested:
            raise ImportCancelledError(message)

    def update_phase(
        self,
        phase_code: str,
        phase_label: str,
        *,
        progress_prefix: str,
        detail: str = "",
        current: int | None = None,
        total: int | None = None,
    ) -> None:
        """上报阶段与进度。"""

        if self._progress_reporter is None:
            return
        self._progress_reporter(
            ImportProgressUpdate(
                operation_id=self.operation_id,
                phase_code=phase_code,
                phase_label=phase_label,
                progress_prefix=progress_prefix,
                detail=detail,
                current=current,
                total=total,
            )
        )

    def make_storage_progress_callback(
        self,
        *,
        phase_code: str,
        phase_label: str,
        progress_prefix: str,
        detail: str = "",
    ) -> Callable[[int, int], None]:
        """构造存储层批量进度回调。"""

        def _callback(completed: int, total: int) -> None:
            self.checkpoint()
            self.update_phase(
                phase_code,
                phase_label,
                progress_prefix=progress_prefix,
                detail=detail,
                current=completed,
                total=total,
            )

        return _callback


__all__ = ["ImportCancelledError", "ImportOperationController", "ImportProgressUpdate"]
