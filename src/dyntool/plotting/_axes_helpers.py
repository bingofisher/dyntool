"""plotting 图例与修轴辅助实现。"""

from __future__ import annotations

from typing import Any, Callable, Iterable, Mapping, Sequence

import numpy as np
from matplotlib.axes import Axes
from matplotlib.legend import Legend
from matplotlib.ticker import FixedFormatter, FixedLocator, MultipleLocator
from numpy.typing import ArrayLike

from ._axes_common import AxisFormatMode, AxisSide
from ._axes_formatters import AxisNumberFormatter, DiscreteAxisFormatter, TickPlanner


class LegendHelper:
    """图例收集、过滤、重命名与后处理辅助工具。"""

    def __init__(self, ax: Axes | None = None, *, params: Mapping[str, Any] | None = None) -> None:
        self._ax = ax
        self._params = dict(params or {})

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

    def format_axis(
        self,
        side: AxisSide,
        *,
        mode: AxisFormatMode,
        data: ArrayLike | None = None,
        ticks: Sequence[float] | None = None,
        major_step: float | None = None,
        num_segments: int | None = None,
        tick_min: float | None = None,
        tick_max: float | None = None,
        minor_step: float | None = None,
        include_zero: bool | None = None,
        baseline: float | None = None,
        height_ratio: float | None = None,
        decimals: int | None = None,
        trim_trailing_zeros: bool = True,
        scientific: bool | None = None,
        scientific_fontsize: float | None = None,
        scientific_exponent: int | None = None,
        scientific_offset_x: float | None = None,
        scientific_offset_y: float | None = None,
        positions: Sequence[float] | None = None,
        labels: Sequence[str] | None = None,
        rotation: float | None = None,
        fontsize: float | None = None,
        show_every: int | None = None,
    ) -> None:
        """按轴边格式化刻度。"""

        if mode == "continuous":
            self._format_continuous_side(
                side=side,
                data=data,
                ticks=ticks,
                major_step=major_step,
                num_segments=num_segments,
                tick_min=tick_min,
                tick_max=tick_max,
                minor_step=minor_step,
                include_zero=include_zero,
                baseline=baseline,
                height_ratio=height_ratio,
                decimals=decimals,
                trim_trailing_zeros=trim_trailing_zeros,
                scientific=scientific,
                scientific_fontsize=scientific_fontsize,
                scientific_exponent=scientific_exponent,
                scientific_offset_x=scientific_offset_x,
                scientific_offset_y=scientific_offset_y,
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
        major_step: float | None,
        num_segments: int | None,
        tick_min: float | None,
        tick_max: float | None,
        minor_step: float | None,
        include_zero: bool | None,
        baseline: float | None,
        height_ratio: float | None,
        decimals: int | None,
        trim_trailing_zeros: bool,
        scientific: bool | None,
        scientific_fontsize: float | None,
        scientific_exponent: int | None,
        scientific_offset_x: float | None,
        scientific_offset_y: float | None,
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
            major_step=major_step,
            num_segments=num_segments,
            tick_min=tick_min,
            tick_max=tick_max,
            resolved_tick_min=lower_bound,
            resolved_tick_max=upper_bound,
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
        if minor_step is not None:
            axis.set_minor_locator(MultipleLocator(float(minor_step)))
        self._set_axis_side_visibility(side)
        self._set_offset_position(side)
        axis.get_offset_text().set_visible(not np.isclose(scale_factor, 1.0))
        self._ax.figure.canvas.draw()
        offset_fontsize = scientific_fontsize
        if offset_fontsize is None:
            offset_fontsize = self._tick_label_size(side)
        if offset_fontsize is not None:
            axis.get_offset_text().set_fontsize(offset_fontsize)
        if scientific_offset_x is not None or scientific_offset_y is not None:
            self._bind_offset_text_position(
                axis=axis,
                x=scientific_offset_x,
                y=scientific_offset_y,
            )

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
        major_step: float | None,
        num_segments: int | None,
        tick_min: float | None,
        tick_max: float | None,
        resolved_tick_min: float | None,
        resolved_tick_max: float | None,
        include_zero: bool | None,
    ) -> np.ndarray:
        if ticks is not None:
            values = np.asarray(list(ticks), dtype=float)
            if values.ndim != 1 or values.size == 0:
                raise ValueError("ticks 必须是一维非空数值序列。")
            return values
        if major_step is not None:
            if major_step <= 0.0:
                raise ValueError("major_step 必须大于 0。")
            return self._build_step_ticks(
                lower=float(tick_min) if tick_min is not None else None,
                upper=float(tick_max) if tick_max is not None else None,
                resolved_lower=float(resolved_tick_min) if resolved_tick_min is not None else None,
                resolved_upper=float(resolved_tick_max) if resolved_tick_max is not None else None,
                data=self._coerce_data_or_axis_data(side=side, data=data),
                step=float(major_step),
                include_zero=bool(include_zero),
            )

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

    @staticmethod
    def _build_step_ticks(
        *,
        lower: float | None,
        upper: float | None,
        resolved_lower: float | None,
        resolved_upper: float | None,
        data: np.ndarray,
        step: float,
        include_zero: bool,
    ) -> np.ndarray:
        if data.size == 0 and (resolved_lower is None or resolved_upper is None):
            raise ValueError("无法在缺少有效数据和显式边界时按 major_step 规划刻度。")
        computed_lower = float(np.nanmin(data)) if resolved_lower is None else float(resolved_lower)
        computed_upper = float(np.nanmax(data)) if resolved_upper is None else float(resolved_upper)
        if include_zero:
            computed_lower = min(computed_lower, 0.0)
            computed_upper = max(computed_upper, 0.0)
        if computed_lower == computed_upper:
            margin = max(abs(computed_lower) * 0.1, step)
            computed_lower -= margin
            computed_upper += margin
        if computed_lower > computed_upper:
            computed_lower, computed_upper = computed_upper, computed_lower

        start = float(lower) if lower is not None else np.floor(computed_lower / step) * step
        end = float(upper) if upper is not None else np.ceil(computed_upper / step) * step
        values = np.arange(start, end + step * 0.5, step, dtype=float)
        if values.size == 0:
            return np.asarray([start, end], dtype=float)
        if upper is not None and not np.isclose(values[-1], end):
            values = values[values < end]
            values = np.append(values, end)
        return values

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

    def _bind_offset_text_position(
        self,
        *,
        axis: Any,
        x: float | None,
        y: float | None,
    ) -> None:
        text = axis.get_offset_text()

        def _apply_position() -> None:
            current_x, current_y = text.get_position()
            text.set_position(
                (
                    float(x) if x is not None else float(current_x),
                    float(y) if y is not None else float(current_y),
                )
            )

        _apply_position()
        canvas = self._ax.figure.canvas
        existing_cid = getattr(text, "_dyntool_offset_draw_cid", None)
        if existing_cid is not None:
            try:
                canvas.mpl_disconnect(existing_cid)
            except ValueError:
                pass
        cid = canvas.mpl_connect("draw_event", lambda _event: _apply_position())
        setattr(text, "_dyntool_offset_draw_cid", cid)
