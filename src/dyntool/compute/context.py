"""计算上下文定义。"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

from .units import UnitSystem, get_default_unit_system


@dataclass(slots=True, frozen=True)
class ComputeContext:
    """统一计算参数上下文。"""

    input_unit_system: UnitSystem = field(default_factory=get_default_unit_system)
    calc_unit_system: UnitSystem = field(default_factory=get_default_unit_system)
    output_unit_system: UnitSystem = field(default_factory=get_default_unit_system)
    freq_range: tuple[float, float] = (1.0, 80.0)
    time_window: float = 1.0
    damping_ratio: float = 0.05
    weight_type: str = "wk"
    extras: dict[str, Any] = field(default_factory=dict)

    def with_updates(self, **kwargs: Any) -> "ComputeContext":
        """基于当前上下文创建新上下文。"""

        merged_extras = dict(self.extras)
        if "extras" in kwargs and isinstance(kwargs["extras"], dict):
            merged_extras.update(kwargs["extras"])
        kwargs["extras"] = merged_extras
        return replace(self, **kwargs)


__all__ = ["ComputeContext"]
