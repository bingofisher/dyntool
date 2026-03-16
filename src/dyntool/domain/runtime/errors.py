"""领域对象运行时绑定错误。"""

from __future__ import annotations


class RuntimeBindingError(RuntimeError):
    """表示领域对象缺少可用的运行时绑定。"""


class RecoverableIOError(RuntimeError):
    """表示可恢复的对象级 I/O 或批处理错误。"""


def build_missing_runtime_error(*, family: str, action: str) -> RuntimeBindingError:
    """构造缺少运行时绑定时的统一错误。"""

    return RuntimeBindingError(f"未绑定 {family} runtime，无法执行 {action}。")
