"""GUI 主题与样式管理。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from matplotlib import font_manager, rcParams
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT
from matplotlib.figure import Figure
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication, QWidget


@dataclass(frozen=True, slots=True)
class ThemeTokens:
    """主题令牌。"""

    ui_font_family: str = (
        '"Microsoft YaHei UI", "Microsoft YaHei", "Noto Sans SC", "Noto Sans CJK SC", '
        '"SimHei", "SimSun", "SongTNR", sans-serif'
    )
    window_background: str = "#F0F2F5"
    panel_background: str = "#F7F8FA"
    card_background: str = "#FFFFFF"
    border_color: str = "#E2E8F0"
    muted_border: str = "#CBD5E1"
    divider_color: str = "#E8ECF1"
    title_background: str = "#EBF0F7"
    header_gradient_start: str = "#2563EB"
    header_gradient_end: str = "#3B82F6"
    accent_color: str = "#2563EB"
    accent_hover: str = "#3B82F6"
    accent_light: str = "#DBEAFE"
    accent_surface: str = "#EFF6FF"
    text_color: str = "#1A202C"
    muted_text: str = "#64748B"
    subtle_text: str = "#94A3B8"
    success_color: str = "#16A34A"
    success_surface: str = "#F0FDF4"
    warning_color: str = "#D97706"
    warning_surface: str = "#FFFBEB"
    error_color: str = "#DC2626"
    error_surface: str = "#FEF2F2"
    selection_background: str = "#DBEAFE"
    hover_background: str = "#F1F5F9"
    disabled_background: str = "#F1F5F9"
    disabled_text: str = "#94A3B8"
    body_font_pt: int = 10
    header_font_pt: int = 11
    page_title_font_pt: int = 13
    radius_sm: int = 4
    radius_md: int = 6
    radius_lg: int = 8
    toolbar_height: int = 48
    nav_height: int = 36
    context_bar_height: int = 40
    dock_title_height: int = 28
    status_height: int = 24
    splitter_width: int = 4


class ThemeManager:
    """应用级主题管理器。"""

    def __init__(self, theme_name: str = "light") -> None:
        self._theme_name = theme_name
        self._tokens = ThemeTokens()

    @property
    def theme_name(self) -> str:
        """返回当前主题名称。"""

        return self._theme_name

    @property
    def tokens(self) -> ThemeTokens:
        """返回当前主题令牌。"""

        return self._tokens

    def apply(self, target: QApplication | QWidget) -> None:
        """应用 Qt 主题。"""

        _register_bundled_fonts()
        app = target if isinstance(target, QApplication) else QApplication.instance()
        if app is not None:
            app.setFont(QFont(_preferred_ui_font_family(), self._tokens.body_font_pt))
        target.setStyleSheet(self.build_qss())

    def build_qss(self) -> str:
        """构建 Qt 主题样式。"""

        t = self._tokens
        return _GLOBAL_QSS % {
            "window_background": t.window_background,
            "ui_font_family": t.ui_font_family,
            "panel_background": t.panel_background,
            "card_background": t.card_background,
            "border_color": t.border_color,
            "muted_border": t.muted_border,
            "divider_color": t.divider_color,
            "title_background": t.title_background,
            "header_gradient_start": t.header_gradient_start,
            "header_gradient_end": t.header_gradient_end,
            "accent_color": t.accent_color,
            "accent_hover": t.accent_hover,
            "accent_light": t.accent_light,
            "accent_surface": t.accent_surface,
            "text_color": t.text_color,
            "muted_text": t.muted_text,
            "subtle_text": t.subtle_text,
            "success_color": t.success_color,
            "success_surface": t.success_surface,
            "warning_color": t.warning_color,
            "warning_surface": t.warning_surface,
            "error_color": t.error_color,
            "error_surface": t.error_surface,
            "selection_background": t.selection_background,
            "hover_background": t.hover_background,
            "disabled_background": t.disabled_background,
            "disabled_text": t.disabled_text,
            "body_font_pt": t.body_font_pt,
            "header_font_pt": t.header_font_pt,
            "page_title_font_pt": t.page_title_font_pt,
            "radius_sm": t.radius_sm,
            "radius_md": t.radius_md,
            "radius_lg": t.radius_lg,
            "toolbar_height": t.toolbar_height,
            "nav_height": t.nav_height,
            "context_bar_height": t.context_bar_height,
            "dock_title_height": t.dock_title_height,
            "status_height": t.status_height,
            "splitter_width": t.splitter_width,
        }

    def apply_plot_figure(self, figure: Figure) -> None:
        """应用 Matplotlib 图形主题。"""

        t = self._tokens
        _register_matplotlib_font()
        figure.patch.set_facecolor(t.card_background)
        for ax in figure.axes:
            ax.set_facecolor(t.card_background)
            ax.grid(True, color="#D0D7E2", linestyle="--", linewidth=0.7, alpha=0.9)
            ax.tick_params(colors="#344054")
            ax.xaxis.label.set_color("#344054")
            ax.yaxis.label.set_color("#344054")
            ax.title.set_color("#102A43")
            for spine in ax.spines.values():
                spine.set_color(t.muted_border)
            legend = ax.get_legend()
            if legend is not None:
                legend.get_frame().set_facecolor(t.card_background)
                legend.get_frame().set_edgecolor(t.border_color)

    def apply_plot_toolbar(self, toolbar: NavigationToolbar2QT) -> None:
        """应用 Matplotlib 工具条主题。"""

        t = self._tokens
        toolbar.setStyleSheet(
            _PLOT_TOOLBAR_QSS
            % {
                "card_background": t.card_background,
                "border_color": t.border_color,
                "radius_md": t.radius_md,
                "radius_sm": t.radius_sm,
                "muted_text": t.muted_text,
                "selection_background": t.selection_background,
                "muted_border": t.muted_border,
                "accent_color": t.accent_color,
            }
        )


def _register_bundled_fonts() -> None:
    """注册仓库内置字体，保证截图环境有中文字体兜底。"""

    font_path = Path(__file__).resolve().parents[1] / "dyntool" / "plotting" / "fonts" / "SongTNR.ttf"
    if font_path.exists():
        QFontDatabase.addApplicationFont(str(font_path))


def _register_matplotlib_font() -> None:
    """注册 Matplotlib 中文字体，避免大图预览出现缺字形方框。"""

    font_path = Path(__file__).resolve().parents[1] / "dyntool" / "plotting" / "fonts" / "SongTNR.ttf"
    if font_path.exists():
        font_manager.fontManager.addfont(str(font_path))
        family = font_manager.FontProperties(fname=str(font_path)).get_name()
    else:
        family = _preferred_ui_font_family()
    rcParams["font.family"] = [family, "sans-serif"]
    rcParams["font.sans-serif"] = [
        family,
        "Microsoft YaHei UI",
        "Microsoft YaHei",
        "Noto Sans CJK SC",
        "SimHei",
        "SimSun",
        "DejaVu Sans",
    ]
    rcParams["axes.unicode_minus"] = False


def _preferred_ui_font_family() -> str:
    """返回当前系统可用的首选中文 UI 字体。"""

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


_GLOBAL_QSS = """
/* ── 基础 ── */
QMainWindow, QWidget {
    background: %(window_background)s;
    color: %(text_color)s;
    font-family: %(ui_font_family)s;
    font-size: %(body_font_pt)spt;
    selection-background-color: %(accent_color)s;
    selection-color: #FFFFFF;
}

