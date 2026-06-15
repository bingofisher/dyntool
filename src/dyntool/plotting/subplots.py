"""多子图组合绘图入口。"""

from __future__ import annotations

from dataclasses import KW_ONLY, dataclass, field
from typing import Any, Mapping, Sequence

from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.gridspec import GridSpec

from .axis_config import AxisConfig
from .config import PlotTheme
from .dataset import PlotCategory, PlotDataset
from .plotters import BoxPlotter, FramePlotter, OneThirdOctavePlotter, StoryValuePlotter
from .types import PlotResult

PanelPlotter = FramePlotter | OneThirdOctavePlotter | StoryValuePlotter | BoxPlotter
"""多子图组合层当前接受的 concrete plotter 类型。"""


@dataclass(slots=True, frozen=True)
class PlotPanel:
    """多子图中的单个绘图面板。"""

    dataset: PlotDataset
    plotter: PanelPlotter
    _: KW_ONLY
    title: str | None = None
    categories: Sequence[PlotCategory | str] | None = None
    names: Sequence[str] | None = None
    legend_options: Mapping[str, Any] | None = None
    axis_config: AxisConfig | None = None
    plot_options: Mapping[str, Any] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class SubplotLayout:
    """多子图行列布局。"""

    rows: int
    cols: int
    _: KW_ONLY
    share_x: bool = False
    share_y: bool = False
    height_ratios: Sequence[float] | None = None
    width_ratios: Sequence[float] | None = None
    hspace: float | None = None
    wspace: float | None = None

    def __post_init__(self) -> None:
        if self.rows <= 0 or self.cols <= 0:
            raise ValueError("子图布局的 rows 和 cols 必须为正整数。")
        if self.height_ratios is not None and len(self.height_ratios) != self.rows:
            raise ValueError("height_ratios 数量必须与 rows 一致。")
        if self.width_ratios is not None and len(self.width_ratios) != self.cols:
            raise ValueError("width_ratios 数量必须与 cols 一致。")

    @property
    def capacity(self) -> int:
        """返回布局可容纳的 panel 数量。"""

        return self.rows * self.cols


class SubplotFigurePlotter:
    """把多个 ``PlotPanel`` 组合到同一张 figure。"""

    def __init__(self, *, theme: PlotTheme | None = None, layout: SubplotLayout | None = None) -> None:
        """构造多子图组合绘图器。"""

        self._theme = theme
        self._layout = layout or SubplotLayout(rows=1, cols=1)

    def plot_panels(self, panels: Sequence[PlotPanel]) -> PlotResult:
        """绘制多个 panel 并返回统一 ``PlotResult``。"""

        if not panels:
            raise ValueError("至少需要一个 PlotPanel。")
        if len(panels) > self._layout.capacity:
            raise ValueError("panel 数量不能超过布局容量。")

        fig = self._build_figure()
        axes = self._build_axes(fig, panel_count=len(panels))
        panel_results: list[PlotResult] = []
        for panel, ax in zip(panels, axes, strict=False):
            panel_results.append(self._plot_panel(panel, ax))
        return PlotResult(
            raw=fig,
            figure=fig,
            axes=tuple(axes),
            artists=tuple(artist for result in panel_results for artist in result.artists),
        )

    def _build_figure(self) -> Figure:
        plt = self._ensure_matplotlib()
        if self._theme is not None:
            self._theme.apply_matplotlib()
            figure_options = self._theme.figure_options()
            return plt.figure(
                figsize=(
                    float(figure_options["width_cm"]) / 2.54,
                    float(figure_options["height_cm"]) / 2.54,
                ),
                dpi=int(figure_options["dpi"]),
            )
        return plt.figure()

    def _build_axes(self, fig: Figure, *, panel_count: int) -> list[Axes]:
        rect = self._subplot_rect()
        grid = GridSpec(
            self._layout.rows,
            self._layout.cols,
            figure=fig,
            left=rect[0],
            bottom=rect[1],
            right=rect[0] + rect[2],
            top=rect[1] + rect[3],
            height_ratios=self._layout.height_ratios,
            width_ratios=self._layout.width_ratios,
            hspace=self._layout.hspace,
            wspace=self._layout.wspace,
        )
        axes: list[Axes] = []
        sharex_ax: Axes | None = None
        sharey_ax: Axes | None = None
        for index in range(panel_count):
            row, col = divmod(index, self._layout.cols)
            ax = fig.add_subplot(
                grid[row, col],
                sharex=sharex_ax if self._layout.share_x else None,
                sharey=sharey_ax if self._layout.share_y else None,
            )
            if sharex_ax is None:
                sharex_ax = ax
            if sharey_ax is None:
                sharey_ax = ax
            axes.append(ax)
        return axes

    def _subplot_rect(self) -> tuple[float, float, float, float]:
        if self._theme is None:
            return (0.125, 0.11, 0.775, 0.77)
        figure_options = self._theme.figure_options()
        return tuple(float(item) for item in figure_options["add_axes_rect"])

    def _plot_panel(self, panel: PlotPanel, ax: Axes) -> PlotResult:
        previous_ax = getattr(panel.plotter, "ax", None)
        if hasattr(panel.plotter, "ax"):
            panel.plotter.ax = ax
        plot_kwargs: dict[str, Any] = {
            "categories": panel.categories,
            "names": panel.names,
            "ax": ax,
            "legend_options": panel.legend_options,
            **dict(panel.plot_options),
        }
        if panel.axis_config is not None:
            plot_kwargs["axis_config"] = panel.axis_config
        try:
            result = panel.plotter.plot_dataset(panel.dataset, **plot_kwargs)
        finally:
            if hasattr(panel.plotter, "ax"):
                panel.plotter.ax = previous_ax
        if panel.title:
            ax.set_title(panel.title)
        return result

    @staticmethod
    def _ensure_matplotlib() -> Any:
        import matplotlib.pyplot as plt

        return plt


__all__ = ["PlotPanel", "SubplotFigurePlotter", "SubplotLayout"]
