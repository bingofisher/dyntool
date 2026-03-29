"""正式 plotting 数据结构。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Iterable, Mapping, Sequence, TypeAlias, Self

import numpy as np
import pandas as pd
from numpy.typing import ArrayLike

from ..domain.limits.base import CurveLimitBase, LimitModelBase, ScalarLimitBase
from ..domain.models.base import DataModelBase
from ..domain.models.vibration_evaluation import OTOVLEval

PlotStyleValue: TypeAlias = str | float | int | bool | None
PlotStyle: TypeAlias = Mapping[str, PlotStyleValue]
PlotMetaValue: TypeAlias = str | PlotStyle | None


class PlotCategory(StrEnum):
    """正式公开的绘图类别。"""

    SAMPLE = "sample"
    ENVELOPE = "envelope"
    LIMIT = "limit"
    STAT = "stat"


@dataclass(slots=True, frozen=True)
class _ColumnKey:
    """内部列键。"""

    category: str
    name: str

    def as_tuple(self) -> tuple[str, str]:
        return (self.category, self.name)


@dataclass(slots=True, frozen=True)
class _SeriesSpec:
    """内部标准曲线规格。"""

    axis: np.ndarray
    value: np.ndarray
    name: str
    category: PlotCategory | str
    label: str | None = None
    axis_unit: str | None = None
    value_unit: str | None = None
    source_type: str = "model"
    style: PlotStyle | None = None


class PlotDataset:
    """严格包装的 plotting 数据集。

    约束:
        - ``data.index`` 必须是单索引，表示共享 axis。
        - ``data.columns`` 必须是两层 ``MultiIndex(category, name)``。
        - ``meta`` 与 ``data.columns`` 必须严格同步。
        - 一个 ``PlotDataset`` 只允许一个共享 axis。
    """

    _META_COLUMNS = ("label", "axis_unit", "value_unit", "source_type", "style")

    def __init__(
        self,
        data: pd.DataFrame | None = None,
        meta: pd.DataFrame | None = None,
        *,
        allowed_categories: Sequence[PlotCategory | str] | None = None,
    ) -> None:
        self._allowed_categories = tuple(
            self._normalize_category_value(item)
            for item in (allowed_categories or tuple(member.value for member in PlotCategory))
        )
        if data is None:
            empty_columns = pd.MultiIndex.from_tuples([], names=["category", "name"])
            self._data = pd.DataFrame(columns=empty_columns, dtype=float)
            self._data.index = pd.Index([], dtype=float, name="axis")
        else:
            self._data = self._coerce_dataframe(data)
            self._validate_categories(tuple(self._data.columns.get_level_values(0)))
        if meta is None:
            self._meta = self._build_default_meta(self._data.columns)
        else:
            self._meta = self._coerce_meta_frame(meta)
        self._sync_meta()

    @classmethod
    def from_axis_value(
        cls,
        *,
        axis: ArrayLike,
        value: ArrayLike,
        name: str,
        category: PlotCategory | str,
        axis_unit: str | None = None,
        value_unit: str | None = None,
        label: str | None = None,
        allowed_categories: Sequence[PlotCategory | str] | None = None,
        source_type: str = "array",
        style: PlotStyle | None = None,
    ) -> Self:
        """从显式 ``axis/value`` 构建数据集。"""

        dataset = cls(allowed_categories=allowed_categories)
        dataset.add_axis_value(
            axis=axis,
            value=value,
            name=name,
            category=category,
            axis_unit=axis_unit,
            value_unit=value_unit,
            label=label,
            source_type=source_type,
            style=style,
        )
        return dataset

    @classmethod
    def from_array2d(
        cls,
        values: np.ndarray,
        *,
        category: PlotCategory | str,
        names: Sequence[str] | None = None,
        axis_unit: str | None = None,
        value_unit: str | None = None,
        labels: Sequence[str | None] | None = None,
        allowed_categories: Sequence[PlotCategory | str] | None = None,
    ) -> "PlotDataset":
        """从二维数组构建数据集。

        第一列必须为共享 axis，后续列是同一 ``category`` 下的多条曲线。
        """

        array = np.asarray(values, dtype=float)
        if array.ndim != 2 or array.shape[1] < 2:
            raise ValueError("二维绘图数组至少需要两列，第一列必须为 axis。")
        resolved_names = list(names) if names is not None else [f"series-{idx}" for idx in range(1, array.shape[1])]
        if len(resolved_names) != array.shape[1] - 1:
            raise ValueError("names 数量必须与 value 列数量一致。")
        resolved_labels = list(labels) if labels is not None else [None] * len(resolved_names)
        if len(resolved_labels) != len(resolved_names):
            raise ValueError("labels 数量必须与 names 数量一致。")
        dataset = cls(allowed_categories=allowed_categories)
        axis = array[:, 0]
        for idx, series_name in enumerate(resolved_names, start=1):
            dataset.add_axis_value(
                axis=axis,
                value=array[:, idx],
                name=series_name,
                category=category,
                axis_unit=axis_unit,
                value_unit=value_unit,
                label=resolved_labels[idx - 1],
                source_type="array2d",
            )
        return dataset

    @classmethod
    def from_model(
        cls,
        model: DataModelBase,
        *,
        name: str | None = None,
        category: PlotCategory | str | None = None,
        label: str | None = None,
        allowed_categories: Sequence[PlotCategory | str] | None = None,
    ) -> "PlotDataset":
        """从数据模型构建数据集。"""

        dataset = cls(allowed_categories=allowed_categories)
        for spec in cls._iter_model_specs(model, name=name, category=category, label=label):
            dataset.add_axis_value(
                axis=spec.axis,
                value=spec.value,
                name=spec.name,
                category=spec.category,
                axis_unit=spec.axis_unit,
                value_unit=spec.value_unit,
                label=spec.label,
                source_type=spec.source_type,
                style=spec.style,
            )
        return dataset

    @classmethod
    def from_limit(
        cls,
        limit: LimitModelBase,
        *,
        axis: ArrayLike | None = None,
        name: str | None = None,
        category: PlotCategory | str | None = None,
        label: str | None = None,
        allowed_categories: Sequence[PlotCategory | str] | None = None,
    ) -> "PlotDataset":
        """从限值对象构建数据集。"""

        dataset = cls(allowed_categories=allowed_categories)
        for spec in cls._iter_limit_specs(limit, axis=axis, name=name, category=category, label=label):
            dataset.add_axis_value(
                axis=spec.axis,
                value=spec.value,
                name=spec.name,
                category=spec.category,
                axis_unit=spec.axis_unit,
                value_unit=spec.value_unit,
                label=spec.label,
                source_type=spec.source_type,
                style=spec.style,
            )
        return dataset

    @classmethod
    def from_dataframe(
        cls,
        df: pd.DataFrame,
        *,
        category: PlotCategory | str | None = None,
        axis_unit: str | None = None,
        value_unit: str | None = None,
        allowed_categories: Sequence[PlotCategory | str] | None = None,
    ) -> "PlotDataset":
        """从 DataFrame 构建数据集。"""

        if isinstance(df.columns, pd.MultiIndex):
            if df.columns.nlevels != 2:
                raise ValueError("绘图 DataFrame 的列必须是两层 MultiIndex(category, name)。")
            dataset = cls(data=df.copy(), allowed_categories=allowed_categories)
            for key in dataset._column_keys():
                if axis_unit is not None:
                    dataset._meta.at[key.as_tuple(), "axis_unit"] = axis_unit
                if value_unit is not None:
                    dataset._meta.at[key.as_tuple(), "value_unit"] = value_unit
            return dataset
        if category is None:
            raise ValueError("单层列 DataFrame 需要显式提供 category。")
        dataset = cls(allowed_categories=allowed_categories)
        axis = df.index.to_numpy(dtype=float)
        for column in df.columns:
            dataset.add_axis_value(
                axis=axis,
                value=df[column].to_numpy(dtype=float),
                name=str(column),
                category=category,
                axis_unit=axis_unit,
                value_unit=value_unit,
                source_type="dataframe",
            )
        return dataset

    def add_axis_value(
        self,
        *,
        axis: ArrayLike,
        value: ArrayLike,
        name: str,
        category: PlotCategory | str,
        axis_unit: str | None = None,
        value_unit: str | None = None,
        label: str | None = None,
        source_type: str = "array",
        style: PlotStyle | None = None,
    ) -> None:
        """追加一条显式 ``axis/value`` 曲线。"""

        key = self._build_key(category=category, name=name)
        axis_array = self._coerce_axis(axis)
        value_array = self._coerce_value(value)
        if axis_array.shape[0] != value_array.shape[0]:
            raise ValueError("axis 与 value 长度必须一致。")
        self._ensure_axis(axis_array)
        if key.as_tuple() in self._data.columns:
            raise ValueError(f"重复的绘图数据键: {key.as_tuple()}")

        new_column = pd.DataFrame(
            value_array,
            index=self._data.index,
            columns=pd.MultiIndex.from_tuples([key.as_tuple()], names=["category", "name"]),
        )
        self._data = pd.concat([self._data, new_column], axis=1)
        new_meta = pd.DataFrame(
            [
                {
                    "label": label or key.name,
                    "axis_unit": axis_unit,
                    "value_unit": value_unit,
                    "source_type": str(source_type),
                    "style": dict(style or {}),
                }
            ],
            index=pd.MultiIndex.from_tuples([key.as_tuple()], names=["category", "name"]),
            columns=self._META_COLUMNS,
        )
        self._meta = pd.concat([self._meta, new_meta], axis=0)
        self._sync_meta()

    def add_model(
        self,
        model: DataModelBase,
        *,
        name: str | None = None,
        category: PlotCategory | str | None = None,
        label: str | None = None,
    ) -> None:
        """追加数据模型。"""

        other = self.from_model(
            model,
            name=name,
            category=category,
            label=label,
            allowed_categories=self._allowed_categories,
        )
        self._extend(other)

    def add_limit(
        self,
        limit: LimitModelBase,
        *,
        axis: ArrayLike | None = None,
        name: str | None = None,
        category: PlotCategory | str | None = None,
        label: str | None = None,
    ) -> None:
        """追加限值对象。"""

        other = self.from_limit(
            limit,
            axis=axis,
            name=name,
            category=category,
            label=label,
            allowed_categories=self._allowed_categories,
        )
        self._extend(other)

    def set_label(self, category: PlotCategory | str, name: str, label: str) -> None:
        """更新指定曲线的显示标签。"""

        key = self._build_key(category=category, name=name)
        self._require_existing_key(key)
        self._meta.at[key.as_tuple(), "label"] = str(label)

    def set_style(self, category: PlotCategory | str, name: str, style: PlotStyle) -> None:
        """更新指定曲线的样式。"""

        key = self._build_key(category=category, name=name)
        self._require_existing_key(key)
        self._meta.at[key.as_tuple(), "style"] = dict(style)

    def set_meta(
        self,
        category: PlotCategory | str,
        name: str,
        *,
        label: str | None = None,
        axis_unit: str | None = None,
        value_unit: str | None = None,
        source_type: str | None = None,
        style: PlotStyle | None = None,
    ) -> None:
        """更新指定曲线的元信息。"""

        key = self._build_key(category=category, name=name)
        self._require_existing_key(key)
        if label is not None:
            self._meta.at[key.as_tuple(), "label"] = str(label)
        if axis_unit is not None:
            self._meta.at[key.as_tuple(), "axis_unit"] = axis_unit
        if value_unit is not None:
            self._meta.at[key.as_tuple(), "value_unit"] = value_unit
        if source_type is not None:
            self._meta.at[key.as_tuple(), "source_type"] = source_type
        if style is not None:
            self._meta.at[key.as_tuple(), "style"] = dict(style)

    def to_dataframe(self) -> pd.DataFrame:
        """返回标准宽表视图。"""

        return self._data.copy()

    def meta_frame(self) -> pd.DataFrame:
        """返回列级元数据表。"""

        return self._meta.copy()

    def _axis_values(self) -> np.ndarray:
        """返回共享轴值。

        Notes:
            该方法属于 plotting 内部桥接工具，不进入正式公开 API。
        """

        return self._data.index.to_numpy(dtype=float)

    def _column_values(self, key: tuple[str, str] | _ColumnKey) -> np.ndarray:
        """返回指定列的数据值。"""

        resolved = key.as_tuple() if isinstance(key, _ColumnKey) else key
        return self._data[resolved].to_numpy(dtype=float)

    def _column_meta(self, key: tuple[str, str] | _ColumnKey) -> dict[str, PlotMetaValue]:
        """返回指定列的元信息快照。"""

        resolved = key.as_tuple() if isinstance(key, _ColumnKey) else key
        row = self._meta.loc[resolved]
        return {name: row[name] for name in self._META_COLUMNS}

    def _extend(self, other: "PlotDataset") -> None:
        """内部合并数据集。"""

        if not other._data.empty:
            self._ensure_axis(other._data.index.to_numpy(dtype=float))
        duplicate_keys = set(self._data.columns.tolist()) & set(other._data.columns.tolist())
        if duplicate_keys:
            duplicate_key = sorted(duplicate_keys)[0]
            raise ValueError(f"重复的绘图数据键: {duplicate_key}")
        if not other._data.empty:
            self._data = pd.concat([self._data, other._data], axis=1)
        if not other._meta.empty:
            self._meta = pd.concat([self._meta, other._meta.loc[:, self._META_COLUMNS]], axis=0)
        self._sync_meta()

    def _subset_columns(
        self,
        *,
        categories: Sequence[PlotCategory | str] | None = None,
        names: Sequence[str] | None = None,
    ) -> list[_ColumnKey]:
        category_filter = (
            {self._normalize_category_value(item) for item in categories} if categories is not None else None
        )
        name_filter = {str(item) for item in names} if names is not None else None
        keys: list[_ColumnKey] = []
        for key in self._column_keys():
            if category_filter is not None and key.category not in category_filter:
                continue
            if name_filter is not None and key.name not in name_filter:
                continue
            keys.append(key)
        return keys

    def _resolve_label(self, key: _ColumnKey) -> str:
        label = self._meta.loc[key.as_tuple(), "label"]
        return str(label) if label else key.name

    def _column_keys(self) -> list[_ColumnKey]:
        return [_ColumnKey(category=str(category), name=str(name)) for category, name in self._data.columns.tolist()]

    def _require_existing_key(self, key: _ColumnKey) -> None:
        if key.as_tuple() not in self._data.columns:
            raise KeyError(f"PlotDataset 不存在绘图数据键: {key.as_tuple()}")

    @staticmethod
    def _coerce_axis(axis: ArrayLike) -> np.ndarray:
        values = np.asarray(axis, dtype=float).flatten()
        if values.size == 0:
            raise ValueError("axis 不能为空。")
        return values

    @staticmethod
    def _coerce_value(value: ArrayLike) -> np.ndarray:
        values = np.asarray(value, dtype=float)
        if values.ndim > 1:
            values = values.squeeze()
        values = values.flatten()
        if values.size == 0:
            raise ValueError("value 不能为空。")
        return values

    def _ensure_axis(self, axis: np.ndarray) -> None:
        if self._data.empty:
            self._data.index = pd.Index(axis, dtype=float, name="axis")
            return
        current = self._data.index.to_numpy(dtype=float)
        if current.shape != axis.shape or not np.allclose(current, axis):
            raise ValueError("PlotDataset 只支持共享 axis；新增数据的 axis 必须与现有 index 完全一致。")

    def _build_key(self, *, category: PlotCategory | str, name: str) -> _ColumnKey:
        category_value = self._normalize_category_value(category)
        self._validate_categories((category_value,))
        normalized_name = str(name).strip()
        if not normalized_name:
            raise ValueError("name 不能为空。")
        return _ColumnKey(category=category_value, name=normalized_name)

    @staticmethod
    def _normalize_category_value(value: PlotCategory | str) -> str:
        normalized = value.value if isinstance(value, PlotCategory) else str(value).strip()
        if not normalized:
            raise ValueError("category 不能为空。")
        return normalized

    def _validate_categories(self, values: Iterable[str]) -> None:
        allowed = set(self._allowed_categories)
        invalid = [value for value in values if value not in allowed]
        if invalid:
            raise ValueError(f"不支持的 plotting category: {invalid}")

    @classmethod
    def _coerce_dataframe(cls, df: pd.DataFrame) -> pd.DataFrame:
        if df.index.nlevels != 1:
            raise ValueError("PlotDataset 的 index 必须是单索引。")
        if not isinstance(df.columns, pd.MultiIndex) or df.columns.nlevels != 2:
            raise ValueError("PlotDataset 的 columns 必须是两层 MultiIndex(category, name)。")
        normalized = df.copy()
        normalized.columns = pd.MultiIndex.from_tuples(
            [(str(category), str(name)) for category, name in normalized.columns.tolist()],
            names=["category", "name"],
        )
        normalized.index = pd.Index(
            normalized.index.to_numpy(dtype=float),
            dtype=float,
            name=str(df.index.name or "axis"),
        )
        return normalized.astype(float)

    @classmethod
    def _coerce_meta_frame(cls, meta: pd.DataFrame) -> pd.DataFrame:
        normalized = meta.copy()
        if not isinstance(normalized.index, pd.MultiIndex) or normalized.index.nlevels != 2:
            raise ValueError("PlotDataset meta 的索引必须是两层 MultiIndex(category, name)。")
        normalized.index = pd.MultiIndex.from_tuples(
            [(str(category), str(name)) for category, name in normalized.index.tolist()],
            names=["category", "name"],
        )
        for column in cls._META_COLUMNS:
            if column not in normalized.columns:
                normalized[column] = None
        return normalized[list(cls._META_COLUMNS)]

    @classmethod
    def _build_default_meta(cls, columns: pd.MultiIndex) -> pd.DataFrame:
        index = pd.MultiIndex.from_tuples(
            [(str(category), str(name)) for category, name in columns.tolist()],
            names=["category", "name"],
        )
        if len(index) == 0:
            return pd.DataFrame(columns=cls._META_COLUMNS, index=index)
        frame = pd.DataFrame(index=index, columns=cls._META_COLUMNS)
        for category, name in index.tolist():
            frame.loc[(category, name), :] = {
                "label": name,
                "axis_unit": None,
                "value_unit": None,
                "source_type": "unknown",
                "style": {},
            }
        return frame

    def _sync_meta(self) -> None:
        columns = pd.MultiIndex.from_tuples(
            [(str(category), str(name)) for category, name in self._data.columns.tolist()],
            names=["category", "name"],
        )
        self._data.columns = columns
        if len(columns) == 0:
            self._meta = self._build_default_meta(columns)
            return
        if not self._meta.index.equals(columns):
            merged = self._build_default_meta(columns)
            overlap = columns.intersection(self._meta.index)
            if len(overlap) > 0:
                merged.loc[overlap, self._META_COLUMNS] = self._meta.loc[overlap, self._META_COLUMNS]
            self._meta = merged
        for category, name in columns.tolist():
            if not self._meta.loc[(category, name), "label"]:
                self._meta.loc[(category, name), "label"] = name
            if not isinstance(self._meta.loc[(category, name), "style"], dict):
                self._meta.loc[(category, name), "style"] = {}

    @classmethod
    def _iter_model_specs(
        cls,
        model: DataModelBase,
        *,
        name: str | None = None,
        category: PlotCategory | str | None = None,
        label: str | None = None,
    ) -> tuple[_SeriesSpec, ...]:
        if isinstance(model, OTOVLEval):
            return cls._otovl_eval_specs(model)
        return (cls._generic_model_spec(model, name=name, category=category, label=label),)

    @classmethod
    def _iter_limit_specs(
        cls,
        limit: LimitModelBase,
        *,
        axis: ArrayLike | None = None,
        name: str | None = None,
        category: PlotCategory | str | None = None,
        label: str | None = None,
    ) -> tuple[_SeriesSpec, ...]:
        resolved_name = name or cls._default_limit_name(limit)
        resolved_category = category or PlotCategory.LIMIT
        resolved_label = label or cls._default_limit_label(limit, resolved_name)

        if isinstance(limit, CurveLimitBase):
            assert limit.axis_field is not None
            assert limit.value_field is not None
            return (
                _SeriesSpec(
                    axis=np.asarray(limit.get_field(limit.axis_field), dtype=float),
                    value=np.asarray(limit.get_field(limit.value_field), dtype=float),
                    name=resolved_name,
                    category=resolved_category,
                    label=resolved_label,
                    axis_unit=limit.base_units()[limit.axis_field],
                    value_unit=limit.base_units()[limit.value_field],
                    source_type="limit",
                    style={"linestyle": "--"},
                ),
            )

        if not isinstance(limit, ScalarLimitBase):
            raise TypeError(f"{type(limit).__name__} 不是支持的限值对象。")
        if axis is None:
            raise ValueError("标量限值需要显式提供 axis 才能广播成绘图曲线。")
        assert limit.value_field is not None
        axis_array = cls._coerce_axis(axis)
        scalar = float(np.asarray(limit.get_field(limit.value_field)).flat[0])
        return (
            _SeriesSpec(
                axis=axis_array,
                value=np.full(axis_array.shape[0], scalar, dtype=float),
                name=resolved_name,
                category=resolved_category,
                label=resolved_label,
                value_unit=limit.base_units()[limit.value_field],
                source_type="limit",
                style={"linestyle": "--"},
            ),
        )

    @classmethod
    def _generic_model_spec(
        cls,
        model: DataModelBase,
        *,
        name: str | None = None,
        category: PlotCategory | str | None = None,
        label: str | None = None,
    ) -> _SeriesSpec:
        if not hasattr(model, "get_axis") or not hasattr(model, "get_value"):
            raise TypeError(f"{type(model).__name__} 不能直接转换为 PlotDataset。")
        resolved_name = name or cls._default_model_name(model)
        resolved_category = category or PlotCategory.SAMPLE
        axis = np.asarray(model.get_axis(), dtype=float)
        value = np.asarray(model.get_value(), dtype=float)
        if value.ndim > 1:
            value = np.asarray(value).squeeze()
        return _SeriesSpec(
            axis=axis,
            value=value,
            name=resolved_name,
            category=resolved_category,
            label=label or resolved_name,
            axis_unit=getattr(model, "axis_unit", None),
            value_unit=getattr(model, "value_unit", None),
            source_type="model",
        )

    @classmethod
    def _otovl_eval_specs(cls, model: OTOVLEval) -> tuple[_SeriesSpec, ...]:
        freq = np.asarray(model.freq, dtype=float)
        comps = np.asarray(model.comps, dtype=float)
        env = np.asarray(model.env, dtype=float)
        current_units = model.current_units()
        specs: list[_SeriesSpec] = []
        if comps.ndim == 1:
            comps = comps[:, None]
        for idx in range(comps.shape[1]):
            specs.append(
                _SeriesSpec(
                    axis=freq,
                    value=comps[:, idx],
                    name=f"comp-{idx + 1}",
                    category=PlotCategory.SAMPLE,
                    label="_nolegend_",
                    axis_unit=current_units["freq"],
                    value_unit=current_units["comps"],
                    source_type="otovl-comp",
                    style={
                        "color": "lightgray",
                        "linewidth": 0.8,
                        "marker": "o",
                        "markersize": 2,
                        "alpha": 0.9,
                    },
                )
            )
        specs.append(
            _SeriesSpec(
                axis=freq,
                value=env,
                name="env",
                category=PlotCategory.ENVELOPE,
                label="包络值",
                axis_unit=current_units["freq"],
                value_unit=current_units["env"],
                source_type="otovl-env",
                style={
                    "color": "blue",
                    "linewidth": 2.0,
                    "marker": "o",
                    "markersize": 6,
                },
            )
        )
        return tuple(specs)

    @staticmethod
    def _default_model_name(model: DataModelBase) -> str:
        raw = getattr(model, "category", None)
        if raw is not None:
            value = getattr(raw, "value", raw)
            normalized = str(value).strip()
            if normalized:
                return normalized
        return type(model).__name__

    @staticmethod
    def _default_limit_name(limit: LimitModelBase) -> str:
        scene = getattr(limit, "scene", None)
        if scene:
            return f"{type(limit).__name__}:{scene}"
        return type(limit).__name__

    @staticmethod
    def _default_limit_label(limit: LimitModelBase, fallback_name: str) -> str:
        scene = getattr(limit, "scene", None)
        if scene:
            return str(scene)
        return fallback_name


__all__ = ["PlotCategory", "PlotDataset"]
