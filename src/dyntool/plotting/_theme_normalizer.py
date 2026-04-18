"""PlotTheme 配置归一化。"""

from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

from ..config import read_config_file
from ._font_runtime import DEFAULT_FONT_CANDIDATES
from .axis_config import AxisConfig, parse_axis_config

DEFAULT_FIGURE_RECT = (0.12, 0.14, 0.82, 0.78)
ALLOWED_THEME_TOP_LEVEL_KEYS = {"locale", "figure", "axes", "artist", "legend", "grid", "axis"}
_ALLOWED_LOCALE_KEYS = {"font_family", "sans_serif", "math_fontset", "unicode_minus"}
_ALLOWED_FIGURE_KEYS = {"width_cm", "height_cm", "dpi", "add_axes_rect"}
_ALLOWED_AXES_KEYS = {"spines", "ticks"}
_ALLOWED_SPINES_KEYS = {"top", "bottom", "left", "right", "linewidth"}
_ALLOWED_TICKS_KEYS = {"direction", "major", "minor"}
_ALLOWED_TICK_STYLE_KEYS = {"length", "width"}
_ALLOWED_ARTIST_METHODS = {"plot", "scatter", "axhline", "fill_between"}
_ALLOWED_ARTIST_KEYS = {
    "plot": {"linewidth", "linestyle", "markersize", "color", "marker", "alpha"},
    "scatter": {"s", "color", "marker", "alpha"},
    "axhline": {"linestyle", "linewidth", "color", "alpha"},
    "fill_between": {"color", "alpha", "linewidth", "linestyle"},
}
_ALLOWED_LEGEND_KEYS = {"loc", "fontsize", "frameon", "ncol"}
_ALLOWED_GRID_AXIS_KEYS = {"major", "minor"}
_ALLOWED_GRID_LEVEL_KEYS = {"enabled", "color", "linestyle", "linewidth"}
_ALLOWED_AXIS_KEYS = {"x", "y"}
_ALLOWED_AXIS_SIDE_KEYS = {"kind", "label", "ticks", "limits", "formatter"}
_ALLOWED_AXIS_LABEL_KEYS = {"text", "pad"}


