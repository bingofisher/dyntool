"""plotting 轴样式、网格、图例与修轴辅助 API。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Literal, Mapping, Sequence

import numpy as np
from matplotlib.axes import Axes
from matplotlib.legend import Legend
from matplotlib.ticker import FixedFormatter, FixedLocator, ScalarFormatter
from numpy.typing import ArrayLike

from .config import load_plotting_section

AxisSide = Literal["top", "bottom", "left", "right"]
AxisFormatMode = Literal["continuous", "discrete"]


def _format_plain_number(value: float) -> str:
    value_int = int(value)
    if abs(value - value_int) < 1e-9:
        return str(value_int)
    return f"{value:.12f}".rstrip("0").rstrip(".")


@dataclass(slots=True)
class AxisFrame:
    """坐标轴样式配置。

    Notes:
        正式配置结构采用 ``axis_frame.frame`` 作为底座，再用
        ``axis_frame.top``、``axis_frame.bottom``、``axis_frame.left``、``axis_frame.right``
        做方向覆盖。该对象只负责 spine 与 ``tick_params`` 外观，不负责 locator、
        formatter、legend、网格和坐标轴语义。
    """

    params: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_file(cls, path: str | Path) -> "AxisFrame":
        """从统一 plotting 配置文件读取轴样式。"""

        payload = load_plotting_section(path, section="axis_frame", fallback_root=True)
        return cls(params=cls._normalize_params(payload))

    @classmethod
    def default(cls) -> "AxisFrame":
        """返回默认轴样式。"""

        return cls(
            params=cls._normalize_params(
                {
                    "frame": {
                        "spine": {"linewidth": 0.8, "color": "black", "visible": True},
                        "major": {"direction": "in", "length": 3.0, "width": 0.8, "labelsize": 8},
                        "minor": {"direction": "in", "length": 2.0, "width": 0.6},
                    }
                }
            )
        )

    def apply(self, ax: Axes) -> None:
        """将样式应用到目标 ``Axes``。"""

        params = self.params or {}
        valid_spines = tuple(ax.spines.keys())

        frame_params = params.get("frame")
        if isinstance(frame_params, Mapping):
            for axis in valid_spines:
                self._apply_axis(ax, axis=axis, params=frame_params)

        for axis in valid_spines:
            axis_params = params.get(axis)
            if isinstance(axis_params, Mapping):
                self._apply_axis(ax, axis=axis, params=axis_params)

    @staticmethod
    def _normalize_params(payload: Mapping[str, Any]) -> dict[str, Any]:
        if "frame" in payload or any(key in payload for key in ("top", "bottom", "left", "right")):
            return {str(key): value for key, value in payload.items() if isinstance(value, Mapping)}
        normalized: dict[str, Any] = {}
        frame: dict[str, Any] = {}
        if "spine" in payload:
            frame["spine"] = dict(payload["spine"])
        if "major_ticks" in payload:
            frame["major"] = dict(payload["major_ticks"])
        if "minor_ticks" in payload:
            frame["minor"] = dict(payload["minor_ticks"])
        if frame:
            normalized["frame"] = frame
        return normalized

    def _apply_axis(self, ax: Axes, *, axis: str, params: Mapping[str, Any]) -> None:
        spine_params = params.get("spine")
        if isinstance(spine_params, Mapping):
            self._set_spine(ax, loc=axis, **{k: v for k, v in spine_params.items() if v is not None})

        major_params = params.get("major")
        if isinstance(major_params, Mapping):
            self._set_tick(ax, loc=axis, which="major", **{k: v for k, v in major_params.items() if v is not None})

        minor_params = params.get("minor")
        if isinstance(minor_params, Mapping):
            self._set_tick(ax, loc=axis, which="minor", **{k: v for k, v in minor_params.items() if v is not None})

    @staticmethod
    def _set_spine(ax: Axes, loc: str, **kwargs: Any) -> None:
        valid_spines = tuple(ax.spines.keys())
        if loc not in valid_spines:
            raise ValueError(f"非法的轴方向: {loc}。可用方向为 {valid_spines}。")
        spine = ax.spines[loc]
        spine.set_linewidth(float(kwargs.get("linewidth", spine.get_linewidth())))
        spine.set_color(kwargs.get("color", spine.get_edgecolor()))
        spine.set_visible(bool(kwargs.get("visible", spine.get_visible())))
        spine.set_zorder(kwargs.get("zorder", spine.get_zorder()))

    @staticmethod
    def _set_tick(ax: Axes, loc: str, *, which: str, **kwargs: Any) -> None:
        valid_spines = tuple(ax.spines.keys())
        if loc not in valid_spines:
            raise ValueError(f"非法的轴方向: {loc}。可用方向为 {valid_spines}。")
        clean_kwargs = {k: v for k, v in kwargs.items() if v is not None and k not in {"axis", "which"}}
        able = clean_kwargs.pop("able", None)
        if able is not None:
            clean_kwargs[loc] = able
        axis_map = {"top": "x", "bottom": "x", "left": "y", "right": "y"}
        ax.tick_params(axis=axis_map[loc], which=which, **clean_kwargs)


@dataclass(slots=True)
class GridFrame:
    """坐标轴网格样式配置。

    Notes:
        ``GridFrame`` 与 ``AxisFrame`` 独立，前者只负责 ``x/y`` 主次网格线样式，
        后者只负责 spine 与 ``tick_params``。
    """

    params: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_file(cls, path: str | Path) -> "GridFrame":
        """从统一 plotting 配置文件读取网格样式。"""

        payload = load_plotting_section(path, section="grid_frame", fallback_root=True)
        return cls(params=cls._normalize_params(payload))

    def apply(self, ax: Axes) -> None:
        """将网格样式应用到目标 ``Axes``。"""

        params = self.params or {}
        for axis_name in ("x", "y"):
            merged: dict[str, Any] = {}
            frame = params.get("frame")
            if isinstance(frame, Mapping):
                merged.update(frame)
            axis_params = params.get(axis_name)
            if isinstance(axis_params, Mapping):
                merged.update(axis_params)
            if merged:
                self._apply_axis(ax, axis_name=axis_name, params=merged)

    @staticmethod
    def _normalize_params(payload: Mapping[str, Any]) -> dict[str, Any]:
        if "frame" in payload or "x" in payload or "y" in payload:
            return {str(key): value for key, value in payload.items() if isinstance(value, Mapping)}
        return {}

    @staticmethod
    def _apply_axis(ax: Axes, *, axis_name: Literal["x", "y"], params: Mapping[str, Any]) -> None:
        which = str(params.get("which", "major"))
        able = bool(params.get("able", False))
        style = {key: value for key, value in params.items() if key not in {"able", "which"} and value is not None}
        which_values = ("major", "minor") if which == "both" else (which,)
        for which_value in which_values:
            if able:
                ax.grid(visible=True, which=which_value, axis=axis_name, **style)
            else:
                ax.grid(visible=False, which=which_value, axis=axis_name)


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
            return _format_plain_number(round(scaled))
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
    include_zero: bool = False

    def plan(self) -> np.ndarray:
        """生成可读的 major ticks。"""

        lower = float(self.lower)
        upper = float(self.upper)
        if self.include_zero:
            lower = min(lower, 0.0)
            upper = max(upper, 0.0)
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

        if self.include_zero and not np.any(np.isclose(ticks, 0.0, atol=1e-12)):
            ticks = np.sort(np.append(ticks, 0.0))
        return self._normalize_ticks(ticks)

    def plan_segments(self) -> np.ndarray:
        """按指定段数严格等分生成 major ticks。"""

        lower = float(self.lower)
        upper = float(self.upper)
        if self.include_zero:
            lower = min(lower, 0.0)
            upper = max(upper, 0.0)
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
            labels=tuple(_format_plain_number(float(item)) for item in values),
            show_every=show_every,
        )

    def resolved_labels(self) -> tuple[str, ...]:
        """返回根据显示步长稀疏后的标签。"""

        if self.show_every is None or self.show_every <= 1:
            return self.labels
        return tuple(label if idx % self.show_every == 0 else "" for idx, label in enumerate(self.labels))


class LegendHelper:
    """图例收集、过滤、重命名与后处理辅助工具。"""

    def __init__(self, ax: Axes | None = None, *, params: Mapping[str, Any] | None = None) -> None:
        self._ax = ax
        self._params = dict(params or {})

    @classmethod
    def from_file(
        cls,
        path: str | Path,
        *,
        ax: Axes | None = None,
    ) -> "LegendHelper":
        """从统一 plotting 配置文件读取 legend 配置。"""

        payload = load_plotting_section(path, section="legend", fallback_root=False)
        return cls(ax=ax, params=payload)

    @property
    def base_options(self) -> dict[str, Any]:
        """返回 legend 基础配置。"""

        raw = self._params.get("frame", {})
        return dict(raw) if isinstance(raw, Mapping) else {}

    def section_options(self, name: str) -> dict[str, Any]:
        """返回基础配置与指定 section 合并后的 legend 配置。"""

        options = self.base_options
        raw = self._params.get(name, {})
        if isinstance(raw, Mapping):
            options.update(raw)
        return options

    def collect(
        self,
        *,
        ax: Axes | None = None,
        handles: Sequence[Any] | None = None,
        labels: Sequence[str] | None = None,
        exclude_labels: Sequence[str] = ("_nolegend_",),
    ) -> tuple[list[Any], list[str]]:
        """收集当前坐标轴上的可见图例项。"""

        target_ax = self._resolve_ax(ax)
        if handles is None or labels is None:
            resolved_handles, resolved_labels = target_ax.get_legend_handles_labels()
        else:
            resolved_handles, resolved_labels = list(handles), list(labels)
        return self.filter(
            handles=resolved_handles,
            labels=resolved_labels,
            exclude_labels=exclude_labels,
        )

    def rename(
        self,
        labels: Sequence[str],
        *,
        post_renamer: Mapping[str, str] | Callable[[str], str] | None = None,
    ) -> list[str]:
        """对图例文本做后处理重命名。"""

        if post_renamer is None:
            return [str(label) for label in labels]
        if isinstance(post_renamer, Mapping):
            return [str(post_renamer.get(label, label)) for label in labels]
        return [str(post_renamer(str(label))) for label in labels]

    def filter(
        self,
        *,
        handles: Sequence[Any],
        labels: Sequence[str],
        include_labels: Sequence[str] | None = None,
        exclude_labels: Sequence[str] = ("_nolegend_",),
    ) -> tuple[list[Any], list[str]]:
        """按图例文本过滤句柄与标签。"""

        include = set(include_labels) if include_labels is not None else None
        exclude = set(exclude_labels)
        visible_handles: list[Any] = []
        visible_labels: list[str] = []
        for handle, label in zip(handles, labels, strict=True):
            if label in exclude:
                continue
            if include is not None and label not in include:
                continue
            visible_handles.append(handle)
            visible_labels.append(str(label))
        return visible_handles, visible_labels

    def apply(
        self,
        *,
        ax: Axes | None = None,
        handles: Sequence[Any] | None = None,
        labels: Sequence[str] | None = None,
        legend_options: Mapping[str, Any] | None = None,
        section: str | None = None,
        post_renamer: Mapping[str, str] | Callable[[str], str] | None = None,
        include_labels: Sequence[str] | None = None,
        exclude_labels: Sequence[str] = ("_nolegend_",),
        add: bool = False,
    ) -> Legend:
        """创建或更新 legend。"""

        target_ax = self._resolve_ax(ax)
        existing_legend = target_ax.get_legend()
        resolved_handles, resolved_labels = self.collect(
            ax=target_ax,
            handles=handles,
            labels=labels,
            exclude_labels=exclude_labels,
        )
        if include_labels is not None:
            resolved_handles, resolved_labels = self.filter(
                handles=resolved_handles,
                labels=resolved_labels,
                include_labels=include_labels,
                exclude_labels=(),
            )
        if not resolved_handles:
            if existing_legend is not None and not add:
                return existing_legend
            raise ValueError("当前坐标轴上不存在可用于生成 legend 的句柄。")

        renamed_labels = self.rename(resolved_labels, post_renamer=post_renamer)
        options = self.base_options
        if section is not None:
            options.update(self.section_options(section))
        if legend_options is not None:
            options.update(legend_options)
        legend = target_ax.legend(resolved_handles, renamed_labels, **options)
        if add and existing_legend is not None and existing_legend is not legend:
            target_ax.add_artist(existing_legend)
        return legend

    def add(self, **kwargs: Any) -> Legend:
        """在保留已有 legend 的情况下新增一个 legend。"""

        kwargs["add"] = True
        return self.apply(**kwargs)

    def _resolve_ax(self, ax: Axes | None) -> Axes:
        target_ax = ax or self._ax
        if target_ax is None:
            raise ValueError("LegendHelper 尚未绑定 Axes。")
        return target_ax


class AxisHelper:
    """公开数值轴、离散轴与图例辅助工具。"""

    _DEFAULT_SCIENTIFIC_THRESHOLD = (-2, 3)

    def __init__(self, ax: Axes) -> None:
        self._ax = ax

    def format_side(
        self,
        side: AxisSide,
        *,
        mode: AxisFormatMode,
        data: ArrayLike | None = None,
        ticks: Sequence[float] | None = None,
        num_segments: int | None = None,
        tick_min: float | None = None,
        tick_max: float | None = None,
        include_zero: bool | None = None,
        baseline: float | None = None,
        height_ratio: float | None = None,
        decimals: int | None = None,
        trim_trailing_zeros: bool = True,
        scientific: bool | None = None,
        scientific_fontsize: float | None = None,
        scientific_exponent: int | None = None,
        positions: Sequence[float] | None = None,
        labels: Sequence[str] | None = None,
        rotation: float | None = None,
        fontsize: float | None = None,
        show_every: int | None = None,
    ) -> None:
        """按轴边格式化刻度。

        Args:
            side (AxisSide): 目标轴边。
            mode (AxisFormatMode): 格式化模式。连续数值轴使用 ``"continuous"``，
                离散标签轴使用 ``"discrete"``。
            data (ArrayLike | None): 用于推断刻度范围的数据。未提供时会尝试从
                当前 ``Axes`` 上已绘制的 artist 中提取对应轴数据。
            ticks (Sequence[float] | None): 显式 major ticks。提供后优先级最高。
            num_segments (int | None): 连续轴分段数。若为 ``4``，则严格生成 5 个
                等距边界 major ticks。
            tick_min (float | None): 连续轴刻度范围下界。未提供时由数据推断。
            tick_max (float | None): 连续轴刻度范围上界。未提供时由数据推断。
            include_zero (bool | None): 是否强制把 0 纳入连续轴刻度规划范围。
            baseline (float | None): 连续轴基线。与 ``height_ratio`` 配合时，
                显示范围会围绕该基线对称扩展。
            height_ratio (float | None): 连续轴上下留白比例。若未单独通过
                :meth:`set_limits` 指定显示范围，则实际 limits 默认在刻度范围外
                再增加该比例对应的留白。
            decimals (int | None): 连续轴刻度文本的小数位控制。
            trim_trailing_zeros (bool): 是否裁掉多余的尾随零。
            scientific (bool | None): 是否启用科学计数法；``None`` 表示自动判断。
            scientific_fontsize (float | None): 科学计数法指数文本字号。
            scientific_exponent (int | None): 强制指定科学计数法指数。
            positions (Sequence[float] | None): 离散轴刻度位置。
            labels (Sequence[str] | None): 离散轴标签文本。
            rotation (float | None): 离散轴标签旋转角度。
            fontsize (float | None): 离散轴标签字号。
            show_every (int | None): 离散轴标签抽样显示步长。

        Raises:
            ValueError: 当格式化模式不支持，或离散轴缺少必要参数时抛出。
        """

        if mode == "continuous":
            self._format_continuous_side(
                side=side,
                data=data,
                ticks=ticks,
                num_segments=num_segments,
                tick_min=tick_min,
                tick_max=tick_max,
                include_zero=include_zero,
                baseline=baseline,
                height_ratio=height_ratio,
                decimals=decimals,
                trim_trailing_zeros=trim_trailing_zeros,
                scientific=scientific,
                scientific_fontsize=scientific_fontsize,
                scientific_exponent=scientific_exponent,
            )
            return
        if mode == "discrete":
            if positions is None or labels is None:
                raise ValueError("离散轴格式化必须同时提供 positions 和 labels。")
            formatter = DiscreteAxisFormatter(
                positions=tuple(float(item) for item in positions),
                labels=tuple(str(item) for item in labels),
                show_every=show_every,
            )
            self._format_discrete_side(
                side=side,
                formatter=formatter,
                rotation=rotation,
                fontsize=fontsize,
            )
            return
        raise ValueError(f"不支持的轴格式化模式: {mode}")

    def set_limits(
        self,
        *,
        x: tuple[float, float] | None = None,
        y: tuple[float, float] | None = None,
    ) -> None:
        """设置显示范围。"""
        if x is not None:
            self._ax.set_xlim(x)
        if y is not None:
            self._ax.set_ylim(y)

    def set_legend(
        self,
        *,
        legend_options: Mapping[str, Any] | None = None,
        handles: Sequence[Any] | None = None,
        labels: Sequence[str] | None = None,
    ) -> Legend:
        """兼容入口：委托给 ``LegendHelper``。"""

        helper = LegendHelper(self._ax)
        return helper.apply(legend_options=legend_options, handles=handles, labels=labels)

    def _format_continuous_side(
        self,
        *,
        side: AxisSide,
        data: ArrayLike | None,
        ticks: Sequence[float] | None,
        num_segments: int | None,
        tick_min: float | None,
        tick_max: float | None,
        include_zero: bool | None,
        baseline: float | None,
        height_ratio: float | None,
        decimals: int | None,
        trim_trailing_zeros: bool,
        scientific: bool | None,
        scientific_fontsize: float | None,
        scientific_exponent: int | None,
    ) -> None:
        lower_bound, upper_bound = self._resolve_continuous_bounds(
            side=side,
            data=data,
            ticks=ticks,
            tick_min=tick_min,
            tick_max=tick_max,
            include_zero=include_zero,
            baseline=baseline,
            height_ratio=height_ratio,
        )
        resolved_ticks = self._resolve_continuous_ticks(
            side=side,
            data=data,
            ticks=ticks,
            num_segments=num_segments,
            tick_min=lower_bound,
            tick_max=upper_bound,
            include_zero=include_zero,
        )
        display_lower, display_upper = self._resolve_display_bounds(
            tick_lower=lower_bound,
            tick_upper=upper_bound,
            baseline=baseline,
            height_ratio=height_ratio,
        )
        self._set_axis_limits(side=side, lower=display_lower, upper=display_upper)
        scale_factor = self._resolve_scale_factor(resolved_ticks, scientific=scientific)
        if scientific_exponent is not None:
            scale_factor = 10.0**scientific_exponent
        formatter = AxisNumberFormatter(
            scale_factor=scale_factor,
            decimals=decimals,
            trim_trailing_zeros=trim_trailing_zeros,
        )
        axis = self._target_axis(side)
        axis.set_major_locator(FixedLocator(resolved_ticks.tolist()))
        axis.set_major_formatter(formatter)
        self._set_axis_side_visibility(side)
        self._set_offset_position(side)
        axis.get_offset_text().set_visible(not np.isclose(scale_factor, 1.0))
        self._ax.figure.canvas.draw()
        offset_fontsize = scientific_fontsize
        if offset_fontsize is None:
            offset_fontsize = self._tick_label_size(side)
        if offset_fontsize is not None:
            axis.get_offset_text().set_fontsize(offset_fontsize)

    def _format_discrete_side(
        self,
        *,
        side: AxisSide,
        formatter: DiscreteAxisFormatter,
        rotation: float | None,
        fontsize: float | None,
    ) -> None:
        axis = self._target_axis(side)
        axis.set_major_locator(FixedLocator(np.asarray(formatter.positions, dtype=float)))
        axis.set_major_formatter(FixedFormatter(list(formatter.resolved_labels())))
        self._set_axis_side_visibility(side)
        axis.get_offset_text().set_text("")
        axis.get_offset_text().set_visible(False)
        ticklabels = self._ticklabels_for_side(side)
        for tick in ticklabels:
            if rotation is not None:
                tick.set_rotation(rotation)
            if fontsize is not None:
                tick.set_fontsize(fontsize)

    def _resolve_continuous_ticks(
        self,
        *,
        side: AxisSide,
        data: ArrayLike | None,
        ticks: Sequence[float] | None,
        num_segments: int | None,
        tick_min: float | None,
        tick_max: float | None,
        include_zero: bool | None,
    ) -> np.ndarray:
        if ticks is not None:
            values = np.asarray(list(ticks), dtype=float)
            if values.ndim != 1 or values.size == 0:
                raise ValueError("ticks 必须是一维非空数值序列。")
            return values

        source_values = self._coerce_data_or_axis_data(side=side, data=data)
        if source_values.size == 0:
            raise ValueError("无法为连续轴格式化推断有效数据。")
        lower = float(np.nanmin(source_values)) if tick_min is None else float(tick_min)
        upper = float(np.nanmax(source_values)) if tick_max is None else float(tick_max)
        if include_zero:
            lower = min(lower, 0.0)
            upper = max(upper, 0.0)
        if not np.isfinite(lower) or not np.isfinite(upper):
            raise ValueError("连续轴刻度范围必须是有限数值。")
        if lower == upper:
            margin = max(abs(lower) * 0.1, 1.0)
            lower -= margin
            upper += margin
        planner = TickPlanner(
            lower=lower,
            upper=upper,
            target_blocks=num_segments or 5,
            include_zero=bool(include_zero),
        )
        if num_segments is not None:
            return planner.plan_segments()
        return planner.plan()

    def _resolve_continuous_bounds(
        self,
        *,
        side: AxisSide,
        data: ArrayLike | None,
        ticks: Sequence[float] | None,
        tick_min: float | None,
        tick_max: float | None,
        include_zero: bool | None,
        baseline: float | None,
        height_ratio: float | None,
    ) -> tuple[float, float]:
        if ticks is not None:
            values = np.asarray(list(ticks), dtype=float)
        else:
            values = self._coerce_data_or_axis_data(side=side, data=data)
        if values.size == 0:
            raise ValueError("无法为连续轴格式化推断有效数据。")
        lower = float(np.nanmin(values)) if tick_min is None else float(tick_min)
        upper = float(np.nanmax(values)) if tick_max is None else float(tick_max)
        if include_zero:
            lower = min(lower, 0.0)
            upper = max(upper, 0.0)
        if not np.isfinite(lower) or not np.isfinite(upper):
            raise ValueError("连续轴刻度范围必须是有限数值。")
        if lower == upper:
            margin = max(abs(lower) * 0.1, 1.0)
            lower -= margin
            upper += margin
        if baseline is not None and tick_min is None and tick_max is None:
            resolved_baseline = float(baseline)
            extent = max(abs(lower - resolved_baseline), abs(upper - resolved_baseline))
            lower = resolved_baseline - extent
            upper = resolved_baseline + extent
        if lower > upper:
            lower, upper = upper, lower
        return lower, upper

    @staticmethod
    def _resolve_display_bounds(
        *,
        tick_lower: float,
        tick_upper: float,
        baseline: float | None,
        height_ratio: float | None,
    ) -> tuple[float, float]:
        if height_ratio is None:
            return tick_lower, tick_upper
        if height_ratio < 0.0:
            raise ValueError("height_ratio 不能为负数。")
        if baseline is not None:
            resolved_baseline = float(baseline)
            lower_distance = abs(tick_lower - resolved_baseline)
            upper_distance = abs(tick_upper - resolved_baseline)
            if tick_lower < resolved_baseline < tick_upper:
                max_distance = max(lower_distance, upper_distance)
                padded_extent = max_distance * (1.0 + float(height_ratio))
                return resolved_baseline - padded_extent, resolved_baseline + padded_extent
            return (
                tick_lower - lower_distance * float(height_ratio),
                tick_upper + upper_distance * float(height_ratio),
            )
        span = tick_upper - tick_lower
        margin = span * float(height_ratio)
        return tick_lower - margin, tick_upper + margin

    def _coerce_data_or_axis_data(self, *, side: AxisSide, data: ArrayLike | None) -> np.ndarray:
        if data is not None:
            values = np.asarray(data, dtype=float).reshape(-1)
        else:
            values = np.asarray(list(self._iter_axis_data(side)), dtype=float).reshape(-1)
        return values[np.isfinite(values)]

    def _iter_axis_data(self, side: AxisSide) -> Iterable[float]:
        for line in self._ax.lines:
            if side in {"top", "bottom"}:
                yield from np.asarray(line.get_xdata(orig=True), dtype=float).reshape(-1)
            else:
                yield from np.asarray(line.get_ydata(orig=True), dtype=float).reshape(-1)

    def _resolve_scale_factor(self, ticks: np.ndarray, *, scientific: bool | None) -> float:
        max_abs = float(np.nanmax(np.abs(ticks))) if ticks.size else 0.0
        if max_abs <= 0.0:
            return 1.0
        exponent = int(np.floor(np.log10(max_abs)))
        if scientific is False:
            return 1.0
        if scientific is True:
            return 10.0**exponent
        lower_threshold, upper_threshold = self._DEFAULT_SCIENTIFIC_THRESHOLD
        if exponent <= lower_threshold or exponent >= upper_threshold:
            return 10.0**exponent
        return 1.0

    def _set_axis_limits(self, *, side: AxisSide, lower: float, upper: float) -> None:
        if side in {"bottom", "top"}:
            self._ax.set_xlim(lower, upper)
            return
        self._ax.set_ylim(lower, upper)

    def _target_axis(self, side: AxisSide) -> Any:
        return self._ax.xaxis if side in {"top", "bottom"} else self._ax.yaxis

    def _ticklabels_for_side(self, side: AxisSide) -> list[Any]:
        if side in {"bottom", "top"}:
            return list(self._ax.get_xticklabels())
        return list(self._ax.get_yticklabels())

    def _tick_label_size(self, side: AxisSide) -> float | None:
        labels = [label for label in self._ticklabels_for_side(side) if label.get_text()]
        if not labels:
            return None
        return float(labels[0].get_fontsize())

    def _set_axis_side_visibility(self, side: AxisSide) -> None:
        if side == "bottom":
            self._ax.tick_params(axis="x", which="major", labelbottom=True, labeltop=False)
        elif side == "top":
            self._ax.tick_params(axis="x", which="major", labeltop=True, labelbottom=False)
        elif side == "left":
            self._ax.tick_params(axis="y", which="major", labelleft=True, labelright=False)
        else:
            self._ax.tick_params(axis="y", which="major", labelright=True, labelleft=False)

    def _set_offset_position(self, side: AxisSide) -> None:
        axis = self._target_axis(side)
        try:
            axis.set_offset_position(side)
        except AttributeError:
            return


__all__ = [
    "AxisFrame",
    "AxisFormatMode",
    "AxisHelper",
    "AxisNumberFormatter",
    "AxisSide",
    "DiscreteAxisFormatter",
    "GridFrame",
    "LegendHelper",
]