/* ── 菜单 ── */
QMenuBar {
    background: %(card_background)s;
    border-bottom: 1px solid %(border_color)s;
    padding: 2px 0;
}
QMenuBar::item {
    spacing: 6px;
    padding: 5px 12px;
    background: transparent;
    border-radius: %(radius_sm)spx;
}
QMenuBar::item:selected {
    background: %(hover_background)s;
}
QMenu {
    background: %(card_background)s;
    border: 1px solid %(border_color)s;
    padding: 6px;
    border-radius: %(radius_md)spx;
}
QMenu::item {
    padding: 6px 24px 6px 12px;
    border-radius: %(radius_sm)spx;
}
QMenu::item:selected {
    background: %(selection_background)s;
}

/* ── 工具栏 ── */
QToolBar {
    spacing: 10px;
    padding: 6px 12px;
    background: %(card_background)s;
    border: none;
    border-bottom: 1px solid %(border_color)s;
    min-height: %(toolbar_height)spx;
}
QToolBar::separator {
    width: 14px;
}
QToolButton {
    border: 1px solid transparent;
    border-radius: %(radius_md)spx;
    padding: 6px 10px;
    background: transparent;
    color: %(muted_text)s;
}
QToolButton:hover {
    background: %(hover_background)s;
    color: %(accent_color)s;
}
QToolButton:pressed {
    background: %(accent_light)s;
}