class _ThemeSchemaParser:
    """收拢 PlotTheme schema 的归一化与校验逻辑。"""

    def validate_theme_top_level_keys(self, payload: Mapping[str, Any]) -> None:
        self._validate_allowed_keys(
            payload,
            allowed=ALLOWED_THEME_TOP_LEVEL_KEYS,
            message="PlotTheme 配置存在未支持的顶层块",
        )

    def mapping_section(self, payload: Mapping[str, Any], key: str) -> Mapping[str, Any] | None:
        """返回可选的 mapping 型配置块。"""

        value = payload.get(key)
        if value is None:
            return None
        if not isinstance(value, Mapping):
            raise ValueError(f"{key} 必须为映射。")
        return value

    def build_theme(self, payload: Mapping[str, Any], *, default_artist: Mapping[str, Any]) -> Any:
        """从已加载的配置负载组装 ``PlotTheme``。"""

        from .config import PlotTheme

        axis_payload = self.mapping_section(payload, "axis")
        artist_payload = self.mapping_section(payload, "artist")
        return PlotTheme(
            locale=self.normalize_locale(self.mapping_section(payload, "locale")),
            figure=self.normalize_figure(self.mapping_section(payload, "figure")),
            axes=self.normalize_axes(self.mapping_section(payload, "axes")),
            grid=self.normalize_grid(self.mapping_section(payload, "grid")),
            artist=self.normalize_artist(artist_payload if artist_payload is not None else default_artist),
            legend=self.normalize_legend(self.mapping_section(payload, "legend")),
            axis_labels=self.normalize_axis_labels(axis_payload),
            axis_config=self.normalize_axis_config(axis_payload),
        )

    def normalize_locale(self, payload: Mapping[str, Any] | None) -> dict[str, Any]:
        raw = payload or {}
        self._validate_allowed_keys(raw, allowed=_ALLOWED_LOCALE_KEYS, message="locale 存在未支持的字段")
        return {
            "font_family": self._coerce_str(raw.get("font_family", "sans-serif"), path="locale.font_family"),
            "sans_serif": self._coerce_string_list(
                raw.get("sans_serif", DEFAULT_FONT_CANDIDATES),
                path="locale.sans_serif",
            ),
            "math_fontset": self._coerce_str(raw.get("math_fontset", "stix"), path="locale.math_fontset"),
            "unicode_minus": self._coerce_bool(raw.get("unicode_minus", False), path="locale.unicode_minus"),
        }

    def normalize_figure(self, payload: Mapping[str, Any] | None) -> dict[str, Any]:
        raw = payload or {}
        self._validate_allowed_keys(raw, allowed=_ALLOWED_FIGURE_KEYS, message="figure 存在未支持的字段")
        return {
            "width_cm": self._coerce_float(raw.get("width_cm", 14.0), path="figure.width_cm"),
            "height_cm": self._coerce_float(raw.get("height_cm", 10.0), path="figure.height_cm"),
            "dpi": self._coerce_int(raw.get("dpi", 150), path="figure.dpi"),
            "add_axes_rect": self._coerce_float_sequence(
                raw.get("add_axes_rect", DEFAULT_FIGURE_RECT),
                path="figure.add_axes_rect",
                expected_size=4,
            ),
        }

    def normalize_axes(self, payload: Mapping[str, Any] | None) -> dict[str, Any]:
        raw = payload or {}
        self._validate_allowed_keys(raw, allowed=_ALLOWED_AXES_KEYS, message="axes 存在未支持的字段")
        spines = self._mapping_or_empty(raw.get("spines"), path="axes.spines")
        ticks = self._mapping_or_empty(raw.get("ticks"), path="axes.ticks")
        major = self._mapping_or_empty(ticks.get("major"), path="axes.ticks.major")
        minor = self._mapping_or_empty(ticks.get("minor"), path="axes.ticks.minor")
        self._validate_allowed_keys(spines, allowed=_ALLOWED_SPINES_KEYS, message="axes.spines 存在未支持的字段")
        self._validate_allowed_keys(ticks, allowed=_ALLOWED_TICKS_KEYS, message="axes.ticks 存在未支持的字段")
        self._validate_allowed_keys(
            major, allowed=_ALLOWED_TICK_STYLE_KEYS, message="axes.ticks.major 存在未支持的字段"
        )
        self._validate_allowed_keys(
            minor, allowed=_ALLOWED_TICK_STYLE_KEYS, message="axes.ticks.minor 存在未支持的字段"
        )
        return {
            "spine_top": self._coerce_bool(spines.get("top", False), path="axes.spines.top"),
            "spine_bottom": self._coerce_bool(spines.get("bottom", True), path="axes.spines.bottom"),
            "spine_left": self._coerce_bool(spines.get("left", True), path="axes.spines.left"),
            "spine_right": self._coerce_bool(spines.get("right", False), path="axes.spines.right"),
            "spine_linewidth": self._coerce_float(spines.get("linewidth", 0.8), path="axes.spines.linewidth"),
            "tick_direction": self._coerce_str(ticks.get("direction", "in"), path="axes.ticks.direction"),
            "tick_length": self._coerce_float(major.get("length", 3.0), path="axes.ticks.major.length"),
            "tick_width": self._coerce_float(major.get("width", 0.8), path="axes.ticks.major.width"),
            "minor_tick_length": self._coerce_float(minor.get("length", 2.0), path="axes.ticks.minor.length"),
            "minor_tick_width": self._coerce_float(minor.get("width", 0.6), path="axes.ticks.minor.width"),
        }

    def normalize_grid(self, payload: Mapping[str, Any] | None) -> dict[str, dict[str, dict[str, Any]]]:
        raw = payload or {}
        self._validate_allowed_keys(raw, allowed={"x", "y"}, message="grid 存在未支持的字段")
        normalized: dict[str, dict[str, dict[str, Any]]] = {}
        for axis_name in ("x", "y"):
            axis_payload = self._mapping_or_empty(raw.get(axis_name), path=f"grid.{axis_name}")
            self._validate_allowed_keys(
                axis_payload,
                allowed=_ALLOWED_GRID_AXIS_KEYS,
                message=f"grid.{axis_name} 存在未支持的字段",
            )
            axis_levels: dict[str, dict[str, Any]] = {}
            for level in ("major", "minor"):
                level_payload = self._mapping_or_empty(axis_payload.get(level), path=f"grid.{axis_name}.{level}")
                self._validate_allowed_keys(
                    level_payload,
                    allowed=_ALLOWED_GRID_LEVEL_KEYS,
                    message=f"grid.{axis_name}.{level} 存在未支持的字段",
                )
                axis_levels[level] = {
                    "enabled": self._coerce_bool(
                        level_payload.get("enabled", False),
                        path=f"grid.{axis_name}.{level}.enabled",
                    ),
                    "color": self._coerce_str(
                        level_payload.get("color", "#d0d0d0"),
                        path=f"grid.{axis_name}.{level}.color",
                    ),
                    "linestyle": self._coerce_str(
                        level_payload.get("linestyle", "--"),
                        path=f"grid.{axis_name}.{level}.linestyle",
                    ),
                    "linewidth": self._coerce_float(
                        level_payload.get("linewidth", 0.5),
                        path=f"grid.{axis_name}.{level}.linewidth",
                    ),
                }
            normalized[axis_name] = axis_levels
        return normalized

    def normalize_artist(self, payload: Mapping[str, Any] | None) -> dict[str, dict[str, Any]]:
        raw = payload or {}
        self._validate_allowed_keys(raw, allowed=_ALLOWED_ARTIST_METHODS, message="artist 存在未支持的方法块")
        normalized: dict[str, dict[str, Any]] = {}
        for method_name in ("plot", "scatter", "axhline", "fill_between"):
            section = raw.get(method_name, {})
            if not isinstance(section, Mapping):
                continue
            self._validate_allowed_keys(
                section,
                allowed=_ALLOWED_ARTIST_KEYS[method_name],
                message=f"artist.{method_name} 存在未支持的字段",
            )
            normalized[method_name] = {str(key): value for key, value in section.items()}
        return normalized

    def normalize_legend(self, payload: Mapping[str, Any] | None) -> dict[str, Any]:
        raw = payload or {}
        self._validate_allowed_keys(raw, allowed=_ALLOWED_LEGEND_KEYS, message="legend 存在未支持的字段")
        return {
            "loc": self._coerce_str(raw.get("loc", "best"), path="legend.loc"),
            "fontsize": self._coerce_float(raw.get("fontsize", 9), path="legend.fontsize"),
            "frameon": self._coerce_bool(raw.get("frameon", False), path="legend.frameon"),
            "ncol": self._coerce_int(raw.get("ncol", 1), path="legend.ncol"),
        }

    def normalize_axis_labels(self, payload: Mapping[str, Any] | None) -> dict[str, dict[str, Any]]:
        raw = payload or {}
        self._validate_allowed_keys(raw, allowed=_ALLOWED_AXIS_KEYS, message="axis 存在未支持的字段")
        normalized: dict[str, dict[str, Any]] = {}
        for side in ("x", "y"):
            section = self._mapping_or_empty(raw.get(side), path=f"axis.{side}")
            self._validate_allowed_keys(
                section,
                allowed=_ALLOWED_AXIS_SIDE_KEYS,
                message=f"axis.{side} 存在未支持的字段",
            )
            label = section.get("label")
            if label is None:
                continue
            label_mapping = self._mapping_or_empty(label, path=f"axis.{side}.label")
            self._validate_allowed_keys(
                label_mapping,
                allowed=_ALLOWED_AXIS_LABEL_KEYS,
                message=f"axis.{side}.label 存在未支持的字段",
            )
            normalized[side] = {
                "text": self._coerce_str(label_mapping.get("text", ""), path=f"axis.{side}.label.text"),
                "pad": self._coerce_float(label_mapping.get("pad", 0.0), path=f"axis.{side}.label.pad"),
            }
        return normalized

    def normalize_axis_config(self, payload: Mapping[str, Any] | None) -> AxisConfig | None:
        return parse_axis_config(payload)

    def _mapping_or_empty(self, value: object, *, path: str) -> Mapping[str, Any]:
        if value is None:
            return {}
        if not isinstance(value, Mapping):
            raise ValueError(f"{path} 必须为映射。")
        return value

    def _raise_unknown_keys(self, message: str, unknown_keys: set[str]) -> None:
        unknown = "、".join(sorted(unknown_keys))
        raise ValueError(f"{message}: {unknown}")

    def _validate_allowed_keys(self, payload: Mapping[str, Any], *, allowed: set[str], message: str) -> None:
        unknown = {str(key) for key in payload.keys() if str(key) not in allowed}
        if unknown:
            self._raise_unknown_keys(message, unknown)

    def _coerce_str(self, value: Any, *, path: str) -> str:
        if not isinstance(value, str):
            raise ValueError(f"{path} 必须为字符串。")
        return value

    def _coerce_bool(self, value: Any, *, path: str) -> bool:
        if not isinstance(value, bool):
            raise ValueError(f"{path} 必须为布尔值。")
        return value

    def _coerce_float(self, value: Any, *, path: str) -> float:
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise ValueError(f"{path} 必须为数字。")
        return float(value)

    def _coerce_int(self, value: Any, *, path: str) -> int:
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise ValueError(f"{path} 必须为整数。")
        return int(value)

    def _coerce_float_sequence(self, value: Any, *, path: str, expected_size: int) -> tuple[float, ...]:
        if not isinstance(value, list | tuple) or len(value) != expected_size:
            raise ValueError(f"{path} 必须为长度为 {expected_size} 的数字序列。")
        return tuple(self._coerce_float(item, path=path) for item in value)

    def _coerce_string_list(self, value: Any, *, path: str) -> list[str]:
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


THEME_SCHEMA = _ThemeSchemaParser()


@lru_cache(maxsize=32)
def _read_plotting_payload_cached(path_str: str) -> dict[str, Any]:
    payload = read_config_file(Path(path_str))
    if not isinstance(payload, Mapping):
        raise TypeError("绘图配置必须解析为字典。")
    return deepcopy(dict(payload))


def read_plotting_payload(path: str | Path) -> dict[str, Any]:
    """读取并缓存 PlotTheme 配置文件。"""

    return deepcopy(_read_plotting_payload_cached(str(Path(path).resolve())))


__all__ = ["THEME_SCHEMA", "read_plotting_payload"]
