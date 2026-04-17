"""正式统计导出与报告包模块。"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterable, Literal, Mapping

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from ..domain.models import OTOVLEval
from ..plotting import FramePlotter, OneThirdOctavePlotter, PlotCategory, PlotDataset, PlotTheme

if TYPE_CHECKING:
    from ..domain.samples import SampleSetBase
    from ..domain.samples.types import SampleSetComparisonReport

ExportFormat = Literal["csv", "xlsx"]

_DEFAULT_SCALAR_FEATURES = ("pga", "rms", "crest_factor")
_DEFAULT_EVAL_DATA_VARS = ("zvl", "otovl", "fdmvl", "fpvdv")
_REPORT_THEME_NAME = "plot_theme_report.toml"
_OTOVL_THEME_NAME = "plot_theme_one_third_octave.toml"
_THEME_DIR = Path(__file__).resolve().parents[1] / "plotting" / "assets"

__all__ = [
    "export_scalar_frame",
    "export_series_frame",
    "export_peaks_frame",
    "export_compare_report",
    "export_report_package",
]


def export_scalar_frame(
    sample_set: "SampleSetBase[Any]",
    output_path: str | Path,
    *,
    features: Iterable[str],
    strict: bool = False,
    format: ExportFormat = "xlsx",
    metadata_fields: Iterable[str] | None = None,
    data_vars: Iterable[str] | None = None,
) -> Path:
    """导出样本集标量统计表。"""

    frame = sample_set.scalar_frame(
        metadata_fields=metadata_fields,
        data_vars=data_vars,
        features=features,
        strict=strict,
    )
    target = _resolve_file_path(output_path, format=format)
    _write_single_frame(frame, target, format=format, sheet_name="scalar_frame")
    return target


def export_series_frame(
    sample_set: "SampleSetBase[Any]",
    output_path: str | Path,
    *,
    data_var: str,
    metadata_fields: Iterable[str] | None = None,
    strict: bool = False,
    format: ExportFormat = "xlsx",
) -> Path:
    """导出样本集序列表。"""

    frame = sample_set.series_frame(
        data_var,
        metadata_fields=metadata_fields,
        strict=strict,
    )
    target = _resolve_file_path(output_path, format=format)
    _write_single_frame(frame, target, format=format, sheet_name="series_frame")
    return target


def export_peaks_frame(
    sample_set: "SampleSetBase[Any]",
    output_path: str | Path,
    *,
    source: str = "accel",
    format: ExportFormat = "xlsx",
    metadata_fields: Iterable[str] | None = None,
    strict: bool = False,
    **peak_options: Any,
) -> Path:
    """导出峰值统计表。"""

    frame = sample_set.peaks_frame(
        source=source,
        metadata_fields=metadata_fields,
        strict=strict,
        **peak_options,
    )
    target = _resolve_file_path(output_path, format=format)
    _write_single_frame(frame, target, format=format, sheet_name="peaks_frame")
    return target


def export_compare_report(
    left: "SampleSetBase[Any]",
    right: "SampleSetBase[Any]",
    output_path: str | Path,
    *,
    data_vars: Iterable[str] | None = None,
    features: Iterable[str] | None = None,
    format: ExportFormat = "xlsx",
    metadata_fields: Iterable[str] | None = None,
    rtol: float = 1e-6,
    atol: float = 1e-6,
    strict_types: bool = True,
) -> Path:
    """导出两个样本集的比较报告。"""

    report = left.compare_with(
        right,
        metadata_fields=metadata_fields,
        data_vars=data_vars,
        features=features,
        rtol=rtol,
        atol=atol,
        strict_types=strict_types,
    )
    frames = _comparison_frames(report)
    if format == "xlsx":
        target = _resolve_file_path(output_path, format="xlsx")
        _write_frames_workbook(frames, target)
        return target
    target_dir = _resolve_dir_path(output_path)
    target_dir.mkdir(parents=True, exist_ok=True)
    for name, frame in frames.items():
        _write_frame_csv(frame, target_dir / f"{name}.csv")
    return target_dir


def export_report_package(
    sample_set: "SampleSetBase[Any]",
    output_dir: str | Path,
    *,
    compare_to: "SampleSetBase[Any]" | None = None,
    features: Iterable[str] | None = None,
    series_vars: Iterable[str] | None = None,
    peak_sources: Iterable[str] | None = None,
    include_plots: bool = True,
    plot_theme: PlotTheme | str | Path | None = None,
    include_eval_summary: bool = True,
    csv_encoding: str = "utf-8-sig",
) -> Path:
    """导出完整项目报告数据包。"""

    output_root = Path(output_dir).resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    tables_dir = output_root / "tables"
    tables_dir.mkdir(exist_ok=True)
    figures_dir = output_root / "figures"
    figures_dir.mkdir(exist_ok=True)

    metadata_frame = sample_set.metadata_frame()
    metadata_summary = _build_metadata_summary(sample_set, metadata_frame)
    _write_json(output_root / "metadata_summary.json", metadata_summary)

    requested_features = tuple(str(item) for item in (features or _DEFAULT_SCALAR_FEATURES))
    requested_series_vars = tuple(str(item) for item in (series_vars or ()))
    requested_peak_sources = tuple(str(item) for item in (peak_sources or ()))
    eval_data_vars = _detect_available_eval_data_vars(sample_set) if include_eval_summary else tuple()
    scalar_eval_data_vars = _filter_scalar_data_vars(sample_set, eval_data_vars)

    workbook_frames: dict[str, pd.DataFrame] = {}
    manifest_tables: list[dict[str, Any]] = []

    workbook_frames["metadata_summary"] = metadata_frame
    _write_frame_csv(metadata_frame, tables_dir / "metadata_summary.csv", encoding=csv_encoding)
    manifest_tables.append(
        _frame_manifest_entry("metadata_summary", tables_dir / "metadata_summary.csv", metadata_frame)
    )

    scalar_frame = sample_set.scalar_frame(features=requested_features, strict=False)
    workbook_frames["scalar_frame"] = scalar_frame
    _write_frame_csv(scalar_frame, tables_dir / "scalar_frame.csv", encoding=csv_encoding)
    manifest_tables.append(_frame_manifest_entry("scalar_frame", tables_dir / "scalar_frame.csv", scalar_frame))

    series_frames: dict[str, pd.DataFrame] = {}
    for data_var in requested_series_vars:
        frame = sample_set.series_frame(data_var, strict=False)
        if frame.empty:
            continue
        sheet_name = f"series_{data_var}"
        workbook_frames[sheet_name] = frame
        csv_path = tables_dir / f"{sheet_name}.csv"
        _write_frame_csv(frame, csv_path, encoding=csv_encoding)
        series_frames[data_var] = frame
        manifest_tables.append(_frame_manifest_entry(sheet_name, csv_path, frame))

    peaks_frames: dict[str, pd.DataFrame] = {}
    for source in requested_peak_sources:
        frame = sample_set.peaks_frame(source=source, strict=False)
        if frame.empty:
            continue
        sheet_name = f"peaks_{source}"
        workbook_frames[sheet_name] = frame
        csv_path = tables_dir / f"{sheet_name}.csv"
        _write_frame_csv(frame, csv_path, encoding=csv_encoding)
        peaks_frames[source] = frame
        manifest_tables.append(_frame_manifest_entry(sheet_name, csv_path, frame))

    if compare_to is not None:
        compare_report = sample_set.compare_with(
            compare_to,
            data_vars=_build_compare_data_vars(scalar_eval_data_vars),
            features=requested_features,
        )
        for frame_name, frame in _comparison_frames(compare_report).items():
            sheet_name = f"compare_{frame_name}"
            workbook_frames[sheet_name] = frame
            csv_path = tables_dir / f"{sheet_name}.csv"
            _write_frame_csv(frame, csv_path, encoding=csv_encoding)
            manifest_tables.append(_frame_manifest_entry(sheet_name, csv_path, frame))

    if scalar_eval_data_vars:
        eval_summary = sample_set.scalar_frame(data_vars=scalar_eval_data_vars, strict=False)
        workbook_frames["eval_summary"] = eval_summary
        csv_path = tables_dir / "eval_summary.csv"
        _write_frame_csv(eval_summary, csv_path, encoding=csv_encoding)
        manifest_tables.append(_frame_manifest_entry("eval_summary", csv_path, eval_summary))

    figures_manifest: list[dict[str, Any]] = []
    if include_plots:
        figures_manifest.extend(
            _export_scalar_summary_figures(
                scalar_frame,
                figures_dir=figures_dir,
                theme_override=plot_theme,
            )
        )
        for data_var, frame in series_frames.items():
            figures_manifest.extend(
                _export_series_figures(
                    frame,
                    data_var=data_var,
                    figures_dir=figures_dir,
                    theme_override=plot_theme,
                )
            )
        for source, frame in peaks_frames.items():
            figures_manifest.extend(
                _export_peaks_figures(
                    frame,
                    source=source,
                    figures_dir=figures_dir,
                    theme_override=plot_theme,
                )
            )
        figures_manifest.extend(
            _export_otovl_figures(
                sample_set,
                figures_dir=figures_dir,
                theme_override=plot_theme,
            )
        )

    figures_index_frame = pd.DataFrame(figures_manifest)
    if not figures_index_frame.empty:
        workbook_frames["figures_index"] = figures_index_frame
        figures_index_path = figures_dir / "figures_index.csv"
        _write_frame_csv(figures_index_frame, figures_index_path, encoding=csv_encoding)
        manifest_tables.append(_frame_manifest_entry("figures_index", figures_index_path, figures_index_frame))
    else:
        workbook_frames["figures_index"] = pd.DataFrame(columns=["name", "path", "plotter", "theme", "title"])

    workbook_path = output_root / "report.xlsx"
    _write_frames_workbook(workbook_frames, workbook_path)

    manifest = {
        "report_workbook": workbook_path.name,
        "sample_set_type": type(sample_set).__name__,
        "sample_type": sample_set.sample_type.__name__,
        "sample_count": len(sample_set),
        "parameters": {
            "features": list(requested_features),
            "series_vars": list(requested_series_vars),
            "peak_sources": list(requested_peak_sources),
            "include_plots": include_plots,
            "include_eval_summary": include_eval_summary,
            "plot_theme": _theme_manifest_value(plot_theme),
            "compare_to": type(compare_to).__name__ if compare_to is not None else None,
        },
        "tables": manifest_tables,
        "figures": figures_manifest,
    }
    _write_json(output_root / "manifest.json", manifest)
    return output_root


def _build_metadata_summary(sample_set: "SampleSetBase[Any]", metadata_frame: pd.DataFrame) -> dict[str, Any]:
    return {
        "sample_set_type": type(sample_set).__name__,
        "sample_type": sample_set.sample_type.__name__,
        "sample_count": len(sample_set),
        "uids": list(sample_set.keys()),
        "metadata_columns": [str(column) for column in metadata_frame.columns],
    }


def _comparison_frames(report: "SampleSetComparisonReport") -> dict[str, pd.DataFrame]:
    return {
        "metadata_diff": report.metadata_diff,
        "presence_diff": report.presence_diff,
        "scalar_diff": report.scalar_diff,
    }


def _build_compare_data_vars(eval_data_vars: Iterable[str]) -> list[str]:
    seen: list[str] = []
    for name in eval_data_vars:
        normalized = str(name)
        if normalized not in seen:
            seen.append(normalized)
    return seen


def _detect_available_eval_data_vars(sample_set: "SampleSetBase[Any]") -> tuple[str, ...]:
    available: list[str] = []
    for data_var in _DEFAULT_EVAL_DATA_VARS:
        if any(sample.get_data_var(data_var) is not None for sample in sample_set.values()):
            available.append(data_var)
    return tuple(available)


def _filter_scalar_data_vars(
    sample_set: "SampleSetBase[Any]",
    data_vars: Iterable[str],
) -> tuple[str, ...]:
    scalar_vars: list[str] = []
    for data_var in data_vars:
        if _is_scalar_data_var(sample_set, data_var):
            scalar_vars.append(str(data_var))
    return tuple(scalar_vars)


def _is_scalar_data_var(sample_set: "SampleSetBase[Any]", data_var: str) -> bool:
    for sample in sample_set.values():
        model = sample.get_data_var(data_var)
        if model is None:
            continue
        try:
            model.to_scalar_record()
        except Exception:  # noqa: BLE001
            return False
        return True
    return False


def _export_scalar_summary_figures(
    frame: pd.DataFrame,
    *,
    figures_dir: Path,
    theme_override: PlotTheme | str | Path | None,
) -> list[dict[str, Any]]:
    if frame.empty:
        return []
    labels = _resolve_sample_labels(frame)
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
        title = f"{column} 统计"
        filename = f"scalar_{_slugify(column)}.png"
        manifest.append(
            _render_plot_figure(
                dataset=dataset,
                plotter=FramePlotter(theme=_resolve_theme("report", theme_override)),
                path=figures_dir / filename,
                title=title,
                theme_name=_resolve_theme_name("report", theme_override),
                xtick_labels=labels,
            )
        )
    return manifest


def _export_series_figures(
    frame: pd.DataFrame,
    *,
    data_var: str,
    figures_dir: Path,
    theme_override: PlotTheme | str | Path | None,
) -> list[dict[str, Any]]:
    if frame.empty:
        return []
    dataset = PlotDataset()
    for column in frame.columns:
        values = pd.to_numeric(frame[column], errors="coerce")
        if values.notna().sum() == 0:
            continue
        flattened = _flatten_label(column)
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
    title = f"{data_var} 序列"
    filename = f"series_{_slugify(data_var)}.png"
    return [
        _render_plot_figure(
            dataset=dataset,
            plotter=FramePlotter(theme=_resolve_theme("report", theme_override)),
            path=figures_dir / filename,
            title=title,
            theme_name=_resolve_theme_name("report", theme_override),
        )
    ]


def _export_peaks_figures(
    frame: pd.DataFrame,
    *,
    source: str,
    figures_dir: Path,
    theme_override: PlotTheme | str | Path | None,
) -> list[dict[str, Any]]:
    if frame.empty:
        return []
    dataset = PlotDataset()
    for column in frame.columns:
        flattened = _flatten_label(column)
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
    title = f"{source} 峰值"
    filename = f"peaks_{_slugify(source)}.png"
    return [
        _render_plot_figure(
            dataset=dataset,
            plotter=FramePlotter(theme=_resolve_theme("report", theme_override)),
            path=figures_dir / filename,
            title=title,
            theme_name=_resolve_theme_name("report", theme_override),
        )
    ]


def _export_otovl_figures(
    sample_set: "SampleSetBase[Any]",
    *,
    figures_dir: Path,
    theme_override: PlotTheme | str | Path | None,
) -> list[dict[str, Any]]:
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
    filename = "otovl_overview.png"
    return [
        _render_plot_figure(
            dataset=dataset,
            plotter=OneThirdOctavePlotter(theme=_resolve_theme("one_third_octave", theme_override)),
            path=figures_dir / filename,
            title="1/3 倍频程振级概览",
            theme_name=_resolve_theme_name("one_third_octave", theme_override),
        )
    ]


def _render_plot_figure(
    *,
    dataset: PlotDataset,
    plotter: Any,
    path: Path,
    title: str,
    theme_name: str,
    xtick_labels: list[str] | None = None,
) -> dict[str, Any]:
    result = plotter.plot_dataset(dataset, legend_options={})
    if result.ax is not None:
        result.ax.set_title(title)
        if xtick_labels is not None:
            result.ax.set_xticks(np.arange(1, len(xtick_labels) + 1, dtype=float))
            result.ax.set_xticklabels(xtick_labels, rotation=30, ha="right")
    if result.figure is None:
        raise RuntimeError("plot_dataset() 未返回 figure，无法导出图件")
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


def _resolve_sample_labels(frame: pd.DataFrame) -> list[str]:
    if "alias" in frame.columns:
        labels = [str(item).strip() for item in frame["alias"].fillna("").tolist()]
        if any(label for label in labels):
            return [label or str(uid) for label, uid in zip(labels, frame["uid"].tolist(), strict=False)]
    if "uid" in frame.columns:
        return [str(item) for item in frame["uid"].tolist()]
    return [str(index) for index in range(1, len(frame) + 1)]


def _resolve_theme(theme_kind: str, theme_override: PlotTheme | str | Path | None) -> PlotTheme:
    if isinstance(theme_override, PlotTheme):
        return theme_override
    if isinstance(theme_override, (str, Path)):
        return PlotTheme.from_file(theme_override)
    if theme_kind == "one_third_octave":
        return PlotTheme.from_file(_THEME_DIR / _OTOVL_THEME_NAME)
    return PlotTheme.from_file(_THEME_DIR / _REPORT_THEME_NAME)


def _resolve_theme_name(theme_kind: str, theme_override: PlotTheme | str | Path | None) -> str:
    if isinstance(theme_override, PlotTheme):
        return "custom_plot_theme"
    if isinstance(theme_override, (str, Path)):
        return Path(theme_override).name
    if theme_kind == "one_third_octave":
        return _OTOVL_THEME_NAME
    return _REPORT_THEME_NAME


def _theme_manifest_value(theme_override: PlotTheme | str | Path | None) -> str | None:
    if theme_override is None:
        return None
    if isinstance(theme_override, PlotTheme):
        return "custom_plot_theme"
    return str(theme_override)


def _frame_manifest_entry(name: str, path: Path, frame: pd.DataFrame) -> dict[str, Any]:
    flattened = _flatten_frame_for_export(frame)
    return {
        "name": name,
        "path": str(path.relative_to(path.parents[1])).replace("\\", "/"),
        "rows": int(flattened.shape[0]),
        "columns": [str(column) for column in flattened.columns],
    }


def _resolve_file_path(output_path: str | Path, *, format: ExportFormat) -> Path:
    target = Path(output_path)
    suffix = f".{format}"
    if target.suffix.lower() != suffix:
        target = target.with_suffix(suffix)
    target.parent.mkdir(parents=True, exist_ok=True)
    return target


def _resolve_dir_path(output_path: str | Path) -> Path:
    target = Path(output_path)
    if target.suffix:
        target = target.with_suffix("")
    return target


def _write_single_frame(
    frame: pd.DataFrame,
    path: Path,
    *,
    format: ExportFormat,
    sheet_name: str,
) -> None:
    if format == "csv":
        _write_frame_csv(frame, path)
        return
    _write_frames_workbook({sheet_name: frame}, path)


def _write_frame_csv(frame: pd.DataFrame, path: Path, *, encoding: str = "utf-8-sig") -> None:
    export_frame = _flatten_frame_for_export(frame)
    path.parent.mkdir(parents=True, exist_ok=True)
    export_frame.to_csv(path, index=False, encoding=encoding)


def _write_frames_workbook(frames: Mapping[str, pd.DataFrame], path: Path) -> None:
    _require_openpyxl()
    path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        for sheet_name, frame in frames.items():
            export_frame = _flatten_frame_for_export(frame)
            export_frame.to_excel(writer, sheet_name=_safe_sheet_name(sheet_name), index=False)
    _style_workbook(path)


def _flatten_frame_for_export(frame: pd.DataFrame) -> pd.DataFrame:
    export_frame = frame.copy()
    if isinstance(export_frame.index, pd.MultiIndex) or export_frame.index.name is not None:
        export_frame = export_frame.reset_index()
    elif not isinstance(export_frame.index, pd.RangeIndex):
        export_frame = export_frame.reset_index()
    export_frame.columns = [_flatten_label(column) for column in export_frame.columns]
    return export_frame


def _flatten_label(value: Any) -> str:
    if isinstance(value, tuple):
        parts = [str(item) for item in value if str(item)]
        return "@".join(parts)
    return str(value)


def _slugify(value: str) -> str:
    cleaned = re.sub(r"[^0-9A-Za-z_\-]+", "_", value.strip())
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    return cleaned or "figure"


def _safe_sheet_name(name: str) -> str:
    cleaned = re.sub(r"[:\\\\/?*\\[\\]]", "_", name)
    return cleaned[:31] or "sheet"


def _require_openpyxl() -> None:
    try:
        import openpyxl  # noqa: F401
    except ModuleNotFoundError as exc:
        raise RuntimeError("导出 xlsx 需要安装 openpyxl 依赖") from exc


def _style_workbook(path: Path) -> None:
    from openpyxl import load_workbook
    from openpyxl.styles import Font

    workbook = load_workbook(path)
    for worksheet in workbook.worksheets:
        worksheet.freeze_panes = "A2"
        for cell in worksheet[1]:
            cell.font = Font(bold=True)
        for column_cells in worksheet.columns:
            values = ["" if cell.value is None else str(cell.value) for cell in column_cells]
            width = min(max(len(item) for item in values) + 2, 60)
            worksheet.column_dimensions[column_cells[0].column_letter].width = max(width, 10)
    workbook.save(path)


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


__all__ = [
    "export_compare_report",
    "export_peaks_frame",
    "export_report_package",
    "export_scalar_frame",
    "export_series_frame",
]
