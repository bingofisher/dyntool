"""领域样本批处理辅助逻辑。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, Iterable, TypeVar

from .commands import VibEvalCommand, run_vib_eval

if TYPE_CHECKING:
    from .base import SampleBaseModel

SampleT = TypeVar("SampleT", bound="SampleBaseModel")
BatchOutT = TypeVar("BatchOutT")


@dataclass(slots=True)
class VibEvalBatchStats:
    """批量振动评价统计信息。"""

    processed: int = 0
    skipped: int = 0
    failed: int = 0
    valid_samples: int = 0


def select_sample_items(
    samples: dict[str, SampleT],
    *,
    uid: str | None = None,
    uids: list[str] | None = None,
    filter_func: Callable[[SampleT], bool] | None = None,
) -> list[tuple[str, SampleT]]:
    """统一样本选择逻辑。"""

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
    **kwargs: object,
) -> tuple[dict[str, tuple[bool, str]], VibEvalBatchStats]:
    """批量执行显式命令分发的振动评价。"""

    results: dict[str, tuple[bool, str]] = {}
    stats = VibEvalBatchStats()
    items_list = list(items)
    stats.valid_samples = sum(1 for _, sample in items_list if getattr(sample, "accel", None) is not None)

    for uid, sample in items_list:
        success, message = run_vib_eval(sample, command, force=overwrite, **kwargs)
        results[uid] = (success, message)
        if success:
            stats.processed += 1
        elif "已存在" in message:
            stats.skipped += 1
        elif "无加速度数据" in message:
            continue
        else:
            stats.failed += 1
    return results, stats


def run_callable_batch(
    items: Iterable[tuple[str, SampleT]],
    *,
    func: Callable[..., BatchOutT],
    strict: bool,
    **kwargs: Any,
) -> dict[str, BatchOutT]:
    """通用批处理执行器。"""

    outputs: dict[str, BatchOutT] = {}
    for uid, sample in items:
        try:
            outputs[uid] = func(sample, **kwargs)
        except Exception:
            if strict:
                raise
    return outputs


__all__ = [
    "VibEvalBatchStats",
    "select_sample_items",
    "run_vibeval_batch",
    "run_callable_batch",
]
