"""绘图模板配置。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

import matplotlib.pyplot as plt

from ._font_runtime import font_runtime
from ._theme_adapters import (
    theme_axes_to_axis_frame_section,
    theme_grid_to_grid_frame_section,
    theme_locale_to_rcparams,
)
from ._theme_normalizer import THEME_SCHEMA, read_plotting_payload
from .axis_config import AxisConfig

_DEFAULT_ARTIST_THEME = {
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


@dataclass(slots=True)
class PlotTheme:
    """轻量图模板底座。"""

    locale: dict[str, Any] = field(default_factory=dict)
    figure: dict[str, Any] = field(default_factory=dict)
    axes: dict[str, Any] = field(default_factory=dict)
    grid: dict[str, dict[str, dict[str, Any]]] = field(default_factory=dict)
    artist: dict[str, dict[str, Any]] = field(default_factory=dict)
    legend: dict[str, Any] = field(default_factory=dict)
    axis_labels: dict[str, dict[str, Any]] = field(default_factory=dict)
    axis_config: AxisConfig | None = None

    @classmethod
    def default(cls) -> PlotTheme:
        """返回内置中文静态报告模板。"""

        return cls(
            locale=THEME_SCHEMA.normalize_locale(None),
            figure=THEME_SCHEMA.normalize_figure(None),
            axes=THEME_SCHEMA.normalize_axes(None),
            grid=THEME_SCHEMA.normalize_grid(None),
            artist=THEME_SCHEMA.normalize_artist(_DEFAULT_ARTIST_THEME),
            legend=THEME_SCHEMA.normalize_legend(None),
            axis_labels=THEME_SCHEMA.normalize_axis_labels(None),
            axis_config=None,
        )

    @classmethod
    def from_file(cls, path: str | Path) -> PlotTheme:
        """从配置文件读取图模板。"""

        payload = read_plotting_payload(path)
        THEME_SCHEMA.validate_theme_top_level_keys(payload)
        return THEME_SCHEMA.build_theme(payload, default_artist=_DEFAULT_ARTIST_THEME)

    @classmethod
    def apply_songtnr(cls, update_fields: Mapping[str, Any] | None = None) -> str | None:
        """快捷把 Matplotlib 全局默认字体切到 ``SongTNR``。"""

        theme = cls.default()
        theme.locale["font_family"] = "sans-serif"
        theme.locale["sans_serif"] = ["SongTNR"]
        return theme.apply_matplotlib(update_fields=update_fields)

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

    def axis_label_options(self, side: str) -> dict[str, Any]:
        """返回指定坐标轴标签的主题配置。"""

        return dict(self.axis_labels.get(side, {}))

    def _build_axis_frame(self) -> Any:
        """返回当前模板对应的内部 ``AxisFrame``。"""

        from ._axes_frame import AxisFrame

        return AxisFrame(params=theme_axes_to_axis_frame_section(self.axes))

    def _build_grid_frame(self) -> Any:
        """返回当前模板对应的内部 ``GridFrame``。"""

        from ._axes_frame import GridFrame

        return GridFrame(params=theme_grid_to_grid_frame_section(self.grid))

    def apply_matplotlib(self, update_fields: Mapping[str, Any] | None = None) -> str | None:
        """应用 locale 对应的 ``rcParams`` 底座。"""

        rc_params = theme_locale_to_rcparams(self.locale)
        if update_fields is not None:
            rc_params.update(dict(update_fields))
        normalized = font_runtime.normalize_font_rcparams(rc_params)
        plt.rcParams.update(normalized)
        fonts = normalized.get("font.sans-serif", [])
        if isinstance(fonts, list) and fonts:
            return str(fonts[0])
        return None


__all__ = ["PlotTheme"]