/* ── 按钮 ── */
QPushButton {
    border: 1px solid %(muted_border)s;
    border-radius: %(radius_md)spx;
    padding: 5px 14px;
    background: %(card_background)s;
    min-height: 20px;
    font-size: %(body_font_pt)spt;
}
QPushButton:hover {
    border-color: %(accent_color)s;
    background: %(accent_surface)s;
}
QPushButton:pressed {
    background: %(accent_light)s;
}
QPushButton:disabled {
    color: %(disabled_text)s;
    background: %(disabled_background)s;
    border-color: %(border_color)s;
}
QPushButton[buttonRole="primary"] {
    background: %(accent_color)s;
    border-color: %(accent_color)s;
    color: #FFFFFF;
    font-weight: 600;
    border-bottom: 2px solid #1D4ED8;
}
QPushButton[buttonRole="primary"]:hover {
    background: %(accent_hover)s;
    border-color: %(accent_hover)s;
    border-bottom-color: #2563EB;
}
QPushButton[buttonRole="primary"]:disabled {
    background: %(accent_light)s;
    border-color: %(accent_light)s;
    color: %(card_background)s;
    border-bottom-color: %(accent_light)s;
}
QPushButton[buttonRole="secondary"] {
    background: %(card_background)s;
    color: %(accent_color)s;
    border-color: %(accent_color)s;
}
QPushButton[buttonRole="secondary"]:hover {
    background: %(accent_surface)s;
}
QPushButton[buttonRole="ghost"] {
    background: %(panel_background)s;
    color: %(muted_text)s;
    border-style: dashed;
    border-color: %(muted_border)s;
}
QPushButton[buttonRole="ghost"]:hover {
    background: %(hover_background)s;
    color: %(text_color)s;
}

/* ── 模块导航按钮 ── */
QPushButton[navButton="true"] {
    min-height: %(nav_height)spx;
    border: none;
    border-bottom: 3px solid transparent;
    border-radius: 0;
    background: transparent;
    color: %(muted_text)s;
    font-weight: 600;
    font-size: %(header_font_pt)spt;
    padding: 4px 16px;
}
QPushButton[navButton="true"]:hover {
    background: %(hover_background)s;
    color: %(text_color)s;
    border-bottom-color: %(muted_border)s;
}
QPushButton[navButton="true"]:checked,
QPushButton[navButton="true"][current="true"] {
    background: %(accent_surface)s;
    border-bottom: 3px solid %(accent_color)s;
    color: %(accent_color)s;
}

/* ── 分组框（卡片） ── */
QGroupBox {
    border: 1px solid %(border_color)s;
    border-left: 3px solid %(accent_color)s;
    border-radius: %(radius_md)spx;
    margin-top: 18px;
    padding: 12px 10px 10px 12px;
    background: %(card_background)s;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    top: 2px;
    padding: 0 6px;
    color: %(text_color)s;
    font-size: %(header_font_pt)spt;
    font-weight: 700;
}

/* ── 输入控件 ── */
QLineEdit, QPlainTextEdit, QComboBox, QTableView, QTreeView, QTableWidget, QListView {
    border: 1px solid %(muted_border)s;
    border-radius: %(radius_md)spx;
    background: %(card_background)s;
}
QLineEdit, QPlainTextEdit, QComboBox {
    padding: 4px 8px;
    min-height: 20px;
}
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus {
    border-color: %(accent_color)s;
    border-width: 2px;
    padding: 3px 7px;
}

/* ── Dock ── */
QDockWidget {
    color: %(text_color)s;
}
QDockWidget::title {
    background: %(title_background)s;
    border-bottom: 1px solid %(border_color)s;
    color: %(muted_text)s;
    font-size: %(body_font_pt)spt;
    font-weight: 600;
    padding-left: 10px;
    height: %(dock_title_height)spx;
}

/* ── Tab ── */
QTabWidget::pane {
    border: 1px solid %(border_color)s;
    background: %(card_background)s;
    border-radius: %(radius_lg)spx;
}
QTabBar::tab {
    background: %(panel_background)s;
    color: %(muted_text)s;
    padding: 7px 16px;
    margin-right: 2px;
    border-top-left-radius: %(radius_md)spx;
    border-top-right-radius: %(radius_md)spx;
    border: 1px solid %(border_color)s;
    border-bottom: none;
    font-size: %(body_font_pt)spt;
}
QTabBar::tab:selected {
    background: %(card_background)s;
    color: %(accent_color)s;
    font-weight: 600;
    border-bottom: 2px solid %(accent_color)s;
}
QTabBar::tab:hover:!selected {
    background: %(hover_background)s;
}

/* ── 表头 ── */
QHeaderView::section {
    background: %(title_background)s;
    color: %(muted_text)s;
    padding: 6px 10px;
    border: none;
    border-right: 1px solid %(border_color)s;
    border-bottom: 1px solid %(border_color)s;
    font-weight: 600;
    font-size: %(body_font_pt)spt;
}

