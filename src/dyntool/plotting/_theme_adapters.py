"""PlotTheme 到 plotting 运行时的适配器。"""

from __future__ import annotations

from typing import Any, Mapping

from ._font_runtime import DEFAULT_FONT_CANDIDATES, font_runtime


def theme_locale_to_rcparams(locale: Mapping[str, Any]) -> dict[str, Any]:
    """将 locale 模板映射到 Matplotlib rcParams。"""

    resolved_sans_serif = font_runtime.resolve_font_candidates(locale.get("sans_serif", DEFAULT_FONT_CANDIDATES))
    return {
        "font.family": locale.get("font_family", "sans-serif"),
        "font.sans-serif": resolved_sans_serif,
        "font.serif": list(resolved_sans_serif),
        "mathtext.fontset": locale.get("math_fontset", "stix"),
        "axes.unicode_minus": bool(locale.get("unicode_minus", False)),
    }


def theme_axes_to_axis_frame_section(axes: Mapping[str, Any]) -> dict[str, Any]:
    """将 axes 模板映射到内部 AxisFrame 配置。"""

    def _side_section(visible: bool) -> dict[str, Any]:
        section: dict[str, Any] = {"spine": {"visible": visible}}
        if not visible:
            section["major"] = {"able": False}
            section["minor"] = {"able": False}
        return section

    return {
        "frame": {
            "spine": {
                "linewidth": float(axes.get("spine_linewidth", 0.8)),
                "color": "black",
                "visible": True,
            },
            "major": {
                "direction": str(axes.get("tick_direction", "in")),
                "length": float(axes.get("tick_length", 3.0)),
                "width": float(axes.get("tick_width", 0.8)),
                "labelsize": 8,
            },
            "minor": {
                "direction": str(axes.get("tick_direction", "in")),
                "length": float(axes.get("minor_tick_length", 2.0)),
                "width": float(axes.get("minor_tick_width", 0.6)),
            },
        },
        "top": _side_section(bool(axes.get("spine_top", False))),
        "bottom": _side_section(bool(axes.get("spine_bottom", True))),
        "left": _side_section(bool(axes.get("spine_left", True))),
        "right": _side_section(bool(axes.get("spine_right", False))),
    }


def theme_grid_to_grid_frame_section(grid: Mapping[str, Any]) -> dict[str, Any]:
    """将 grid 模板映射到内部 GridFrame 配置。"""

    normalized: dict[str, Any] = {}
    for axis_name in ("x", "y"):
        axis_section = grid.get(axis_name, {})
        if not isinstance(axis_section, Mapping):
            continue
        normalized[axis_name] = {}
        for level in ("major", "minor"):
            level_section = axis_section.get(level, {})
            if not isinstance(level_section, Mapping):
                continue
            normalized[axis_name][level] = {
                "able": bool(level_section.get("enabled", False)),
                "linewidth": float(level_section.get("linewidth", 0.5)),
                "color": str(level_section.get("color", "#d0d0d0")),
                "linestyle": str(level_section.get("linestyle", "--")),
                "alpha": 0.7,
                "zorder": 0,
            }
    return normalized


__all__ = [
    "theme_axes_to_axis_frame_section",
    "theme_grid_to_grid_frame_section",
    "theme_locale_to_rcparams",
]
