"""GUI 应用级设置持久化。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import QByteArray, QSettings
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QMainWindow

_WINDOW_LAYOUT_VERSION = 3


class AppSettingsStore:
    """负责读写 GUI 机器级偏好与窗口布局。"""

    def __init__(self, path: str | Path | None = None) -> None:
        self._path = None if path is None else Path(path).resolve()
        if self._path is None:
            self._settings = QSettings("AdvDynTool", "dyntool_gui")
        else:
            self._settings = QSettings(str(self._path), QSettings.Format.IniFormat)

    def save_preferences(self, payload: dict[str, Any]) -> None:
        """保存应用偏好。"""

        self._settings.setValue("theme/name", str(payload.get("theme_name", "light")))
        self._settings.setValue("recent/projects", list(payload.get("recent_projects", [])))
        self._settings.setValue("recent/sample_dir", payload.get("recent_sample_dir", ""))
        self._settings.setValue("recent/sampleset_dir", payload.get("recent_sampleset_dir", ""))
        self._settings.sync()

    def load_preferences(self) -> dict[str, Any]:
        """读取应用偏好。"""

        projects = self._settings.value("recent/projects", [])
        if isinstance(projects, str):
            projects = [projects]
        return {
            "theme_name": str(self._settings.value("theme/name", "light")),
            "recent_projects": [str(item) for item in projects or []],
            "recent_sample_dir": str(self._settings.value("recent/sample_dir", "")),
            "recent_sampleset_dir": str(self._settings.value("recent/sampleset_dir", "")),
        }

    def save_main_window(self, window: QMainWindow) -> None:
        """保存主窗口几何与布局。"""

        geometry = window.geometry()
        self._settings.setValue("window/geometry", window.saveGeometry())
        self._settings.setValue("window/state", window.saveState())
        self._settings.setValue("window/layout_version", _WINDOW_LAYOUT_VERSION)
        self._settings.setValue("window/width", geometry.width())
        self._settings.setValue("window/height", geometry.height())
        self._settings.setValue("window/x", geometry.x())
        self._settings.setValue("window/y", geometry.y())
        self._settings.sync()

    def restore_main_window(self, window: QMainWindow) -> None:
        """恢复主窗口几何与布局。"""

        layout_version = int(self._settings.value("window/layout_version", 0) or 0)
        if layout_version != _WINDOW_LAYOUT_VERSION:
            self._reset_legacy_window_layout()
            return

        restored = False
        width = self._to_int(self._settings.value("window/width"))
        height = self._to_int(self._settings.value("window/height"))
        x = self._to_int(self._settings.value("window/x"))
        y = self._to_int(self._settings.value("window/y"))
        screen = QGuiApplication.primaryScreen()
        if screen is not None and width is not None and height is not None:
            available = screen.availableGeometry()
            min_width = max(window.minimumWidth(), min(1840, int(available.width() * 0.72)))
            min_height = max(window.minimumHeight(), min(1120, int(available.height() * 0.78)))
            target_width = max(min_width, min(width, available.width()))
            target_height = max(min_height, min(height, available.height()))
            target_x = available.x() if x is None else max(available.x(), min(x, available.right() - target_width + 1))
            target_y = (
                available.y() if y is None else max(available.y(), min(y, available.bottom() - target_height + 1))
            )
            window.setGeometry(target_x, target_y, target_width, target_height)
            restored = True

        geometry = self._settings.value("window/geometry")
        state = self._settings.value("window/state")
        if not restored and isinstance(geometry, QByteArray) and not geometry.isEmpty():
            window.restoreGeometry(geometry)
        if isinstance(state, QByteArray) and not state.isEmpty():
            window.restoreState(state)

    def _reset_legacy_window_layout(self) -> None:
        """丢弃旧版窗口布局缓存，避免跨版本恢复异常几何。"""

        for key in (
            "window/geometry",
            "window/state",
            "window/width",
            "window/height",
            "window/x",
            "window/y",
        ):
            self._settings.remove(key)
        self._settings.setValue("window/layout_version", _WINDOW_LAYOUT_VERSION)
        self._settings.sync()

    def _to_int(self, value: Any) -> int | None:
        """将设置值转换为整数。"""

        if value in {None, ""}:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
