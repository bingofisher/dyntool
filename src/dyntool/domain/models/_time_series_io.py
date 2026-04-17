"""时程序列 I/O 相关的内部辅助函数。"""

from __future__ import annotations

from typing import Any, Mapping

import pandas as pd

from ..constants import (
    format_label_with_unit,
    parse_label_unit,
    resolve_file_units,
)


def time_series_to_pandas(series: Any) -> pd.DataFrame:
    """转换为带当前单位表头的 DataFrame。"""

    axis_name = format_label_with_unit("time", series.axis_unit)
    value_name = format_label_with_unit("value", series.value_unit)
    t = series.get_axis()
    v = series.get_value()
    index = pd.Index(t, name=axis_name)
    if v.ndim == 1:
        return pd.DataFrame({value_name: v}, index=index)
    cols = [format_label_with_unit(f"value_{idx}", series.value_unit) for idx in range(v.shape[1])]
    return pd.DataFrame(v, index=index, columns=cols)


def time_series_from_pandas(
    cls: type[Any],
    df: pd.DataFrame,
    *,
    axis_unit: str | None = None,
    data_unit: str | None = None,
    units: Mapping[str, str | None] | None = None,
    unit_system: Any | None = None,
) -> Any:
    """根据 DataFrame 构造时程序列。"""

    _, parsed_axis_unit = parse_label_unit(df.index.name or "time")
    parsed_units: dict[str, str | None] = {"time": parsed_axis_unit}
    inferred_value_unit = None
    if len(df.columns) == 1:
        _, inferred_value_unit = parse_label_unit(df.columns[0])
    parsed_units["value"] = inferred_value_unit
    current = resolve_file_units(
        {"time", "value"},
        parsed_units=parsed_units,
        units=cls._merge_input_units(
            axis_unit=axis_unit,
            data_unit=data_unit,
            units=units,
        ),
        allow_partial=True,
    )
    default_current = cls._resolve_current_units(
        units=current if current else units,
        unit_system=unit_system,
    )
    t = df.index.to_numpy()
    v = df.iloc[:, 0].to_numpy() if len(df.columns) == 1 else df.to_numpy()
    return cls.from_data(v, time=t, units=default_current, unit_system=unit_system)


def time_series_to_dict(series: Any) -> dict[str, Any]:
    """序列化当前单位数组与单位元数据。"""

    return {
        "time": series.get_axis(),
        "value": series.get_value(),
        "_units": series.current_units(),
    }


def time_series_from_dict(
    cls: type[Any],
    data: dict[str, Any],
    *,
    axis_unit: str | None = None,
    data_unit: str | None = None,
    units: Mapping[str, str | None] | None = None,
    unit_system: Any | None = None,
) -> Any:
    """根据字典载荷反序列化时程序列。"""

    current = resolve_file_units(
        {"time", "value"},
        parsed_units=data.get("_units", {}),
        units=cls._merge_input_units(
            axis_unit=axis_unit,
            data_unit=data_unit,
            units=units,
        ),
        allow_partial=True,
    )
    default_current = cls._resolve_current_units(
        units=current if current else units,
        unit_system=unit_system,
    )
    return cls.from_data(
        data["value"],
        time=data["time"],
        units=default_current,
        unit_system=unit_system,
    )


__all__ = [
    "time_series_from_dict",
    "time_series_from_pandas",
    "time_series_to_dict",
    "time_series_to_pandas",
]
