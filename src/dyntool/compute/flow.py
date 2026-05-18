"""可链式组合的计算流对象。"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

from .context import ComputeContext


@dataclass(slots=True)
class ComputeFlow:
    """支持处理、检查点与提交的计算流。"""

    _result: Any
    context: ComputeContext = field(default_factory=ComputeContext)
    _artifacts: dict[str, Any] = field(default_factory=dict)
    _metrics: dict[str, float] = field(default_factory=dict)
    _checkpoints: dict[str, Any] = field(default_factory=dict)
    _history: list[dict[str, Any]] = field(default_factory=list)
    commit_handler: Any | None = None
    source: str | None = None

    def result(self) -> Any:
        """返回当前结果。"""

        return self._result

    def set_result(self, value: Any, *, action: str = "set_result") -> "ComputeFlow":
        """替换当前结果并记录历史。"""

        self._result = value
        self._history.append({"action": action})
        return self

    def then(
        self,
        operation: Any,
        /,
        *args: Any,
        action: str | None = None,
        **kwargs: Any,
    ) -> "ComputeFlow":
        """对当前结果应用操作并继续链式处理。"""

        if not callable(operation):
            raise TypeError("operation 必须是可调用对象")
        self._result = operation(self._result, *args, **kwargs)
        self._history.append(
            {
                "action": action or "then",
                "operation": getattr(operation, "__name__", type(operation).__name__),
            }
        )
        return self

    def truncate(self, start: float, end: float) -> "ComputeFlow":
        """对当前时序结果执行截断。"""

        return self.then(lambda model: model.truncate(start, end), action="truncate")

    def baseline(self, *, method: Any, order: int = 1) -> "ComputeFlow":
        """对当前时序结果执行基线校正。"""

        return self.then(lambda model: model.baseline_correct(method=method, order=order), action="baseline")

    def highpass(self, freq: float, *, order: int = 4) -> "ComputeFlow":
        """对当前时序结果执行高通滤波。"""

        return self.then(lambda model: model.filter_highpass(freq, order=order), action="highpass")

    def lowpass(self, freq: float, *, order: int = 4) -> "ComputeFlow":
        """对当前时序结果执行低通滤波。"""

        return self.then(lambda model: model.filter_lowpass(freq, order=order), action="lowpass")

    def bandpass(self, f_low: float, f_high: float, *, order: int = 4) -> "ComputeFlow":
        """对当前时序结果执行带通滤波。"""

        return self.then(
            lambda model: model.filter_bandpass(f_low, f_high=f_high, order=order),
            action="bandpass",
        )

    def artifact(self, name: str) -> Any:
        """返回已保存的中间产物。"""

        return self._artifacts[name]

    def add_artifact(self, name: str, value: Any) -> "ComputeFlow":
        """保存中间产物。"""

        self._artifacts[name] = value
        self._history.append({"action": "artifact", "name": name})
        return self

    def metrics(self) -> dict[str, float]:
        """返回指标快照。"""

        return dict(self._metrics)

    def add_metric(self, name: str, value: float) -> "ComputeFlow":
        """保存数值指标。"""

        self._metrics[name] = float(value)
        self._history.append({"action": "metric", "name": name, "value": float(value)})
        return self

    def checkpoint(self, name: str) -> "ComputeFlow":
        """保存深拷贝检查点。"""

        self._checkpoints[name] = deepcopy(
            {
                "result": self._result,
                "artifacts": self._artifacts,
                "metrics": self._metrics,
                "history": self._history,
            }
        )
        self._history.append({"action": "checkpoint", "name": name})
        return self

    def from_checkpoint(self, name: str) -> "ComputeFlow":
        """从命名检查点恢复。"""

        snapshot = deepcopy(self._checkpoints[name])
        self._result = snapshot["result"]
        self._artifacts = snapshot["artifacts"]
        self._metrics = snapshot["metrics"]
        self._history = snapshot["history"] + [{"action": "restore", "name": name}]
        return self

    def restore(self, name: str) -> "ComputeFlow":
        """恢复检查点的可读别名。"""

        return self.from_checkpoint(name)

    def branch(self, name: str) -> "ComputeFlow":
        """创建深拷贝分支流。"""

        branch_flow = ComputeFlow(
            _result=deepcopy(self._result),
            context=self.context,
            _artifacts=deepcopy(self._artifacts),
            _metrics=deepcopy(self._metrics),
            _checkpoints=deepcopy(self._checkpoints),
            _history=deepcopy(self._history),
        )
        branch_flow._history.append({"action": "branch", "name": name})
        return branch_flow

    def commit_with_options(self, *, replace: bool) -> Any:
        """按选项提交当前结果。"""

        self._history.append({"action": "commit", "replace": replace})
        if self.commit_handler is None:
            return self._result
        return self.commit_handler(self._result, replace=replace)

    def commit(self, *, replace: bool = True) -> Any:
        """提交当前结果，可选择是否原位写回。"""

        return self.commit_with_options(replace=replace)

    def compare(self, other: Any) -> dict[str, Any]:
        """比较当前结果与另一结果的基础差异。"""

        left = self._result
        if isinstance(other, str):
            snapshot = self._checkpoints[other]
            right = snapshot["result"]
        elif isinstance(other, ComputeFlow):
            right = other.result()
        else:
            right = other
        comparison: dict[str, Any] = {
            "left_type": type(left).__name__,
            "right_type": type(right).__name__,
            "same_type": type(left) is type(right),
        }
        if hasattr(left, "to_array") and hasattr(right, "to_array"):
            left_array = left.to_array()
            right_array = right.to_array()
            comparison["left_shape"] = tuple(left_array.shape)
            comparison["right_shape"] = tuple(right_array.shape)
            comparison["same_shape"] = tuple(left_array.shape) == tuple(right_array.shape)
        else:
            comparison["equal"] = left == right
        self._history.append({"action": "compare"})
        return comparison

    def history(self) -> list[dict[str, Any]]:
        """返回与内部状态隔离的历史快照。"""

        return deepcopy(self._history)


__all__ = ["ComputeFlow"]
