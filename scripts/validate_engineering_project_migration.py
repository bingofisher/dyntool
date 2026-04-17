"""工程项目迁移验证脚本。

该脚本用于基于真实工程项目输入目录，验证 `v1.2.0` 主链对工程项目的迁移覆盖度：

- 时程 txt 文件解析
- 样本集组织
- `connect_storage -> save_all -> load_all`
- `export_scalar_frame`
- `export_report_package`
- 与现有结果层的键值映射对比

说明：
- 这是内部验证脚本，不属于正式公开 API。
- 默认只验证用户锁定的 3 个工程目录。
- 不做外部软件结果提取。
"""

from __future__ import annotations

import argparse
import json
import math
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Literal

import pandas as pd

from dyntool import AccelSeries
from dyntool.domain.metadata import VibrationTestMetadata
from dyntool.domain.samples import VibrationTestSample, VibrationTestSampleSet
from dyntool.reporting import export_report_package, export_scalar_frame
from dyntool.storage import StorageMode, StorageScheme

INPUT_KIND_TIME_ACCEL_CSV = "time_accel_csv"
INPUT_KIND_ACCEL_COLUMN = "accel_column"

RESULT_KEY_COLUMNS = (
    "casetag",
    "pointtag",
    "wavetag",
    "drcttag",
    "instrument",
    "timestamp",
)

