"""GUI 内部截图工具。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication

from .persistence import ProjectFileStore
from .session import ModuleKey, ProjectSession
from .theme import ThemeManager


@dataclass(frozen=True, slots=True)
class GuiScreenshotOptions:
    """GUI 截图参数。"""

    output_path: Path
    demo_key: str = "bridge"
    project_path: Path | None = None
    module_key: str = "project"
    width: int = 1920
    height: int = 1080


def resolve_gui_font_family() -> str:
    """返回截图环境可用的中文 UI 字体。"""

    _register_bundled_font()
    families = set(QFontDatabase.families())
    for family in (
        "Microsoft YaHei UI",
        "Microsoft YaHei",
        "Noto Sans SC",
        "Noto Sans CJK SC",
        "SimHei",
        "SimSun",
        "SongTNR",
    ):
        if family in families:
            return family
    return "Sans Serif"


def capture_main_window_screenshot(options: GuiScreenshotOptions) -> Path:
    """渲染主窗口并保存 PNG 截图。"""

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setFont(QFont(resolve_gui_font_family(), 10))
    session = _build_session(options)

    from .main_window import MainWindow

    window = MainWindow(session, theme_manager=ThemeManager())
    window.setWindowState(Qt.WindowState.WindowNoState)
    window.resize(QSize(options.width, options.height))
    window.workspace.set_current_module(_resolve_module_key(options.module_key))
    if options.module_key.strip().lower() == "filter":
        window.workspace.import_filter_workspace.focus_subset_workspace()
    window.show()
    window.resize(QSize(options.width, options.height))
    window._apply_adaptive_layout(force=True)
    for _ in range(5):
        app.processEvents()

    pixmap = window.grab(QRect(0, 0, options.width, options.height))
    target = options.output_path.resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    if not pixmap.save(str(target), "PNG"):
        raise RuntimeError(f"截图保存失败：{target}")
    window.close()
    app.processEvents()
    return target


def _build_session(options: GuiScreenshotOptions) -> ProjectSession:
    if options.project_path is not None:
        return ProjectFileStore().load(options.project_path)
    return ProjectSession.build_demo(options.demo_key)


def _resolve_module_key(value: str) -> ModuleKey:
    normalized = value.strip().lower()
    aliases = {
        "overview": ModuleKey.PROJECT,
        "project": ModuleKey.PROJECT,
        "import": ModuleKey.IMPORT,
        "filter": ModuleKey.IMPORT,
        "processing": ModuleKey.PROCESSING,
        "plotting": ModuleKey.PLOTTING,
    }
    if normalized in aliases:
        return aliases[normalized]
    return ModuleKey(normalized)


def _register_bundled_font() -> None:
    font_path = Path(__file__).resolve().parents[1] / "dyntool" / "plotting" / "fonts" / "SongTNR.ttf"
    if font_path.exists():
        QFontDatabase.addApplicationFont(str(font_path))


__all__ = ["GuiScreenshotOptions", "capture_main_window_screenshot", "resolve_gui_font_family"]
