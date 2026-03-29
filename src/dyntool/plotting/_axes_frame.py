"""plotting 坐标轴边框与网格样式实现。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Mapping

from matplotlib.axes import Axes

from .config import load_plotting_section


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
    """坐标轴网格样式配置。"""

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
