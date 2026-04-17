"""绘图模板配置。"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

import matplotlib.pyplot as plt

from ..config import read_config_file

_DEFAULT_FONT_CANDIDATES = [
    "SongTNR",
    "Microsoft YaHei",
    "SimHei",
    "KaiTi",
    "NSimSun",
]
_DEFAULT_FIGURE_RECT = (0.12, 0.14, 0.82, 0.78)
_ALLOWED_THEME_TOP_LEVEL_KEYS = {"locale", "figure", "axes", "artist", "legend"}
_ALLOWED_LOCALE_KEYS = {"font_family", "sans_serif", "math_fontset", "unicode_minus"}
_ALLOWED_FIGURE_KEYS = {"width_cm", "height_cm", "dpi", "add_axes_rect"}
_ALLOWED_AXES_KEYS = {
    "spine_top",
    "spine_bottom",
    "spine_left",
    "spine_right",
    "spine_linewidth",
    "tick_length",
    "tick_width",
    "minor_tick_length",
    "minor_tick_width",
    "tick_direction",
    "grid_linewidth",
}
_ALLOWED_ARTIST_METHODS = {"plot", "scatter", "axhline", "fill_between"}
_ALLOWED_ARTIST_KEYS = {
    "plot": {"linewidth", "linestyle", "markersize", "color", "marker", "alpha"},
    "scatter": {"s", "color", "marker", "alpha"},
    "axhline": {"linestyle", "linewidth", "color", "alpha"},
    "fill_between": {"color", "alpha", "linewidth", "linestyle"},
}
_ALLOWED_LEGEND_KEYS = {"loc", "fontsize", "frameon", "ncol"}


def _raise_unknown_keys(message: str, unknown_keys: set[str]) -> None:
    unknown = "、".join(sorted(unknown_keys))
    raise ValueError(f"{message}: {unknown}")


def _validate_allowed_keys(payload: Mapping[str, Any], *, allowed: set[str], message: str) -> None:
    unknown = {str(key) for key in payload.keys() if str(key) not in allowed}
    if unknown:
        _raise_unknown_keys(message, unknown)


def _coerce_str(value: Any, *, path: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{path} 必须为字符串。")
    return value


def _coerce_bool(value: Any, *, path: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{path} 必须为布尔值。")
    return value


def _coerce_float(value: Any, *, path: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"{path} 必须为数字。")
    return float(value)


def _coerce_int(value: Any, *, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"{path} 必须为整数。")
    return int(value)


def _coerce_float_sequence(value: Any, *, path: str, expected_size: int) -> tuple[float, ...]:
    if not isinstance(value, list | tuple) or len(value) != expected_size:
        raise ValueError(f"{path} 必须为长度为 {expected_size} 的数字序列。")
    normalized: list[float] = []
    for item in value:
        normalized.append(_coerce_float(item, path=path))
    return tuple(normalized)


def _coerce_string_list(value: Any, *, path: str) -> list[str]:
    if isinstance(value, str):
        return [value]
    if not isinstance(value, list | tuple):
        raise ValueError(f"{path} 必须为字符串列表。")
    normalized: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise ValueError(f"{path} 必须为字符串列表。")
        normalized.append(item)
    return normalized


def _normalize_locale(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    raw = payload or {}
    _validate_allowed_keys(raw, allowed=_ALLOWED_LOCALE_KEYS, message="locale 存在未支持的字段")
    return {
        "font_family": _coerce_str(raw.get("font_family", "sans-serif"), path="locale.font_family"),
        "sans_serif": _coerce_string_list(raw.get("sans_serif", _DEFAULT_FONT_CANDIDATES), path="locale.sans_serif"),
        "math_fontset": _coerce_str(raw.get("math_fontset", "stix"), path="locale.math_fontset"),
        "unicode_minus": _coerce_bool(raw.get("unicode_minus", False), path="locale.unicode_minus"),
    }


def _normalize_figure(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    raw = payload or {}
    _validate_allowed_keys(raw, allowed=_ALLOWED_FIGURE_KEYS, message="figure 存在未支持的字段")
    return {
        "width_cm": _coerce_float(raw.get("width_cm", 14.0), path="figure.width_cm"),
        "height_cm": _coerce_float(raw.get("height_cm", 10.0), path="figure.height_cm"),
        "dpi": _coerce_int(raw.get("dpi", 150), path="figure.dpi"),
        "add_axes_rect": _coerce_float_sequence(
            raw.get("add_axes_rect", _DEFAULT_FIGURE_RECT),
            path="figure.add_axes_rect",
            expected_size=4,
        ),
    }


def _normalize_axes(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    raw = payload or {}
    _validate_allowed_keys(raw, allowed=_ALLOWED_AXES_KEYS, message="axes 存在未支持的字段")
    return {
        "spine_top": _coerce_bool(raw.get("spine_top", False), path="axes.spine_top"),
        "spine_bottom": _coerce_bool(raw.get("spine_bottom", True), path="axes.spine_bottom"),
        "spine_left": _coerce_bool(raw.get("spine_left", True), path="axes.spine_left"),
        "spine_right": _coerce_bool(raw.get("spine_right", False), path="axes.spine_right"),
        "spine_linewidth": _coerce_float(raw.get("spine_linewidth", 0.8), path="axes.spine_linewidth"),
        "tick_length": _coerce_float(raw.get("tick_length", 3.0), path="axes.tick_length"),
        "tick_width": _coerce_float(raw.get("tick_width", 0.8), path="axes.tick_width"),
        "minor_tick_length": _coerce_float(raw.get("minor_tick_length", 2.0), path="axes.minor_tick_length"),
        "minor_tick_width": _coerce_float(raw.get("minor_tick_width", 0.6), path="axes.minor_tick_width"),
        "tick_direction": _coerce_str(raw.get("tick_direction", "in"), path="axes.tick_direction"),
        "grid_linewidth": _coerce_float(raw.get("grid_linewidth", 0.5), path="axes.grid_linewidth"),
    }


def _normalize_artist(payload: Mapping[str, Any] | None) -> dict[str, dict[str, Any]]:
    raw = payload or {}
    _validate_allowed_keys(raw, allowed=_ALLOWED_ARTIST_METHODS, message="artist 存在未支持的方法块")
    normalized: dict[str, dict[str, Any]] = {}
    for method_name in ("plot", "scatter", "axhline", "fill_between"):
        section = raw.get(method_name, {})
        if not isinstance(section, Mapping):
            continue
        _validate_allowed_keys(
            section,
            allowed=_ALLOWED_ARTIST_KEYS[method_name],
            message=f"artist.{method_name} 存在未支持的字段",
        )
        normalized[method_name] = {str(key): value for key, value in section.items()}
    return normalized


def _normalize_legend(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    raw = payload or {}
    _validate_allowed_keys(raw, allowed=_ALLOWED_LEGEND_KEYS, message="legend 存在未支持的字段")
    return {
        "loc": _coerce_str(raw.get("loc", "best"), path="legend.loc"),
        "fontsize": _coerce_float(raw.get("fontsize", 9), path="legend.fontsize"),
        "frameon": _coerce_bool(raw.get("frameon", False), path="legend.frameon"),
        "ncol": _coerce_int(raw.get("ncol", 1), path="legend.ncol"),
    }


def _theme_to_locale_rcparams(locale: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "font.family": locale.get("font_family", "sans-serif"),
        "font.sans-serif": list(locale.get("sans_serif", _DEFAULT_FONT_CANDIDATES)),
        "mathtext.fontset": locale.get("math_fontset", "stix"),
        "axes.unicode_minus": bool(locale.get("unicode_minus", False)),
    }


def _theme_to_axis_frame_section(axes: Mapping[str, Any]) -> dict[str, Any]:
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
        "top": {"spine": {"visible": bool(axes.get("spine_top", False))}},
        "bottom": {"spine": {"visible": bool(axes.get("spine_bottom", True))}},
        "left": {"spine": {"visible": bool(axes.get("spine_left", True))}},
        "right": {"spine": {"visible": bool(axes.get("spine_right", False))}},
    }


def _theme_to_grid_frame_section(axes: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "frame": {
            "able": False,
            "which": "major",
            "linewidth": float(axes.get("grid_linewidth", 0.5)),
            "color": "#d0d0d0",
            "linestyle": "--",
            "alpha": 0.7,
            "zorder": 0,
        }
    }


@lru_cache(maxsize=32)
def _read_plotting_payload_cached(path_str: str) -> dict[str, Any]:
    payload = read_config_file(Path(path_str))
    if not isinstance(payload, Mapping):
        raise TypeError("绘图配置必须解析为字典。")
    return deepcopy(dict(payload))


def _read_plotting_payload(path: str | Path) -> dict[str, Any]:
    return deepcopy(_read_plotting_payload_cached(str(Path(path).resolve())))


@dataclass(slots=True)
class PlotTheme:
    """轻量图模板底座。"""

    locale: dict[str, Any] = field(default_factory=dict)
    figure: dict[str, Any] = field(default_factory=dict)
    axes: dict[str, Any] = field(default_factory=dict)
    artist: dict[str, dict[str, Any]] = field(default_factory=dict)
    legend: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def default(cls) -> PlotTheme:
        """返回内置中文静态报告模板。"""

        return cls(
            locale=_normalize_locale(None),
            figure=_normalize_figure(None),
            axes=_normalize_axes(None),
            artist=_normalize_artist(
                {
                    "plot": {
                        "linewidth": 1.2,
                        "linestyle": "-",
                        "markersize": 4.0,
                        "color": "#4c72b0",
                        "marker": "None",
                        "alpha": 1.0,
                    },
                    "scatter": {
                        "s": 16.0,
                        "color": "#4c72b0",
                        "marker": "o",
                        "alpha": 1.0,
                    },
                    "axhline": {
                        "linestyle": "--",
                        "linewidth": 1.0,
                        "color": "gray",
                        "alpha": 1.0,
                    },
                    "fill_between": {
                        "color": "#4c72b0",
                        "alpha": 0.2,
                        "linewidth": 0.0,
                        "linestyle": "-",
                    },
                }
            ),
            legend=_normalize_legend(None),
        )

    @classmethod
    def from_file(cls, path: str | Path) -> PlotTheme:
        """从配置文件读取图模板。"""

        payload = _read_plotting_payload(path)
        _validate_allowed_keys(
            payload, allowed=_ALLOWED_THEME_TOP_LEVEL_KEYS, message="PlotTheme 配置存在未支持的顶层块"
        )
        return cls(
            locale=_normalize_locale(payload.get("locale") if isinstance(payload.get("locale"), Mapping) else None),
            figure=_normalize_figure(payload.get("figure") if isinstance(payload.get("figure"), Mapping) else None),
            axes=_normalize_axes(payload.get("axes") if isinstance(payload.get("axes"), Mapping) else None),
            artist=_normalize_artist(payload.get("artist") if isinstance(payload.get("artist"), Mapping) else None),
            legend=_normalize_legend(payload.get("legend") if isinstance(payload.get("legend"), Mapping) else None),
        )

    def figure_options(self) -> dict[str, Any]:
        """返回 figure 底座配置。"""

        return {
            "width_cm": float(self.figure["width_cm"]),
            "height_cm": float(self.figure["height_cm"]),
            "dpi": int(self.figure["dpi"]),
            "add_axes_rect": tuple(self.figure["add_axes_rect"]),
        }

    def artist_options(self, method_name: str) -> dict[str, Any]:
        """返回指定 ``Axes`` 方法的默认样式参数。"""

        return dict(self.artist.get(method_name, {}))

    def legend_options(self) -> dict[str, Any]:
        """返回 legend 默认参数。"""

        return dict(self.legend)

    def _build_axis_frame(self) -> Any:
        """返回当前模板对应的内部 ``AxisFrame``。"""

        from ._axes_frame import AxisFrame

        return AxisFrame(params=_theme_to_axis_frame_section(self.axes))

    def _build_grid_frame(self) -> Any:
        """返回当前模板对应的内部 ``GridFrame``。"""

        from ._axes_frame import GridFrame

        return GridFrame(params=_theme_to_grid_frame_section(self.axes))

    def apply_matplotlib(self, update_fields: Mapping[str, Any] | None = None) -> str | None:
        """应用 locale 对应的 ``rcParams`` 底座。"""

        rc_params = _theme_to_locale_rcparams(self.locale)
        if update_fields is not None:
            rc_params.update(dict(update_fields))
        plt.rcParams.update(rc_params)
        fonts = rc_params.get("font.sans-serif", [])
        if isinstance(fonts, list) and fonts:
            return str(fonts[0])
        return None


__all__ = ["PlotTheme"]
