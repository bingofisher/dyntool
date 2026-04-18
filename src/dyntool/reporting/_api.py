"""reporting 正式导出接口实现。"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterable

import pandas as pd

from ._figure_export import (
    export_otovl_figures,
    export_peaks_figures,
    export_scalar_summary_figures,
    export_series_figures,
    theme_manifest_value,
)
from ._frame_builders import (
    DEFAULT_SCALAR_FEATURES,
    build_compare_data_vars,
    build_metadata_summary,
    comparison_frames,
    detect_available_eval_data_vars,
    filter_scalar_data_vars,
)
from ._writers import (
    ExportFormat,
    frame_manifest_entry,
    resolve_dir_path,
    resolve_file_path,
    write_frame_csv,
    write_frames_workbook,
    write_json,
    write_single_frame,
)

if TYPE_CHECKING:
    from ..domain.samples import SampleSetBase
    from ..plotting import PlotTheme


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
    target = resolve_file_path(output_path, format=format)
    write_single_frame(frame, target, format=format, sheet_name="scalar_frame")
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
    target = resolve_file_path(output_path, format=format)
    write_single_frame(frame, target, format=format, sheet_name="series_frame")
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
    target = resolve_file_path(output_path, format=format)
    write_single_frame(frame, target, format=format, sheet_name="peaks_frame")
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
    frames = comparison_frames(report)
    if format == "xlsx":
        target = resolve_file_path(output_path, format="xlsx")
        write_frames_workbook(frames, target)
        return target
    target_dir = resolve_dir_path(output_path)
    target_dir.mkdir(parents=True, exist_ok=True)
    for name, frame in frames.items():
        write_frame_csv(frame, target_dir / f"{name}.csv")
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
    plot_theme: "PlotTheme | str | Path | None" = None,
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
    metadata_summary = build_metadata_summary(sample_set, metadata_frame)
    write_json(output_root / "metadata_summary.json", metadata_summary)

    requested_features = tuple(str(item) for item in (features or DEFAULT_SCALAR_FEATURES))
    requested_series_vars = tuple(str(item) for item in (series_vars or ()))
    requested_peak_sources = tuple(str(item) for item in (peak_sources or ()))
    eval_data_vars = detect_available_eval_data_vars(sample_set) if include_eval_summary else tuple()
    scalar_eval_data_vars = filter_scalar_data_vars(sample_set, eval_data_vars)

    workbook_frames: dict[str, pd.DataFrame] = {}
    manifest_tables: list[dict[str, Any]] = []

    workbook_frames["metadata_summary"] = metadata_frame
    write_frame_csv(metadata_frame, tables_dir / "metadata_summary.csv", encoding=csv_encoding)
    manifest_tables.append(
        frame_manifest_entry("metadata_summary", tables_dir / "metadata_summary.csv", metadata_frame)
    )

    scalar_frame = sample_set.scalar_frame(features=requested_features, strict=False)
    workbook_frames["scalar_frame"] = scalar_frame
    write_frame_csv(scalar_frame, tables_dir / "scalar_frame.csv", encoding=csv_encoding)
    manifest_tables.append(frame_manifest_entry("scalar_frame", tables_dir / "scalar_frame.csv", scalar_frame))

    series_frames: dict[str, pd.DataFrame] = {}
    for data_var in requested_series_vars:
        frame = sample_set.series_frame(data_var, strict=False)
        if frame.empty:
            continue
        sheet_name = f"series_{data_var}"
        workbook_frames[sheet_name] = frame
        csv_path = tables_dir / f"{sheet_name}.csv"
        write_frame_csv(frame, csv_path, encoding=csv_encoding)
        series_frames[data_var] = frame
        manifest_tables.append(frame_manifest_entry(sheet_name, csv_path, frame))

    peaks_frames: dict[str, pd.DataFrame] = {}
    for source in requested_peak_sources:
        try:
            frame = sample_set.peaks_frame(source=source, strict=False)
        except ValueError:
            continue
        if frame.empty:
            continue
        sheet_name = f"peaks_{source}"
        workbook_frames[sheet_name] = frame
        csv_path = tables_dir / f"{sheet_name}.csv"
        write_frame_csv(frame, csv_path, encoding=csv_encoding)
        peaks_frames[source] = frame
        manifest_tables.append(frame_manifest_entry(sheet_name, csv_path, frame))

    if compare_to is not None:
        compare_report = sample_set.compare_with(
            compare_to,
            data_vars=build_compare_data_vars(scalar_eval_data_vars),
            features=requested_features,
        )
        for frame_name, frame in comparison_frames(compare_report).items():
            sheet_name = f"compare_{frame_name}"
            workbook_frames[sheet_name] = frame
            csv_path = tables_dir / f"{sheet_name}.csv"
            write_frame_csv(frame, csv_path, encoding=csv_encoding)
            manifest_tables.append(frame_manifest_entry(sheet_name, csv_path, frame))

    if scalar_eval_data_vars:
        eval_summary = sample_set.scalar_frame(data_vars=scalar_eval_data_vars, strict=False)
        workbook_frames["eval_summary"] = eval_summary
        csv_path = tables_dir / "eval_summary.csv"
        write_frame_csv(eval_summary, csv_path, encoding=csv_encoding)
        manifest_tables.append(frame_manifest_entry("eval_summary", csv_path, eval_summary))

    figures_manifest: list[dict[str, Any]] = []
    if include_plots:
        figures_manifest.extend(
            export_scalar_summary_figures(
                scalar_frame,
                figures_dir=figures_dir,
                theme_override=plot_theme,
            )
        )
        for data_var, frame in series_frames.items():
            figures_manifest.extend(
                export_series_figures(
                    frame,
                    data_var=data_var,
                    figures_dir=figures_dir,
                    theme_override=plot_theme,
                )
            )
        for source, frame in peaks_frames.items():
            figures_manifest.extend(
                export_peaks_figures(
                    frame,
                    source=source,
                    figures_dir=figures_dir,
                    theme_override=plot_theme,
                )
            )
        figures_manifest.extend(
            export_otovl_figures(
                sample_set,
                figures_dir=figures_dir,
                theme_override=plot_theme,
            )
        )

    figures_index_frame = pd.DataFrame(figures_manifest)
    if not figures_index_frame.empty:
        workbook_frames["figures_index"] = figures_index_frame
        figures_index_path = figures_dir / "figures_index.csv"
        write_frame_csv(figures_index_frame, figures_index_path, encoding=csv_encoding)
        manifest_tables.append(frame_manifest_entry("figures_index", figures_index_path, figures_index_frame))
    else:
        workbook_frames["figures_index"] = pd.DataFrame(columns=["name", "path", "plotter", "theme", "title"])

    workbook_path = output_root / "report.xlsx"
    write_frames_workbook(workbook_frames, workbook_path)

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
            "plot_theme": theme_manifest_value(plot_theme),
            "compare_to": type(compare_to).__name__ if compare_to is not None else None,
        },
        "tables": manifest_tables,
        "figures": figures_manifest,
    }
    write_json(output_root / "manifest.json", manifest)
    return output_root


__all__ = [
    "export_compare_report",
    "export_peaks_frame",
    "export_report_package",
    "export_scalar_frame",
    "export_series_frame",
]
