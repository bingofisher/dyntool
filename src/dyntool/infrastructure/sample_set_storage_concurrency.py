"""样本集存储并发辅助函数。"""

from __future__ import annotations

from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from typing import Any, Callable, Iterator, TypeVar

TItem = TypeVar("TItem")


def drain_completed(
    pending: dict[Future[Any], str],
) -> list[tuple[str, Future[Any]]]:
    """收集已完成的 future，并同步更新待处理映射。"""

    if not pending:
        return []
    done, _ = wait(set(pending.keys()), return_when=FIRST_COMPLETED)
    completed: list[tuple[str, Future[Any]]] = []
    for future in done:
        uid = pending.pop(future)
        completed.append((uid, future))
    return completed


def submit_until_limit(
    executor: ThreadPoolExecutor,
    pending: dict[Future[Any], str],
    tasks: Iterator[tuple[str, TItem]],
    submitter: Callable[[TItem], Any],
    *,
    limit: int,
) -> None:
    """持续提交任务，直到并发窗口达到限制。"""

    while len(pending) < limit:
        try:
            uid, item = next(tasks)
        except StopIteration:
            break
        pending[executor.submit(submitter, item)] = uid


__all__ = ["drain_completed", "submit_until_limit"]