_WAVE_FILENAME_PATTERN = re.compile(
    r"^C-(?P<case>.+?)_W-(?P<wave>[^_]+)_P-(?P<point>[^_]+)_I-(?P<instr>[^_]+)_T-(?P<timestamp>\d{14})_D-(?P<direction>[^.]+)\.txt$",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class WaveFilenameInfo:
    """振动波文件名解析结果。"""

    case: str
    wave: str
    point: str
    instr: str
    timestamp: str
    direction: str


@dataclass(frozen=True, slots=True)
class ProjectSpec:
    """工程项目迁移验证规格。"""

    project_id: str
    label: str
    input_dir: Path
    input_kind: Literal["time_accel_csv", "accel_column"]
    dt: float | None
    migration_cost: Literal["low", "medium", "high"]
    compare_files: dict[str, Path]
    direct_result_anchor: Path | None
    split_table_anchor: Path | None
    split_wave_column: str | None
    result_key_adapter: Callable[[WaveFilenameInfo], dict[str, str]] | None = None
    migration_notes: tuple[str, ...] = ()


@dataclass(slots=True)
class ProjectValidationSummary:
    """单个项目的迁移验证摘要。"""

    project_id: str
    label: str
    input_dir: str
    input_kind: str
    dt: float | None
    input_file_count: int
    parsed_file_count: int
    parsed_coverage: float
    subset_size: int
    compare_file_status: dict[str, bool]
    direct_result_alignment: dict[str, Any] | None
    split_table_alignment: dict[str, Any] | None
    storage_dir: str
    scalar_export_path: str
    report_package_dir: str
    report_compare: dict[str, Any]
    sample_set_plan: dict[str, Any]
    plotting_cost_is_primary: bool
    reporting_can_replace_export_chain: bool
    migration_cost: str
    estimated_person_days: str
    migration_notes: list[str]


def build_project_specs() -> tuple[ProjectSpec, ...]:
    """返回固定的工程项目迁移验证规格。"""

    pr25_root = Path(r"E:\22_WorkingProjects\P-R2-5_科学城别墅地铁振动测试-广州地铁院\C_数据分析")
    pr26_root = Path(r"E:\22_WorkingProjects\P-R2-6_广州白云站高铁振动测试-铁四院\C_数据分析")
    pr27_root = Path(r"E:\22_WorkingProjects\P-R2-7_西安环园中路车辆段振震双控设计\A_振动噪声测试\C_数据分析")
    return (
        ProjectSpec(
            project_id="P-R2-5",
            label="科学城别墅地铁振动测试",
            input_dir=pr25_root / "12-D_地铁波数据",
            input_kind=INPUT_KIND_TIME_ACCEL_CSV,
            dt=None,
            migration_cost="low",
            compare_files={
                "工况筛选表": pr25_root / "工况筛选表.csv",
                "地铁波分割表": pr25_root / "地铁波分割表.csv",
                "Z振级数据": pr25_root / "Z振级数据.csv",
                "分频最大振级数据": pr25_root / "分频最大振级数据.csv",
                "测点数据汇总": pr25_root / "测点数据汇总.xlsx",
            },
            direct_result_anchor=pr25_root / "Z振级数据.csv",
            split_table_anchor=pr25_root / "地铁波分割表.csv",
            split_wave_column="地铁波",
            migration_notes=(
                "原始文件名可直接映射到 Z 振级结果层主键。",
                "时程文件自带时间列，导入不需要额外补 dt。",
                "split 表中的地铁波编号属于派生结果，不是原始文件名直出字段。",
            ),
        ),
        ProjectSpec(
            project_id="P-R2-6",
            label="广州白云站高铁振动测试",
            input_dir=pr26_root / "D21_振动波时程数据",
            input_kind=INPUT_KIND_ACCEL_COLUMN,
            dt=0.01,
            migration_cost="medium",
            compare_files={
                "振动波分割表": pr26_root / "Z21_振动波分割表.csv",
                "振动波信息表": pr26_root / "Z22_振动波信息表.csv",
                "Z振级数据": pr26_root / "D31_Z振级数据.csv",
                "三分之一分频振级数据": pr26_root / "D32_三分之一分频振级数据-合并.csv",
                "测试报告数据": pr26_root / "D90_测试报告数据.xlsx",
            },
            direct_result_anchor=pr26_root / "D31_Z振级数据.csv",
            split_table_anchor=pr26_root / "Z21_振动波分割表.csv",
            split_wave_column="振动波",
            migration_notes=(
                "原始文件只有加速度列，项目侧需要固定 dt=0.01。",
                "原始文件名可直接映射到 D31 结果层主键。",
                "批量规模更大，成本主要来自批量导入、存储和报告包吞吐。",
            ),
        ),
        ProjectSpec(
            project_id="P-R2-7",
            label="西安环园中路车辆段振震双控设计",
            input_dir=pr27_root / "D21_振动波时程数据",
            input_kind=INPUT_KIND_ACCEL_COLUMN,
            dt=0.002,
            migration_cost="high",
            compare_files={
                "振动波分割表": pr27_root / "Z21_振动波分割表.csv",
                "振动波信息表": pr27_root / "Z22_振动波信息表.csv",
                "Z振级数据": pr27_root / "D31_Z振级数据.csv",
                "测试报告数据": pr27_root / "D90_测试报告数据.xlsx",
            },
            direct_result_anchor=pr27_root / "D31_Z振级数据.csv",
            split_table_anchor=pr27_root / "Z21_振动波分割表.csv",
            split_wave_column="地铁波",
            result_key_adapter=_adapt_pr27_result_keys,
            migration_notes=(
                "原始文件只有加速度列，项目侧需要固定 dt=0.002。",
                "原始文件名可直接映射到 split 表，但 D31 结果层使用了归一化工况/波号。",
                "成本主要来自结果层适配和测试链嵌入更大工程目录的组织方式。",
            ),
        ),
    )


def parse_wave_filename(filename: str) -> WaveFilenameInfo:
    """解析工程项目振动波 txt 文件名。"""

    match = _WAVE_FILENAME_PATTERN.match(Path(filename).name)
    if match is None:
        raise ValueError(f"无法解析振动波文件名: {filename}")
    payload = match.groupdict()
    return WaveFilenameInfo(
        case=payload["case"].strip(),
        wave=payload["wave"].strip(),
        point=payload["point"].strip(),
        instr=payload["instr"].strip(),
        timestamp=payload["timestamp"].strip(),
        direction=payload["direction"].strip(),
    )


def read_wave_txt(
    path: str | Path,
    input_kind: Literal["time_accel_csv", "accel_column"],
    *,
    dt: float | None,
) -> pd.DataFrame:
    """读取振动波 txt 文件并统一为 `time/accel` 两列。"""

    target = Path(path)
    frame = _read_text_table(target)
    if input_kind == INPUT_KIND_TIME_ACCEL_CSV:
        if frame.shape[1] < 2:
            raise ValueError(f"双列时程文件至少应包含两列: {target}")
        out = frame.iloc[:, :2].copy()
        out.columns = ["time", "accel"]
        out = out.apply(pd.to_numeric, errors="raise")
        return out
    if input_kind == INPUT_KIND_ACCEL_COLUMN:
        if dt is None:
            raise ValueError("单列振动波文件必须显式提供 dt")
        if frame.shape[1] < 1:
            raise ValueError(f"单列振动波文件至少应包含一列: {target}")
        accel = pd.to_numeric(frame.iloc[:, 0], errors="raise")
        time = pd.Series(range(len(accel)), dtype=float) * float(dt)
        return pd.DataFrame({"time": time, "accel": accel.to_numpy(dtype=float)})
    raise ValueError(f"不支持的输入类型: {input_kind}")


def build_result_key_frame(
    source: pd.DataFrame,
    key_columns: tuple[str, ...] = RESULT_KEY_COLUMNS,
) -> pd.DataFrame:
    """从结果表中抽取主键列并统一为字符串。"""

    missing = [column for column in key_columns if column not in source.columns]
    if missing:
        raise ValueError(f"结果表缺少主键列: {missing}")
    out = source.loc[:, list(key_columns)].copy()
    for column in key_columns:
        out[column] = out[column].map(_normalize_key_value)
    return out.drop_duplicates(ignore_index=True)


def build_raw_result_join_frame(
    parsed_items: list[WaveFilenameInfo],
    adapter: Callable[[WaveFilenameInfo], dict[str, str]] | None,
) -> pd.DataFrame:
    """根据原始文件名构造可与结果层对齐的键值表。"""

    records: list[dict[str, str]] = []
    for item in parsed_items:
        if adapter is not None:
            record = adapter(item)
        else:
            record = {
                "casetag": item.case,
                "pointtag": item.point,
                "wavetag": item.wave,
                "drcttag": item.direction,
                "instrument": item.instr,
                "timestamp": item.timestamp,
            }
        records.append({column: _normalize_key_value(record[column]) for column in RESULT_KEY_COLUMNS})
    return pd.DataFrame.from_records(records, columns=list(RESULT_KEY_COLUMNS)).drop_duplicates(ignore_index=True)


def build_sample_from_wave_file(path: str | Path, spec: ProjectSpec) -> VibrationTestSample:
    """根据工程项目时程文件创建振动测试样本。"""

    target = Path(path)
    parsed = parse_wave_filename(target.name)
    frame = read_wave_txt(target, spec.input_kind, dt=spec.dt)
    metadata = VibrationTestMetadata(
        case=parsed.case,
        point=parsed.point,
        instr=parsed.instr,
        dir=parsed.direction,
        record=parsed.wave,
        timestamp=parsed.timestamp,
        extra={
            "project_id": spec.project_id,
            "project_label": spec.label,
            "source_file": str(target),
        },
    )
    accel = AccelSeries.from_data(
        frame["accel"].to_numpy(dtype=float),
        dt=_infer_dt(frame),
        axis_unit="second",
        data_unit="meter/second**2",
    )
    return VibrationTestSample(metadata=metadata, accel=accel)


def build_project_migration_matrix(
    output_root: str | Path,
    *,
    project_ids: list[str] | None = None,
    subset_size: int = 24,
) -> dict[str, Any]:
    """构建工程项目迁移矩阵。"""

    output_dir = Path(output_root).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    specs = list(build_project_specs())
    selected_specs = [spec for spec in specs if project_ids is None or spec.project_id in set(project_ids)]
    if not selected_specs:
        raise ValueError("没有匹配的项目规格")

    summaries = [
        run_project_validation(spec, output_dir=output_dir, subset_size=subset_size) for spec in selected_specs
    ]
    matrix = {
        "version_line": "v1.2.0",
        "evaluation_target": "engineering_project_migration",
        "projects": [asdict(summary) for summary in summaries],
    }
    (output_dir / "migration_matrix.json").write_text(
        json.dumps(matrix, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return matrix


def run_project_validation(
    spec: ProjectSpec,
    *,
    output_dir: Path,
    subset_size: int,
) -> ProjectValidationSummary:
    """执行单个工程项目的迁移验证。"""

    input_files = sorted(spec.input_dir.glob("*.txt"))
    parsed_items: list[WaveFilenameInfo] = []
    parse_errors: list[str] = []
    for file_path in input_files:
        try:
            parsed_items.append(parse_wave_filename(file_path.name))
        except ValueError as exc:
            parse_errors.append(f"{file_path.name}: {exc}")
    subset_files = input_files[: min(subset_size, len(input_files))]

    samples = [build_sample_from_wave_file(file_path, spec) for file_path in subset_files]
    sample_set = VibrationTestSampleSet.from_samples(samples)
    sample_set.eval_zvl(overwrite=True, freq_range=(2.0, 80.0))

    project_output = output_dir / spec.project_id
    project_output.mkdir(parents=True, exist_ok=True)

    storage_dir = project_output / "storage"
    sample_set.connect_storage(
        storage_dir,
        storage_scheme=StorageScheme.SET_SQLITE_H5,
        mode=StorageMode.CREATE,
    )
    sample_set.save_all(show_progress=False)

    loaded = VibrationTestSampleSet()
    loaded.connect_storage(storage_dir, storage_scheme=StorageScheme.SET_SQLITE_H5)
    loaded.load_all(show_progress=False, categories=["accel", "zvl"])
    compare_report = sample_set.compare_with(
        loaded,
        data_vars=["zvl"],
        features=["pga", "rms"],
    )

    scalar_export_path = export_scalar_frame(
        loaded,
        project_output / "scalar_frame.xlsx",
        features=["pga", "rms"],
        data_vars=["zvl"],
        strict=False,
        format="xlsx",
    )
    report_package_dir = export_report_package(
        loaded,
        project_output / "report_package",
        features=["pga", "rms"],
        include_eval_summary=True,
        include_plots=True,
    )

    compare_file_status = {name: path.exists() for name, path in spec.compare_files.items()}
    direct_result_alignment = _build_direct_result_alignment(spec, parsed_items)
    split_table_alignment = _build_split_table_alignment(spec, parsed_items)

    parsed_coverage = float(len(parsed_items)) / float(len(input_files)) if input_files else 0.0
    return ProjectValidationSummary(
        project_id=spec.project_id,
        label=spec.label,
        input_dir=str(spec.input_dir),
        input_kind=spec.input_kind,
        dt=spec.dt,
        input_file_count=len(input_files),
        parsed_file_count=len(parsed_items),
        parsed_coverage=round(parsed_coverage, 4),
        subset_size=len(subset_files),
        compare_file_status=compare_file_status,
        direct_result_alignment=direct_result_alignment,
        split_table_alignment=split_table_alignment,
        storage_dir=str(storage_dir),
        scalar_export_path=str(scalar_export_path),
        report_package_dir=str(report_package_dir),
        report_compare=_comparison_report_summary(compare_report),
        sample_set_plan=_sample_set_plan_summary(samples),
        plotting_cost_is_primary=False,
        reporting_can_replace_export_chain=True,
        migration_cost=spec.migration_cost,
        estimated_person_days=_estimate_person_days(spec.migration_cost),
        migration_notes=[
            *spec.migration_notes,
            *parse_errors[:5],
        ],
    )


def _adapt_pr27_result_keys(item: WaveFilenameInfo) -> dict[str, str]:
    """将 P-R2-7 原始命名适配到 D31 结果层键。"""

    match = re.fullmatch(r"L(?P<wave>\d+)-(?P<suffix>[A-Z])", item.case)
    if match is None:
        raise ValueError(f"P-R2-7 工况号不满足已知适配规则: {item.case}")
    return {
        "casetag": f"A{match.group('suffix')}",
        "pointtag": item.point,
        "wavetag": match.group("wave"),
        "drcttag": item.direction,
        "instrument": item.instr,
        "timestamp": item.timestamp,
    }


def _read_text_table(path: Path) -> pd.DataFrame:
    """按多种常见编码读取工程项目文本表。"""

    last_error: Exception | None = None
    for encoding in ("utf-8", "utf-8-sig", "gbk", "gb18030"):
        try:
            return pd.read_csv(path, encoding=encoding)
        except Exception as exc:  # noqa: BLE001
            last_error = exc
    raise ValueError(f"无法读取文本文件: {path}") from last_error


def _read_result_table(path: Path) -> pd.DataFrame:
    """读取结果层对比表。"""

    if path.suffix.lower() == ".xlsx":
        return pd.read_excel(path)
    return _read_text_table(path)


def _infer_dt(frame: pd.DataFrame) -> float:
    """从 time 列推导 dt。"""

    if len(frame) < 2:
        raise ValueError("振动波样本点数不足，无法推导 dt")
    dt = float(frame["time"].iloc[1] - frame["time"].iloc[0])
    if not math.isfinite(dt) or dt <= 0:
        raise ValueError(f"推导得到的 dt 非法: {dt}")
    return dt


def _normalize_key_value(value: Any) -> str:
    """将结果表键值规范化为字符串。"""

    if pd.isna(value):
        return ""
    text = str(value).strip()
    if text.isdigit():
        return str(int(text))
    if text.endswith(".0"):
        try:
            numeric = float(text)
            if numeric.is_integer():
                return str(int(numeric))
        except ValueError:
            return text
    return text


def _build_direct_result_alignment(
    spec: ProjectSpec,
    parsed_items: list[WaveFilenameInfo],
) -> dict[str, Any] | None:
    if spec.direct_result_anchor is None or not spec.direct_result_anchor.exists():
        return None
    raw_frame = build_raw_result_join_frame(parsed_items, adapter=spec.result_key_adapter)
    result_frame = build_result_key_frame(_read_result_table(spec.direct_result_anchor))
    return _compute_key_overlap(raw_frame, result_frame, label=spec.direct_result_anchor.name)


def _build_split_table_alignment(
    spec: ProjectSpec,
    parsed_items: list[WaveFilenameInfo],
) -> dict[str, Any] | None:
    if spec.split_table_anchor is None or not spec.split_table_anchor.exists() or spec.split_wave_column is None:
        return None
    split_table = _read_result_table(spec.split_table_anchor)
    split_key_columns = ("工况号", "测点号", "仪器号", spec.split_wave_column)
    missing = [column for column in split_key_columns if column not in split_table.columns]
    if missing:
        return {
            "anchor": spec.split_table_anchor.name,
            "missing_columns": missing,
        }
    split_frame = split_table.loc[:, list(split_key_columns)].copy()
    split_frame.columns = ["case", "point", "instr", "wave"]
    for column in split_frame.columns:
        split_frame[column] = split_frame[column].map(_normalize_key_value)
    raw_records = [
        {
            "case": item.case,
            "point": item.point,
            "instr": item.instr,
            "wave": item.wave,
        }
        for item in parsed_items
    ]
    raw_frame = pd.DataFrame.from_records(raw_records, columns=["case", "point", "instr", "wave"])
    return _compute_key_overlap(raw_frame, split_frame, label=spec.split_table_anchor.name)


def _compute_key_overlap(
    left: pd.DataFrame,
    right: pd.DataFrame,
    *,
    label: str,
) -> dict[str, Any]:
    """计算两组键值表的交集覆盖度。"""

    if left.empty or right.empty:
        return {
            "anchor": label,
            "left_total": int(len(left)),
            "right_total": int(len(right)),
            "matched": 0,
            "coverage": 0.0,
        }
    left_keys = {tuple(row) for row in left.itertuples(index=False, name=None)}
    right_keys = {tuple(row) for row in right.itertuples(index=False, name=None)}
    matched = len(left_keys & right_keys)
    coverage = matched / len(left_keys) if left_keys else 0.0
    return {
        "anchor": label,
        "left_total": len(left_keys),
        "right_total": len(right_keys),
        "matched": matched,
        "coverage": round(float(coverage), 4),
    }


def _comparison_report_summary(report: Any) -> dict[str, Any]:
    """抽取样本集比较摘要。"""

    metadata_rows = len(getattr(report, "metadata_diff", pd.DataFrame()))
    presence_rows = len(getattr(report, "presence_diff", pd.DataFrame()))
    scalar_rows = len(getattr(report, "scalar_diff", pd.DataFrame()))
    return {
        "summary": getattr(report, "summary", ""),
        "metadata_diff_rows": metadata_rows,
        "presence_diff_rows": presence_rows,
        "scalar_diff_rows": scalar_rows,
    }


def _sample_set_plan_summary(samples: list[VibrationTestSample]) -> dict[str, Any]:
    """返回样本集组织摘要。"""

    if not samples:
        return {"sample_count": 0}
    return {
        "sample_count": len(samples),
        "metadata_type": "VibrationTestMetadata",
        "sample_type": "VibrationTestSample",
        "sample_set_type": "VibrationTestSampleSet",
        "record_field_used_for_wave": True,
        "fields": {
            "case": samples[0].metadata.case,
            "point": samples[0].metadata.point,
            "instr": samples[0].metadata.instr,
            "dir": samples[0].metadata.dir,
            "record": samples[0].metadata.record,
        },
    }


def _estimate_person_days(cost: Literal["low", "medium", "high"]) -> str:
    """返回迁移成本对应的人天区间。"""

    mapping = {
        "low": "0.5-1.5",
        "medium": "2-4",
        "high": "4-7",
    }
    return mapping[cost]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="验证 v1.2.0 对真实工程项目的迁移成本")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(".pytest_tmp") / "engineering_project_migration_validation",
        help="验证输出目录",
    )
    parser.add_argument(
        "--project",
        action="append",
        dest="project_ids",
        help="仅验证指定项目，可重复提供；默认验证全部",
    )
    parser.add_argument(
        "--subset-size",
        type=int,
        default=24,
        help="每个项目用于实际闭环验证的样本上限",
    )
    return parser.parse_args()


def main() -> int:
    """脚本命令行入口。"""

    args = _parse_args()
    matrix = build_project_migration_matrix(
        args.output_dir,
        project_ids=args.project_ids,
        subset_size=args.subset_size,
    )
    print(json.dumps(matrix, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
