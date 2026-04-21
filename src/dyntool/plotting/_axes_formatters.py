"""plotting 坐标轴刻度规划与格式化实现。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np
from matplotlib.ticker import ScalarFormatter

from ._axes_common import format_plain_number


class AxisNumberFormatter(ScalarFormatter):
    """连续数值轴格式化器。"""

    def __init__(
        self,
        *,
        scale_factor: float = 1.0,
        decimals: int | None = None,
        trim_trailing_zeros: bool = True,
    ) -> None:
        super().__init__(useMathText=True)
        self.scale_factor = float(scale_factor)
        self.decimals = decimals
        self.trim_trailing_zeros = trim_trailing_zeros
        self.set_useOffset(True)
        if np.isclose(self.scale_factor, 1.0):
            self._fixed_exponent: int | None = None
            self.set_scientific(False)
        else:
            self._fixed_exponent = int(round(np.log10(abs(self.scale_factor))))
            self.set_scientific(True)
            self.set_powerlimits((0, 0))

    def __call__(self, value: float, _position: float | None = None) -> str:
        scale_factor = 10.0**self.orderOfMagnitude if self.orderOfMagnitude else 1.0
        scaled = (value - self.offset) / scale_factor
        resolved_decimals = self._resolve_decimals(scaled)
        if resolved_decimals <= 0:
            return format_plain_number(round(scaled))
        rendered = f"{scaled:.{resolved_decimals}f}"
        if self.trim_trailing_zeros and self.decimals is None:
            rendered = rendered.rstrip("0").rstrip(".")
        return rendered

    def offset_text(self) -> str:
        """返回 Matplotlib 使用的 offset 文本。"""

        return self.get_offset()

    def _resolve_decimals(self, scaled_value: float) -> int:
        if self.decimals is not None:
            return max(0, self.decimals)
        rounded = round(scaled_value)
        if abs(scaled_value - rounded) < 1e-9:
            return 0
        return 3

    def _set_order_of_magnitude(self) -> None:
        if self._fixed_exponent is not None:
            self.orderOfMagnitude = self._fixed_exponent
            return
        super()._set_order_of_magnitude()


@dataclass(slots=True, frozen=True)
class TickPlanner:
    """连续数值轴 major ticks 规划器。"""

    lower: float
    upper: float
    target_blocks: int = 5

    def plan(self) -> np.ndarray:
        """生成可读的 major ticks。"""

        lower = float(self.lower)
        upper = float(self.upper)
        if lower == upper:
            margin = max(abs(lower) * 0.1, 1.0)
            lower -= margin
            upper += margin
        if lower > upper:
            lower, upper = upper, lower

        step = self._resolve_step(lower, upper, self.target_blocks)
        start = np.floor(lower / step) * step
        end = np.ceil(upper / step) * step
        ticks = self._build_ticks(start, end, step)
        return self._normalize_ticks(ticks)

    def plan_segments(self) -> np.ndarray:
        """按指定段数严格等分生成 major ticks。"""

        lower = float(self.lower)
        upper = float(self.upper)
        if lower == upper:
            margin = max(abs(lower) * 0.1, 1.0)
            lower -= margin
            upper += margin
        if lower > upper:
            lower, upper = upper, lower
        return self._normalize_ticks(np.linspace(lower, upper, max(self.target_blocks, 1) + 1, dtype=float))

    @classmethod
    def _resolve_step(cls, lower: float, upper: float, target_blocks: int) -> float:
        span = max(abs(upper - lower), 1e-12)
        desired = span / max(target_blocks, 1)
        return cls._nice_step(desired)

    @staticmethod
    def _nice_step(value: float) -> float:
        if value <= 0:
            return 1.0
        exponent = np.floor(np.log10(value))
        fraction = value / (10.0**exponent)
        if fraction <= 1.0:
            nice_fraction = 1.0
        elif fraction <= 2.0:
            nice_fraction = 2.0
        elif fraction <= 2.5:
            nice_fraction = 2.5
        elif fraction <= 5.0:
            nice_fraction = 5.0
        else:
            nice_fraction = 10.0
        return float(nice_fraction * (10.0**exponent))

    @staticmethod
    def _build_ticks(start: float, end: float, step: float) -> np.ndarray:
        count = int(np.round((end - start) / step)) + 1
        return np.asarray([start + idx * step for idx in range(count)], dtype=float)

    @staticmethod
    def _normalize_ticks(ticks: np.ndarray) -> np.ndarray:
        normalized = ticks.copy()
        normalized[np.isclose(normalized, 0.0, atol=1e-12)] = 0.0
        return normalized


@dataclass(slots=True, frozen=True)
class DiscreteAxisFormatter:
    """离散轴刻度文本格式化器。"""

    positions: tuple[float, ...]
    labels: tuple[str, ...]
    show_every: int | None = None

    @classmethod
    def from_number_values(
        cls,
        *,
        positions: Sequence[float],
        values: Sequence[float],
        show_every: int | None = None,
    ) -> "DiscreteAxisFormatter":
        """从数值序列构造离散轴格式化器。"""

        return cls(
            positions=tuple(float(item) for item in positions),
            labels=tuple(format_plain_number(float(item)) for item in values),
            show_every=show_every,
        )

    def resolved_labels(self) -> tuple[str, ...]:
        """返回根据显示步长稀疏后的标签。"""

        if self.show_every is None or self.show_every <= 1:
            return self.labels
        return tuple(label if idx % self.show_every == 0 else "" for idx, label in enumerate(self.labels))
