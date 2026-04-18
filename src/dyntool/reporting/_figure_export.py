"""reporting 图表导出。"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from ..domain.models import OTOVLEval
from ..plotting import FramePlotter, OneThirdOctavePlotter, PlotCategory, PlotDataset, PlotTheme
from ._writers import flatten_label, slugify

if TYPE_CHECKING:
    from ..domain.samples import SampleSetBase

REPORT_THEME_NAME = "plot_theme_report.toml"
OTOVL_THEME_NAME = "plot_theme_one_third_octave.toml"
THEME_DIR = Path(__file__).resolve().parents[1] / "plotting" / "assets"


def export_scalar_summary_figures(
    frame: pd.DataFrame,
    *,
    figures_dir: Path,
    theme_override: PlotTheme | str | Path | None,
) -> list[dict[str, Any]]:
    """导出标量统计图。"""

    if frame.empty:
        return []
    labels = resolve_sample_labels(frame)
    numeric_columns: list[str] = []
    for column in frame.columns:
        if str(column) in {"uid", "alias"}:
            continue
        series = pd.to_numeric(frame[column], errors="coerce")
        if series.notna().any():
            numeric_columns.append(str(column))
    manifest: list[dict[str, Any]] = []
    axis = np.arange(1, len(frame) + 1, dtype=float)
    for column in numeric_columns:
        values = pd.to_numeric(frame[column], errors="coerce").to_numpy(dtype=float)
        if np.isnan(values).all():
            continue
        dataset = PlotDataset.from_axis_value(
            axis=axis,
            value=values,
            name=column,
            category=PlotCategory.STAT,
            label=column,
            source_type="report.scalar_frame",
        )
        manifest.append(
            render_plot_figure(
                dataset=dataset,
                plotter=FramePlotter(theme=resolve_theme("report", theme_override)),
                path=figures_dir / f"scalar_{slugify(column)}.png",
                title=f"{column} 统计",
                theme_name=resolve_theme_name("report", theme_override),
                xtick_labels=labels,
            )
        )
    return manifest


def export_series_figures(
    frame: pd.DataFrame,
    *,
    data_var: str,
    figures_dir: Path,
    theme_override: PlotTheme | str | Path | None,
) -> list[dict[str, Any]]:
    """导出序列图。"""

    if frame.empty:
        return []
    dataset = PlotDataset()
    for column in frame.columns:
        values = pd.to_numeric(frame[column], errors="coerce")
        if values.notna().sum() == 0:
            continue
        flattened = flatten_label(column)
        dataset.add_axis_value(
            axis=frame.index.to_numpy(dtype=float),
            value=values.to_numpy(dtype=float),
            name=flattened,
            category=PlotCategory.SAMPLE,
            label=flattened,
            source_type=f"report.series.{data_var}",
        )
    if dataset.to_dataframe().empty:
        return []
    return [
        render_plot_figure(
            dataset=dataset,
            plotter=FramePlotter(theme=resolve_theme("report", theme_override)),
            path=figures_dir / f"series_{slugify(data_var)}.png",
            title=f"{data_var} 序列",
            theme_name=resolve_theme_name("report", theme_override),
        )
    ]


def export_peaks_figures(
    frame: pd.DataFrame,
    *,
    source: str,
    figures_dir: Path,
    theme_override: PlotTheme | str | Path | None,
) -> list[dict[str, Any]]:
    """导出峰值统计图。"""

    if frame.empty:
        return []
    dataset = PlotDataset()
    for column in frame.columns:
        flattened = flatten_label(column)
        if not flattened.endswith("@peak_value") and flattened != "peak_value":
            continue
        values = pd.to_numeric(frame[column], errors="coerce")
        if values.notna().sum() == 0:
            continue
        dataset.add_axis_value(
            axis=frame.index.to_numpy(dtype=float),
            value=values.to_numpy(dtype=float),
            name=flattened,
            category=PlotCategory.STAT,
            label=flattened,
            source_type=f"report.peaks.{source}",
        )
    if dataset.to_dataframe().empty:
        return []
    return [
        render_plot_figure(
            dataset=dataset,
            plotter=FramePlotter(theme=resolve_theme("report", theme_override)),
            path=figures_dir / f"peaks_{slugify(source)}.png",
            title=f"{source} 峰值",
            theme_name=resolve_theme_name("report", theme_override),
        )
    ]


def export_otovl_figures(
    sample_set: "SampleSetBase[Any]",
    *,
    figures_dir: Path,
    theme_override: PlotTheme | str | Path | None,
) -> list[dict[str, Any]]:
    """导出 OTOVL 总览图。"""

    dataset = PlotDataset()
    found = False
    for sample in sample_set.values():
        model = sample.get_data_var("otovl")
        if not isinstance(model, OTOVLEval):
            continue
        dataset.add_axis_value(
            axis=model.get_axis(),
            value=model.get_value(),
            name=sample.uid,
            category=PlotCategory.SAMPLE,
            axis_unit=model.current_units().get("freq"),
            value_unit=model.current_units().get("env"),
            label=sample.alias or sample.uid,
            source_type="report.otovl",
        )
        found = True
    if not found:
        return []
    return [
        render_plot_figure(
            dataset=dataset,
            plotter=OneThirdOctavePlotter(theme=resolve_theme("one_third_octave", theme_override)),
            path=figures_dir / "otovl_overview.png",
            title="1/3 倍频程振级概览",
            theme_name=resolve_theme_name("one_third_octave", theme_override),
        )
    ]


def render_plot_figure(
    *,
    dataset: PlotDataset,
    plotter: Any,
    path: Path,
    title: str,
    theme_name: str,
    xtick_labels: list[str] | None = None,
) -> dict[str, Any]:
    """执行 plotter 并输出 PNG 文件。"""

    result = plotter.plot_dataset(dataset, legend_options={})
    if result.ax is not None:
        result.ax.set_title(title)
        if xtick_labels is not None:
            result.ax.set_xticks(np.arange(1, len(xtick_labels) + 1, dtype=float))
            result.ax.set_xticklabels(xtick_labels, rotation=30, ha="right")
    if result.figure is None:
        raise RuntimeError("plot_dataset() 未返回 figure，无法导出图像")
    path.parent.mkdir(parents=True, exist_ok=True)
    result.figure.savefig(path, bbox_inches="tight")
    plt.close(result.figure)
    return {
        "name": path.stem,
        "path": str(path.relative_to(path.parents[1])).replace("\\", "/"),
        "plotter": type(plotter).__name__,
        "theme": theme_name,
        "title": title,
    }


def resolve_sample_labels(frame: pd.DataFrame) -> list[str]:
    """解析样本标签优先级。"""

    if "alias" in frame.columns:
        labels = [str(item).strip() for item in frame["alias"].fillna("").tolist()]
        if any(label for label in labels):
            return [label or str(uid) for label, uid in zip(labels, frame["uid"].tolist(), strict=False)]
    if "uid" in frame.columns:
        return [str(item) for item in frame["uid"].tolist()]
    return [str(index) for index in range(1, len(frame) + 1)]


def resolve_theme(theme_kind: str, theme_override: PlotTheme | str | Path | None) -> PlotTheme:
    """解析图表导出所用主题。"""

    if isinstance(theme_override, PlotTheme):
        return theme_override
    if isinstance(theme_override, (str, Path)):
        return PlotTheme.from_file(theme_override)
    if theme_kind == "one_third_octave":
        return PlotTheme.from_file(THEME_DIR / OTOVL_THEME_NAME)
    return PlotTheme.from_file(THEME_DIR / REPORT_THEME_NAME)


def resolve_theme_name(theme_kind: str, theme_override: PlotTheme | str | Path | None) -> str:
    """解析写入 manifest 的主题名称。"""

    if isinstance(theme_override, PlotTheme):
        return "custom_plot_theme"
    if isinstance(theme_override, (str, Path)):
        return Path(theme_override).name
    if theme_kind == "one_third_octave":
        return OTOVL_THEME_NAME
    return REPORT_THEME_NAME


def theme_manifest_value(theme_override: PlotTheme | str | Path | None) -> str | None:
    """解析写入参数区的主题值。"""

    if theme_override is None:
        return None
    if isinstance(theme_override, PlotTheme):
        return "custom_plot_theme"
    return str(theme_override)


__all__ = [
    "export_otovl_figures",
    "export_peaks_figures",
    "export_scalar_summary_figures",
    "export_series_figures",
    "theme_manifest_value",
]
