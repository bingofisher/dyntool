"""样本集存储请求摘要格式化。"""

from __future__ import annotations

from typing import Any

from .types import StorageScheme

_SUMMARY_DATA_OPTION_KEYS = (
    "attr_data_format",
    "decimal_round",
    "float_dtype",
    "h5_compression",
    "h5_compression_level",
)


def summarize_sample_set_categories(categories: list[str] | None) -> str:
    """汇总样本集分类参数，供日志记录使用。"""

    if not categories:
        return "all"
    return ",".join(str(item) for item in categories)


def summarize_sample_set_data_options(data_options: dict[str, Any] | None) -> str:
    """汇总样本集数据选项，供日志记录使用。"""

    if not data_options:
        return "none"
    keys = ",".join(sorted(str(key) for key in data_options))
    summary_parts = [f"keys={keys}"]
    for key in _SUMMARY_DATA_OPTION_KEYS:
        if key in data_options:
            summary_parts.append(f"{key}={data_options[key]}")
    return "; ".join(summary_parts)


def summarize_sample_set_scheme(scheme: StorageScheme | None) -> str | None:
    """格式化样本集存储方案名称。"""

    if scheme is None:
        return None
    return scheme.name


__all__ = [
    "summarize_sample_set_categories",
    "summarize_sample_set_data_options",
    "summarize_sample_set_scheme",
]
