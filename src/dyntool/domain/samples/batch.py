"""样本批处理结果、统计与辅助执行函数。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, Generic, Iterable, Iterator, TypeVar

from ..runtime.errors import RecoverableIOError
from .commands import VibEvalCommand

if TYPE_CHECKING:
    from .base import SampleBaseModel

SampleT = TypeVar("SampleT", bound="SampleBaseModel")
ResultT = TypeVar("ResultT")

OperationStatus = str


@dataclass(slots=True)
class OperationResult(Generic[ResultT]):
    """表示单个对象操作结果。"""

    action: str
    status: OperationStatus
    message: str
    value: ResultT | None = None
    error: Exception | None = None

    @property
    def success(self) -> bool:
        """返回当前结果是否成功。"""

        return self.status == "success"


@dataclass(slots=True)
class BatchOperationStats:
    """表示批处理统计信息。"""

    total: int = 0
    valid_samples: int = 0
    succeeded: int = 0
    skipped: int = 0
    failed: int = 0


@dataclass(slots=True)
class BatchOperationReport(Generic[ResultT]):
    """表示统一批处理报告。"""

    action: str
    strict: bool
    stats: BatchOperationStats = field(default_factory=BatchOperationStats)
    results: dict[str, OperationResult[ResultT]] = field(default_factory=dict)

    def __iter__(self) -> Iterator[str]:
        """按样本 UID 迭代结果键。"""

        return iter(self.results)

    def __getitem__(self, uid: str) -> OperationResult[ResultT]:
        """返回指定样本的处理结果。"""

        return self.results[uid]

    def __len__(self) -> int:
        """返回结果条目数。"""

        return len(self.results)

    def items(self) -> Any:
        """返回 `uid -> result` 视图。"""

        return self.results.items()

    def keys(self) -> Any:
        """返回结果键视图。"""

        return self.results.keys()

    def values(self) -> Any:
        """返回结果值视图。"""

        return self.results.values()

    def add(self, uid: str, result: OperationResult[ResultT]) -> None:
        """登记单个样本结果并更新统计。"""

        self.stats.total += 1
        self.results[uid] = result
        if result.status == "success":
            self.stats.succeeded += 1
        elif result.status == "skipped":
            self.stats.skipped += 1
        elif result.status == "failed":
            self.stats.failed += 1


def make_operation_result(
    *,
    action: str,
    success: bool,
    message: str,
    value: ResultT | None = None,
    error: Exception | None = None,
) -> OperationResult[ResultT]:
    """根据成功标记构造统一操作结果。"""

    return OperationResult(
        action=action,
        status=infer_batch_status(success, message),
        message=message,
        value=value,
        error=error,
    )


def infer_batch_status(success: bool, message: str) -> OperationStatus:
    """根据执行结果推断批处理状态。"""

    if success:
        return "success"
    if "已存在" in message or "跳过" in message:
        return "skipped"
    return "failed"


def _recoverable_io_error() -> type[RecoverableIOError]:
    """返回统一的可恢复 I/O 错误类型。"""

    return RecoverableIOError


def select_sample_items(
    samples: dict[str, SampleT],
    *,
    uid: str | None = None,
    uids: list[str] | None = None,
    filter_func: Callable[[SampleT], bool] | None = None,
) -> list[tuple[str, SampleT]]:
    """根据 UID、UID 列表或过滤函数统一筛选样本。"""

    if uid is not None and uids is not None:
        raise ValueError("uid 与 uids 不能同时指定")

    if uid is not None:
        if uid not in samples:
            raise KeyError(f"样本 '{uid}' 不存在于样本集中")
        items = [(uid, samples[uid])]
    elif uids is not None:
        missing = [item for item in uids if item not in samples]
        if missing:
            raise KeyError(f"样本不存在: {missing}")
        items = [(item, samples[item]) for item in uids]
    else:
        items = list(samples.items())

    if filter_func is not None:
        items = [(item_uid, sample) for item_uid, sample in items if filter_func(sample)]
    return items


def run_vibeval_batch(
    items: Iterable[tuple[str, SampleT]],
    *,
    command: VibEvalCommand,
    overwrite: bool = False,
    strict: bool = True,
    **options: Any,
) -> BatchOperationReport[SampleT]:
    """批量执行显式振动评价命令。

    Args:
        items: 待处理的 `(uid, sample)` 序列。
        command: 显式评价命令。
        overwrite: 是否允许覆盖已有评价结果。
        strict: 遇到失败时是否立即抛出可恢复错误。
        **options: 传给 `run_vib_eval()` 的评价参数，支持 `freq_range`、
            `weight_type`、`time_windows`、`nsup`、`calc_unit_system`、
            `output_unit_system` 等正式键。

    Returns:
        统一批处理报告。
    """

    from .commands import run_vib_eval

    report = BatchOperationReport[SampleT](action=command.value, strict=strict)
    items_list = list(items)
    report.stats.valid_samples = sum(1 for _, sample in items_list if getattr(sample, "accel", None) is not None)

    for uid, sample in items_list:
        result = run_vib_eval(sample, command, overwrite=overwrite, **options)
        report.add(uid, result)
        if strict and result.status == "failed":
            raise RecoverableIOError(f"批处理失败: {uid}") from result.error
    return report


def run_callable_batch(
    items: Iterable[tuple[str, SampleT]],
    *,
    func: Callable[..., ResultT],
    strict: bool,
    **kwargs: Any,
) -> dict[str, ResultT]:
    """对样本序列执行通用批处理函数。"""

    outputs: dict[str, ResultT] = {}
    for uid, sample in items:
        try:
            outputs[uid] = func(sample, **kwargs)
        except Exception:
            if strict:
                raise
    return outputs


__all__ = [
    "BatchOperationReport",
    "BatchOperationStats",
    "OperationResult",
    "_recoverable_io_error",
    "infer_batch_status",
    "make_operation_result",
    "run_callable_batch",
    "run_vibeval_batch",
    "select_sample_items",
]
