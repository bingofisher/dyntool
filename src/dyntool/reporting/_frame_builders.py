"""reporting 表格与摘要构造。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Iterable

import numpy as np
import pandas as pd

from ..compute.units import get_unit_registry, convert_array

from ..domain.samples._sample_set_views import supports_scalar_data_var

if TYPE_CHECKING:
    from ..domain.samples import SampleSetBase
    from ..domain.samples.types import SampleSetComparisonReport

DEFAULT_SCALAR_FEATURES = ("pga", "rms", "crest_factor")
DEFAULT_EVAL_DATA_VARS = ("zvl", "otovl", "fdmvl", "fpvdv")


class _ReportFrames:
    """报告专用 SI 表格，保持普通显示表的单位合同。"""

    @staticmethod
    def unit(unit: str | None) -> str | None:
        """保留 dB，角度转弧度，其余物理量转相干 SI。"""
        if unit is None or unit in {"dB", "decibel", "dimensionless"}:
            return unit
        return str(get_unit_registry().Quantity(1, unit).to_base_units().units)

    @classmethod
    def scalar(cls, sample_set: Any, **options: Any) -> pd.DataFrame:
        """规范化各个单元格，摘要读取仍不访问数组。"""
        frame = sample_set.scalar_frame(**options).copy()
        units = frame.attrs.get("scalar_units", {})
        columns: dict[Any, str] = {}
        uids = frame.get("uid", pd.Series(dtype=str)).to_numpy()
        for column in frame.columns:
            values = frame[column].to_numpy(dtype=object, copy=True)
            changed = False
            for index, uid in enumerate(uids):
                unit = units.get((uid, column))
                target = cls.unit(unit)
                value = values[index]
                if target is not None:
                    columns[column] = target
                    if isinstance(value, (int, float, np.number)) and not pd.isna(value):
                        values[index] = float(convert_array(value, from_unit=unit, to_unit=target))
                        changed = True
            if changed:
                frame[column] = pd.to_numeric(pd.Series(values, index=frame.index))
        frame.attrs["column_units"] = columns
        return frame

    @classmethod
    def series(cls, sample_set: Any, data_var: str, **options: Any) -> pd.DataFrame:
        """仅复制所需模型状态，统一轴和值后一次组合序列表。"""
        samples = []
        member_units: dict[str, dict[str, str | None]] = {}
        for sample in sample_set.values():
            model = sample.get_data_var(data_var)
            clone = sample._clone_for_view()
            if model is not None:
                units = {key: cls.unit(unit) for key, unit in model.current_units().items()}
                member_units[sample.uid] = units
                clone._replace_data_var_internal(
                    clone._resolve_field(data_var), model.convert_units(units, replace=False)
                )
            samples.append(clone)
        frame = type(sample_set)(samples).series_frame(data_var, **options)
        columns: dict[Any, str | None] = {}
        for column in frame.columns:
            units = member_units.get(str(column[0]), {})
            columns[column] = units.get(
                str(column[-1]),
                units.get("value", "dimensionless") if str(column[-1]).startswith("value") else "dimensionless",
            )
        frame.attrs["column_units"] = columns
        for sample in samples:
            if (model := sample.get_data_var(data_var)) is not None:
                frame.attrs["index_unit"] = model.axis_unit
                break
        return frame

    @classmethod
    def peaks(cls, sample_set: Any, *, source: str = "accel", **options: Any) -> pd.DataFrame:
        """峰选择参数按原单位解释，仅转换输出峰值。"""
        frame = sample_set.peaks_frame(source=source, **options)
        units: dict[Any, str] = {}
        for column in frame.columns:
            if column[-1] != "peak_value":
                continue
            model = sample_set[str(column[0])].get_data_var(source)
            unit = model.value_unit
            target = cls.unit(unit)
            frame[column] = convert_array(frame[column].to_numpy(), from_unit=unit, to_unit=target)
            units[column] = target
        frame.attrs["column_units"] = units
        return frame


def build_metadata_summary(sample_set: "SampleSetBase[Any]", metadata_frame: pd.DataFrame) -> dict[str, Any]:
    """构造样本集元数据摘要。"""

    return {
        "sample_set_type": type(sample_set).__name__,
        "sample_type": sample_set.sample_type.__name__,
        "sample_count": len(sample_set),
        "uids": list(sample_set.keys()),
        "metadata_columns": [str(column) for column in metadata_frame.columns],
    }


def comparison_frames(report: "SampleSetComparisonReport") -> dict[str, pd.DataFrame]:
    """提取标准比较报表的三张对比表。"""

    return {
        "metadata_diff": report.metadata_diff,
        "presence_diff": report.presence_diff,
        "scalar_diff": report.scalar_diff,
    }


def build_compare_data_vars(eval_data_vars: Iterable[str]) -> list[str]:
    """去重并保序整理用于 compare 的 data_var 列表。"""

    seen: list[str] = []
    for name in eval_data_vars:
        normalized = str(name)
        if normalized not in seen:
            seen.append(normalized)
    return seen


def detect_available_eval_data_vars(sample_set: "SampleSetBase[Any]") -> tuple[str, ...]:
    """识别样本集中真实存在的评价 data_var。"""

    available: list[str] = []
    for data_var in DEFAULT_EVAL_DATA_VARS:
        if not sample_set.sample_schema.has_slot(data_var):
            continue
        if any(sample.get_data_var(data_var) is not None for sample in sample_set.values()):
            available.append(data_var)
    return tuple(available)


def filter_scalar_data_vars(
    sample_set: "SampleSetBase[Any]",
    data_vars: Iterable[str],
) -> tuple[str, ...]:
    """仅保留可通过 scalar_frame 导出的 data_var。"""

    scalar_vars: list[str] = []
    for data_var in data_vars:
        if is_scalar_data_var(sample_set, data_var):
            scalar_vars.append(str(data_var))
    return tuple(scalar_vars)


def is_scalar_data_var(sample_set: "SampleSetBase[Any]", data_var: str) -> bool:
    """判断 data_var 是否能走 scalar 快路径。"""

    try:
        return supports_scalar_data_var(sample_set, data_var)
    except KeyError:
        return False


__all__ = [
    "DEFAULT_SCALAR_FEATURES",
    "build_compare_data_vars",
    "build_metadata_summary",
    "comparison_frames",
    "detect_available_eval_data_vars",
    "filter_scalar_data_vars",
]
