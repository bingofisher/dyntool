"""基础设施层 CSV 持久化后端。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from ...domain.constants import DataCategory, parse_label_unit

_CSV_READ_OPTION_KEYS = {
    "sep",
    "delimiter",
    "header",
    "names",
    "index_col",
    "encoding",
    "comment",
    "decimal",
    "skiprows",
}
_CSV_WRITE_OPTION_KEYS = {
    "sep",
    "delimiter",
    "encoding",
    "index",
    "header",
    "lineterminator",
}


def _extract_csv_options(
    backend_options: dict[str, Any],
    *,
    allowed_keys: set[str],
) -> dict[str, Any]:
    """从后端参数中提取 CSV 相关参数。"""

    csv_parser_options = dict(backend_options.pop("csv_read_options", {}) or {})
    for key in list(backend_options):
        if key in allowed_keys:
            csv_parser_options.setdefault(key, backend_options.pop(key))
    return csv_parser_options


def _inspect_dataframe_units(df: pd.DataFrame) -> dict[str, str]:
    """从 DataFrame 标签中收集单位信息。"""

    units: dict[str, str] = {}
    index_name, index_unit = parse_label_unit(df.index.name or "")
    if index_unit is not None and index_name:
        units[index_name] = index_unit
    for label in df.columns:
        name, unit = parse_label_unit(label)
        if unit is not None:
            units[name] = unit
    return units


class CSVBackend:
    """通过带单位表头的 CSV 文件读写模型。"""

    def save(self, path: Path, model: Any, **backend_options: Any) -> None:
        """保存模型到 CSV。"""

        path = Path(path)
        if not hasattr(model, "to_pandas"):
            raise TypeError(f"{type(model).__name__} must implement to_pandas().")
        df = model.to_pandas()
        path.parent.mkdir(parents=True, exist_ok=True)
        csv_write_options = _extract_csv_options(
            backend_options,
            allowed_keys=_CSV_WRITE_OPTION_KEYS,
        )
        delimiter = csv_write_options.pop("delimiter", None)
        if delimiter is not None:
            csv_write_options.setdefault("sep", delimiter)
        csv_write_options.setdefault("encoding", "utf-8")
        csv_write_options.setdefault("index", True)
        df.to_csv(path, **csv_write_options)

    def load(
        self,
        path: Path,
        category: DataCategory | None = None,
        **backend_options: Any,
    ) -> Any:
        """从 CSV 加载模型。"""

        path = Path(path)
        if category is None:
            raise ValueError("从 CSV 加载模型时必须提供 category。")
        units = backend_options.pop("units", None)
        csv_read_options = _extract_csv_options(
            backend_options,
            allowed_keys=_CSV_READ_OPTION_KEYS,
        )
        delimiter = csv_read_options.pop("delimiter", None)
        if delimiter is not None:
            csv_read_options.setdefault("sep", delimiter)
        csv_read_options.setdefault("encoding", "utf-8")
        csv_read_options.setdefault("index_col", 0)
        df = pd.read_csv(path, **csv_read_options)

        from ...domain.models import DataModelBase

        cls = DataModelBase.from_category(category)
        from_pandas = getattr(cls, "from_pandas", None)
        if from_pandas is None:
            raise TypeError(f"{cls.__name__} must implement from_pandas().")
        return from_pandas(df, units=units)

    def inspect_units(
        self,
        path: Path,
        category: DataCategory | None = None,
        **backend_options: Any,
    ) -> dict[str, str]:
        """在不加载模型对象的前提下读取 CSV 中的单位标签。"""

        del category
        path = Path(path)
        csv_read_options = _extract_csv_options(
            backend_options,
            allowed_keys=_CSV_READ_OPTION_KEYS,
        )
        delimiter = csv_read_options.pop("delimiter", None)
        if delimiter is not None:
            csv_read_options.setdefault("sep", delimiter)
        csv_read_options.setdefault("encoding", "utf-8")
        csv_read_options.setdefault("index_col", 0)
        df = pd.read_csv(path, **csv_read_options)
        return _inspect_dataframe_units(df)


__all__ = ["CSVBackend"]