/* ── 表格/树 ── */
QTableView, QTreeView, QTableWidget {
    gridline-color: %(divider_color)s;
    alternate-background-color: %(panel_background)s;
}
QTreeView::item:selected, QTableView::item:selected, QTableWidget::item:selected {
    background: %(selection_background)s;
    color: %(text_color)s;
}
QTreeView::item:hover, QTableView::item:hover {
    background: %(hover_background)s;
}

/* ── 进度条 ── */
QProgressBar {
    border: 1px solid %(muted_border)s;
    border-radius: %(radius_md)spx;
    background: %(panel_background)s;
    text-align: center;
    min-height: 18px;
}
QProgressBar::chunk {
    background: %(accent_color)s;
    border-radius: %(radius_md)spx;
}

/* ── 语义标签 ── */
QLabel[cardRole="header"] {
    color: %(accent_color)s;
    font-size: %(page_title_font_pt)spt;
    font-weight: 700;
    padding: 2px 0;
}
QLabel[cardRole="pageTitle"] {
    color: %(text_color)s;
    font-size: %(page_title_font_pt)spt;
    font-weight: 700;
    padding: 4px 0 0 0;
}
QLabel[cardRole="pageSubtitle"] {
    color: %(muted_text)s;
    font-size: %(body_font_pt)spt;
    padding: 0;
}
QLabel[cardRole="pageSummary"] {
    background: %(panel_background)s;
    border: none;
    border-left: 3px solid %(accent_color)s;
    border-radius: 0;
    color: %(muted_text)s;
    font-weight: 500;
    padding: 5px 10px;
}
QLabel[cardRole="heroSummary"] {
    background: %(accent_surface)s;
    border: 1px solid %(accent_light)s;
    border-radius: %(radius_lg)spx;
    color: %(accent_color)s;
    font-weight: 600;
    padding: 6px 12px;
}
QLabel[cardRole="status"] {
    background: %(card_background)s;
    border: 1px solid %(border_color)s;
    border-radius: %(radius_md)spx;
    padding: 6px 10px;
    line-height: 1.5;
}
QLabel[cardRole="emptyState"] {
    background: %(panel_background)s;
    border: 2px dashed %(muted_border)s;
    border-radius: %(radius_lg)spx;
    color: %(subtle_text)s;
    padding: 24px 16px;
    font-size: %(header_font_pt)spt;
}

/* ── 上下文条 ── */
QFrame#contextBar {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 %(header_gradient_start)s,
        stop:1 %(header_gradient_end)s);
    min-height: %(context_bar_height)spx;
    max-height: %(context_bar_height)spx;
}
QFrame#contextBar QLabel {
    color: white;
}

/* ── 面板容器 ── */
QWidget[pageHeader="true"],
QWidget[surfaceRole="pageHeader"] {
    background: %(card_background)s;
    border: 1px solid %(border_color)s;
    border-radius: %(radius_lg)spx;
}
QWidget[surfaceRole="actionPanel"],
QWidget[surfaceRole="resultPanel"],
QWidget[surfaceRole="summaryPanel"] {
    background: %(panel_background)s;
    border: 1px solid %(border_color)s;
    border-radius: %(radius_lg)spx;
}

/* ── 状态栏 ── */
QStatusBar {
    background: %(card_background)s;
    border-top: 1px solid %(border_color)s;
    min-height: %(status_height)spx;
}
QStatusBar QLabel {
    color: %(muted_text)s;
    padding: 0 8px;
}

/* ── 分隔器 ── */
QSplitter::handle {
    background: %(divider_color)s;
    width: %(splitter_width)spx;
    height: %(splitter_width)spx;
}
QSplitter::handle:hover {
    background: %(accent_light)s;
}

QScrollArea {
    border: none;
}

/* ── Checkbox/Radio ── */
QCheckBox, QRadioButton {
    spacing: 6px;
    font-size: %(body_font_pt)spt;
}
QCheckBox::indicator, QRadioButton::indicator {
    width: 16px;
    height: 16px;
}
"""

_PLOT_TOOLBAR_QSS = """
QToolBar {
    background: %(card_background)s;
    border: 1px solid %(border_color)s;
    border-radius: %(radius_md)spx;
    padding: 4px 6px;
    spacing: 6px;
}
QToolButton {
    border: 1px solid transparent;
    border-radius: %(radius_sm)spx;
    padding: 5px;
    background: transparent;
    color: %(muted_text)s;
}
QToolButton:hover {
    background: %(selection_background)s;
    border-color: %(muted_border)s;
    color: %(accent_color)s;
}
QToolBar::separator {
    width: 10px;
}
"""
