"""reporting 写出与清单工具。"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Literal, Mapping

import pandas as pd

from ..infrastructure._storage_commit import _FileCommit

ExportFormat = Literal["csv", "xlsx"]


def frame_manifest_entry(name: str, path: Path, frame: pd.DataFrame) -> dict[str, Any]:
    """生成导出表格的 manifest 条目。"""

    flattened = flatten_frame_for_export(frame)
    return {
        "name": name,
        "path": str(path.relative_to(path.parents[1])).replace("\\", "/"),
        "rows": int(flattened.shape[0]),
        "columns": [str(column) for column in flattened.columns],
        "units": {flatten_label(column): unit for column, unit in frame.attrs.get("column_units", {}).items()},
        "index_unit": frame.attrs.get("index_unit"),
    }


def resolve_file_path(output_path: str | Path, *, format: ExportFormat) -> Path:
    """规范化单文件导出路径。"""

    target = Path(output_path)
    suffix = f".{format}"
    if target.suffix.lower() != suffix:
        target = target.with_suffix(suffix)
    target.parent.mkdir(parents=True, exist_ok=True)
    return target


def resolve_dir_path(output_path: str | Path) -> Path:
    """规范化目录导出路径。"""

    target = Path(output_path)
    if target.suffix:
        target = target.with_suffix("")
    return target


def write_single_frame(
    frame: pd.DataFrame,
    path: Path,
    *,
    format: ExportFormat,
    sheet_name: str,
) -> None:
    """按指定格式导出单张表。"""

    if format == "csv":
        write_frame_csv(frame, path)
        return
    write_frames_workbook({sheet_name: frame}, path)


def write_frame_csv(frame: pd.DataFrame, path: Path, *, encoding: str = "utf-8-sig") -> None:
    """导出 CSV 表格。"""

    export_frame = flatten_frame_for_export(frame)
    path.parent.mkdir(parents=True, exist_ok=True)
    with _FileCommit(path.parent, "导出 CSV") as commit:
        export_frame.to_csv(commit.stage(path), index=False, encoding=encoding)
        commit.commit()


def write_frames_workbook(frames: Mapping[str, pd.DataFrame], path: Path) -> None:
    """导出 Excel workbook。"""

    require_openpyxl()
    path.parent.mkdir(parents=True, exist_ok=True)
    with _FileCommit(path.parent, "导出 Excel") as commit:
        staged = commit.stage(path)
        with pd.ExcelWriter(staged, engine="openpyxl") as writer:
            descriptions = []
            for sheet_name, frame in frames.items():
                export_frame = flatten_frame_for_export(frame)
                export_frame.to_excel(writer, sheet_name=safe_sheet_name(sheet_name), index=False)
                descriptions.extend(
                    {"表": sheet_name, "字段": flatten_label(column), "单位": unit}
                    for column, unit in frame.attrs.get("column_units", {}).items()
                )
                if frame.attrs.get("index_unit"):
                    descriptions.append(
                        {"表": sheet_name, "字段": str(frame.index.name), "单位": frame.attrs["index_unit"]}
                    )
            pd.DataFrame(descriptions, columns=["表", "字段", "单位"]).to_excel(
                writer, sheet_name="单位说明", index=False
            )
        style_workbook(staged)
        commit.commit()


def flatten_frame_for_export(frame: pd.DataFrame) -> pd.DataFrame:
    """将 DataFrame 展平到稳定导出形态。"""

    export_frame = frame.copy()
    if isinstance(export_frame.index, pd.MultiIndex) or export_frame.index.name is not None:
        export_frame = export_frame.reset_index()
    elif not isinstance(export_frame.index, pd.RangeIndex):
        export_frame = export_frame.reset_index()
    units = frame.attrs.get("column_units", {})
    index_unit = frame.attrs.get("index_unit")
    export_frame.columns = [
        f"{flatten_label(column)} [{unit}]"
        if (unit := units.get(column) or (index_unit if column == frame.index.name else None))
        else flatten_label(column)
        for column in export_frame.columns
    ]
    return export_frame


def flatten_label(value: Any) -> str:
    """将 tuple / 多级列标签拍平成稳定字符串。"""

    if isinstance(value, tuple):
        parts = [str(item) for item in value if str(item)]
        return "@".join(parts)
    return str(value)


def slugify(value: str) -> str:
    """将标题或字段名转成稳定文件名。"""

    cleaned = re.sub(r"[^0-9A-Za-z_\\-]+", "_", value.strip())
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    return cleaned or "figure"


def safe_sheet_name(name: str) -> str:
    """将 sheet 名裁剪为 Excel 可接受的形式。"""

    cleaned = re.sub(r"[:\\\\/?*\\[\\]]", "_", name)
    return cleaned[:31] or "sheet"


def require_openpyxl() -> None:
    """确保 xlsx 依赖可用。"""

    try:
        import openpyxl  # noqa: F401
    except ModuleNotFoundError as exc:
        raise RuntimeError("导出 xlsx 需要安装 openpyxl 依赖") from exc


def style_workbook(path: Path) -> None:
    """对 workbook 应用统一表头样式与列宽。"""

    from openpyxl import load_workbook
    from openpyxl.styles import Font

    workbook = load_workbook(path)
    try:
        for worksheet in workbook.worksheets:
            worksheet.freeze_panes = "A2"
            for cell in worksheet[1]:
                cell.font = Font(bold=True)
            for column_cells in worksheet.columns:
                values = ["" if cell.value is None else str(cell.value) for cell in column_cells]
                width = min(max(len(item) for item in values) + 2, 60)
                worksheet.column_dimensions[column_cells[0].column_letter].width = max(width, 10)
        workbook.save(path)
    finally:
        workbook.close()


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    """导出 UTF-8 JSON 文件。"""

    with _FileCommit(path.parent, "导出 JSON") as commit:
        commit.stage(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        commit.commit()


__all__ = [
    "ExportFormat",
    "flatten_label",
    "frame_manifest_entry",
    "resolve_dir_path",
    "resolve_file_path",
    "slugify",
    "write_frame_csv",
    "write_frames_workbook",
    "write_json",
    "write_single_frame",
]
