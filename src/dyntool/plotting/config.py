"""绘图模块内部配置。"""

from __future__ import annotations

from pathlib import Path
from typing import Any
import warnings

import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.font_manager import FontEntry

from ..config import read_config_file

_DEFAULT_FONT_CANDIDATES = [
    "SongTNR",
    "Microsoft YaHei",
    "SimHei",
    "KaiTi",
    "NSimSun",
]
_CACHED_FONT_NAME: str | None = None


def _coerce_font_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return [str(item) for item in value]


class ZhPlotConfig:
    """管理 matplotlib 中文字体配置。"""

    CONFIG_PATH = Path(__file__).resolve().parent / "assets" / "plotting.json"

    def __init__(
        self,
        *,
        config_path: str | None = None,
        font_path: str | None = None,
    ) -> None:
        self.config_path = Path(config_path) if config_path else self.CONFIG_PATH
        self.font_path = Path(font_path) if font_path else None
        self.config: dict[str, Any] | None = None

    def _set_config(self) -> None:
        payload = read_config_file(self.config_path)
        if not isinstance(payload, dict):
            raise TypeError("绘图配置必须解析为字典。")
        self.config = payload

    def _list_installed_font_names(self) -> set[str]:
        return {font.name for font in font_manager.fontManager.ttflist}

    def _register_font_file(self, font_path: Path) -> str:
        font_manager.fontManager.addfont(str(font_path))
        if font_path.name == "SongTNR.ttf":
            if all(font.name != "SongTNR" for font in font_manager.fontManager.ttflist):
                font_manager.fontManager.ttflist.append(FontEntry(fname=str(font_path), name="SongTNR"))
            return "SongTNR"
        return font_manager.FontProperties(fname=str(font_path)).get_name()

    def _resolve_font_name(self) -> str | None:
        if self.font_path is not None:
            if not self.font_path.exists():
                raise FileNotFoundError(f"字体文件不存在：{self.font_path}")
            return self._register_font_file(self.font_path)

        installed = self._list_installed_font_names()
        for candidate in _DEFAULT_FONT_CANDIDATES:
            if candidate in installed:
                return candidate
        return None

    def _set_font(self) -> None:
        assert self.config is not None
        font_name = self._resolve_font_name()
        if font_name is None:
            warnings.warn(
                "No Chinese font was found for matplotlib. Chinese glyphs may be missing.",
                stacklevel=2,
            )
            self.config["axes.unicode_minus"] = False
            return

        sans_serif = _coerce_font_list(self.config.get("font.sans-serif", []))
        serif = _coerce_font_list(self.config.get("font.serif", []))
        self.config["font.family"] = "sans-serif"
        self.config["font.sans-serif"] = [
            font_name,
            *[item for item in sans_serif if item != font_name],
        ]
        self.config["font.serif"] = [
            font_name,
            *[item for item in serif if item != font_name],
        ]
        self.config["axes.unicode_minus"] = False

    def apply(self, update_fields: dict[str, Any] | None = None) -> str | None:
        """应用中文字体配置。"""

        self._set_config()
        self._set_font()
        assert self.config is not None
        if update_fields is not None:
            self.config.update(update_fields)
        plt.rcParams.update(self.config)
        fonts = self.config.get("font.sans-serif", [])
        if isinstance(fonts, list) and fonts:
            return str(fonts[0])
        return None


def configure_zh(
    config_path: str | None = None,
    *,
    font_path: str | None = None,
    update_fields: dict[str, Any] | None = None,
) -> str | None:
    """配置 matplotlib 中文绘图环境。"""

    global _CACHED_FONT_NAME
    if _CACHED_FONT_NAME is not None and config_path is None and font_path is None and update_fields is None:
        return _CACHED_FONT_NAME
    if font_path is None:
        font_path = str(Path(__file__).resolve().parent / "fonts" / "SongTNR.ttf")
    zh_plot_config = ZhPlotConfig(config_path=config_path, font_path=font_path)
    _CACHED_FONT_NAME = zh_plot_config.apply(update_fields=update_fields)
    return _CACHED_FONT_NAME


__all__ = ["ZhPlotConfig", "configure_zh"]
