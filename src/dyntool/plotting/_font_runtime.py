"""PlotTheme 字体运行时支持。"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from matplotlib import font_manager
from matplotlib.font_manager import FontEntry

DEFAULT_FONT_CANDIDATES = [
    "SongTNR",
    "Microsoft YaHei",
    "SimHei",
    "KaiTi",
    "NSimSun",
]

_FONTS_DIR = Path(__file__).resolve().parent / "fonts"
_BUNDLED_FONT_PATHS = {
    "SongTNR": _FONTS_DIR / "SongTNR.ttf",
}


def _coerce_font_candidates(font_candidates: Any) -> list[str]:
    if isinstance(font_candidates, str):
        return [font_candidates]
    if not isinstance(font_candidates, list | tuple):
        raise ValueError("locale.sans_serif 必须为字符串列表。")
    normalized: list[str] = []
    for item in font_candidates:
        if not isinstance(item, str):
            raise ValueError("locale.sans_serif 必须为字符串列表。")
        normalized.append(item)
    return normalized


class _FontRuntime:
    """负责内置字体注册与 rcParams 字体链归一化。"""

    @staticmethod
    @lru_cache(maxsize=32)
    def _resolve_font_name(font_name: str) -> str:
        bundled_path = _BUNDLED_FONT_PATHS.get(font_name)
        if bundled_path is None or not bundled_path.exists():
            return font_name
        font_manager.fontManager.addfont(str(bundled_path))
        if all(font.name != font_name for font in font_manager.fontManager.ttflist):
            font_manager.fontManager.ttflist.append(FontEntry(fname=str(bundled_path), name=font_name))
        return font_name

    def resolve_font_candidates(self, font_candidates: Any) -> list[str]:
        """解析字体候选链并注册内置字体别名。"""

        resolved: list[str] = []
        for candidate in _coerce_font_candidates(font_candidates):
            mapped = self._resolve_font_name(candidate)
            if mapped not in resolved:
                resolved.append(mapped)
        return resolved

    def normalize_font_rcparams(self, rc_params: dict[str, Any]) -> dict[str, Any]:
        """归一化 rcParams 中的字体配置。"""

        resolved_sans_serif = self.resolve_font_candidates(rc_params.get("font.sans-serif", DEFAULT_FONT_CANDIDATES))
        rc_params["font.sans-serif"] = resolved_sans_serif
        rc_params["font.serif"] = self.resolve_font_candidates(rc_params.get("font.serif", resolved_sans_serif))
        return rc_params


font_runtime = _FontRuntime()

__all__ = ["DEFAULT_FONT_CANDIDATES", "font_runtime"]
