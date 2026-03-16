"""Chainable compute workflow utilities."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

from .context import ComputeContext


@dataclass(slots=True)
class ComputeFlow:
    """Chainable compute workflow with checkpoints and branching."""

    _result: Any
    context: ComputeContext = field(default_factory=ComputeContext)
    _artifacts: dict[str, Any] = field(default_factory=dict)
    _metrics: dict[str, float] = field(default_factory=dict)
    _checkpoints: dict[str, Any] = field(default_factory=dict)
    _history: list[dict[str, Any]] = field(default_factory=list)

    def result(self) -> Any:
        """Return the current result."""

        return self._result

    def set_result(self, value: Any, *, action: str = "set_result") -> "ComputeFlow":
        """Replace the current result and record history."""

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
        """Apply an operation to the current result and continue chaining."""

        if not callable(operation):
            raise TypeError("operation must be callable")
        self._result = operation(self._result, *args, **kwargs)
        self._history.append(
            {
                "action": action or "then",
                "operation": getattr(operation, "__name__", type(operation).__name__),
            }
        )
        return self

    def artifact(self, name: str) -> Any:
        """Return a stored artifact."""

        return self._artifacts[name]

    def add_artifact(self, name: str, value: Any) -> "ComputeFlow":
        """Store an artifact."""

        self._artifacts[name] = value
        self._history.append({"action": "artifact", "name": name})
        return self

    def metrics(self) -> dict[str, float]:
        """Return a snapshot of metrics."""

        return dict(self._metrics)

    def add_metric(self, name: str, value: float) -> "ComputeFlow":
        """Store a numeric metric."""

        self._metrics[name] = float(value)
        self._history.append({"action": "metric", "name": name, "value": float(value)})
        return self

    def checkpoint(self, name: str) -> "ComputeFlow":
        """Save a deep-copied checkpoint."""

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
        """Restore from a named checkpoint."""

        snapshot = deepcopy(self._checkpoints[name])
        self._result = snapshot["result"]
        self._artifacts = snapshot["artifacts"]
        self._metrics = snapshot["metrics"]
        self._history = snapshot["history"] + [{"action": "restore", "name": name}]
        return self

    def restore(self, name: str) -> "ComputeFlow":
        """Readable alias for restoring a checkpoint."""

        return self.from_checkpoint(name)

    def branch(self, name: str) -> "ComputeFlow":
        """Create a deep-copied branch flow."""

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

    def commit(self) -> Any:
        """Return the current result and record a commit action."""

        self._history.append({"action": "commit"})
        return self._result

    def history(self) -> list[dict[str, Any]]:
        """Return the workflow history."""

        return list(self._history)


__all__ = ["ComputeFlow"]
