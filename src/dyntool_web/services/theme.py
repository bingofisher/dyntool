"""Web 绘图主题服务。"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import tomllib

from dyntool.plotting import PlotTheme

THEME_ASSET = Path(__file__).resolve().parents[2] / "dyntool" / "plotting" / "assets" / "plot_theme_report.toml"


def default_theme_payload() -> dict[str, Any]:
    """读取默认主题负载。"""

    with THEME_ASSET.open("rb") as file:
        return tomllib.load(file)


def resolve_theme_path(workdir: Path) -> Path:
    """返回项目级 GUI 绘图主题路径。"""

    return workdir / "themes" / "gui_plot_theme.toml"


def load_active_theme(workdir: Path) -> tuple[dict[str, Any], Path | None]:
    """读取当前活动主题。"""

    theme_path = resolve_theme_path(workdir)
    if theme_path.exists():
        with theme_path.open("rb") as file:
            return tomllib.load(file), theme_path
    return default_theme_payload(), None


def save_theme(workdir: Path, payload: dict[str, Any]) -> Path:
    """保存项目级主题 TOML。"""

    theme_path = resolve_theme_path(workdir)
    theme_path.parent.mkdir(parents=True, exist_ok=True)
    theme_path.write_text(_dump_toml(payload), encoding="utf-8", newline="\n")
    PlotTheme.from_file(theme_path)
    return theme_path


def ensure_default_theme(workdir: Path) -> Path:
    """确保项目级主题存在。"""

    theme_path = resolve_theme_path(workdir)
    if not theme_path.exists():
        theme_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(THEME_ASSET, theme_path)
    return theme_path


def _dump_toml(payload: dict[str, Any]) -> str:
    lines: list[str] = []
    _write_table(lines, (), payload)
    return "\n".join(lines).strip() + "\n"


def _write_table(lines: list[str], prefix: tuple[str, ...], mapping: dict[str, Any]) -> None:
    values = {key: value for key, value in mapping.items() if not isinstance(value, dict)}
    tables = {key: value for key, value in mapping.items() if isinstance(value, dict)}
    if prefix:
        lines.append("")
        lines.append(f"[{'.'.join(prefix)}]")
    for key, value in values.items():
        lines.append(f"{key} = {_toml_value(value)}")
    for key, value in tables.items():
        _write_table(lines, (*prefix, str(key)), value)


def _toml_value(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return str(value)
    if isinstance(value, list | tuple):
        return "[" + ", ".join(_toml_value(item) for item in value) + "]"
    return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"') + '"'
