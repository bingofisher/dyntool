"""reporting 表格与摘要构造。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Iterable

import pandas as pd

from ..domain.samples._sample_set_views import supports_scalar_data_var

if TYPE_CHECKING:
    from ..domain.samples import SampleSetBase
    from ..domain.samples.types import SampleSetComparisonReport

DEFAULT_SCALAR_FEATURES = ("pga", "rms", "crest_factor")
DEFAULT_EVAL_DATA_VARS = ("zvl", "otovl", "fdmvl", "fpvdv")


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
