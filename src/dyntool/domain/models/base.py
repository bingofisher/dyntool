"""数据模型基础类与统一 I/O 入口。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, ClassVar, Mapping, Self, cast

import numpy as np

from ..constants import (
    DataCategory,
    convert_array,
    ensure_ndarray,
    normalize_unit,
    normalize_unit_map,
)
from ..runtime import resolve_model_runtime
from .conversion import MagnitudeConversion

PathLike = str | Path


class DataModelBase:
    """所有带单位数据容器的基础类。

    Attributes:
        _registry: 分类字符串到模型类型的注册表，用于运行时分发和反序列化。
        category: 当前模型的正式数据分类，会影响存储、加载和 structured payload 分派。
        axis_field: 主轴字段名；设置后 `axis_unit`、`inspect_units()` 和 CSV/H5 读写会优先围绕该字段解释轴单位。
        value_field: 主值字段名；设置后 `value_unit`、`inspect_units()` 和 CSV/H5 读写会优先围绕该字段解释主数据单位。
    """

    _registry: ClassVar[dict[str, type["DataModelBase"]]] = {}
    category: ClassVar[str | DataCategory] = DataCategory.UNDEFINED
    axis_field: ClassVar[str | None] = None
    value_field: ClassVar[str | None] = None

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if not hasattr(cls, "category"):
            raise NotImplementedError(f"子类 {cls.__name__} 必须定义 category。")
        category_value = cls._normalize_category(cls.category)
        if category_value == DataCategory.UNDEFINED.value:
            raise NotImplementedError(f"子类 {cls.__name__} 不能使用 UNDEFINED 分类。")
        if category_value in DataModelBase._registry:
            raise ValueError(f"分类 {category_value} 已由 {DataModelBase._registry[category_value].__name__} 注册。")
        DataModelBase._registry[category_value] = cls

    @classmethod
    def from_category(cls, category: str | DataCategory) -> type[Self]:
        """根据分类查找已注册的容器类型。"""

        category_value = cls._normalize_category(category)
        if category_value not in cls._registry:
            raise ValueError(f"未注册的数据分类: {category_value}")
        return cast(type[Self], cls._registry[category_value])

    @classmethod
    def list_categories(cls) -> list[str]:
        """返回所有已注册分类。"""

        return list(cls._registry.keys())

    @classmethod
    def list_supported_categories(cls) -> list[str]:
        """返回 I/O 分发可用的分类值。"""

        return list(cls._registry.keys())

    @staticmethod
    def _normalize_category(category: str | DataCategory) -> str:
        if isinstance(category, DataCategory):
            return category.value
        normalized = str(category).strip()
        if not normalized:
            raise ValueError("category 不能为空")
        return normalized

    @staticmethod
    def get_magnitude(data: Any) -> np.ndarray:
        """兼容旧逻辑的纯数值读取辅助函数。"""

        return ensure_ndarray(data, dtype=None)

    @property
    def units(self) -> dict[str, str]:
        """返回实例当前单位。"""

        return self.current_units()

    @property
    def axis_unit(self) -> str | None:
        """返回主轴字段的当前单位。"""

        if self.axis_field is None:
            return None
        return self.get_field_unit(self.axis_field)

    @property
    def value_unit(self) -> str | None:
        """返回主值字段的当前单位。"""

        if self.value_field is None:
            return None
        return self.get_field_unit(self.value_field)

    def current_units(self) -> dict[str, str]:
        """返回实例当前单位。"""

        raise NotImplementedError(f"{self.__class__.__name__} 未实现 current_units()。")

    def field_units(self) -> dict[str, str]:
        """返回字段级当前单位。"""

        return self.current_units()

    def base_units(self) -> dict[str, str]:
        """返回模型固定的内部基础单位。"""

        raise NotImplementedError(f"{self.__class__.__name__} 未实现 base_units()。")

    def get_field_unit(self, name: str) -> str | None:
        """返回指定字段的当前单位。"""

        return normalize_unit(self.current_units().get(name))

    def get_base_unit(self, name: str) -> str | None:
        """返回指定字段的基准单位。"""

        return normalize_unit(self.base_units().get(name))

    def get_field(self, name: str, unit: str | None = None) -> np.ndarray:
        """返回字段数组，可按需要临时换算单位。"""

        raise NotImplementedError(f"{self.__class__.__name__} 未实现 get_field()。")

    def get_axis(self, unit: str | None = None) -> np.ndarray:
        """返回主轴字段数组。"""

        if self.axis_field is None:
            raise AttributeError(f"{self.__class__.__name__} 没有主轴字段。")
        return self.get_field(self.axis_field, unit=unit)

    def get_value(self, unit: str | None = None) -> np.ndarray:
        """返回主值字段数组。"""

        if self.value_field is None:
            raise AttributeError(f"{self.__class__.__name__} 没有主值字段。")
        return self.get_field(self.value_field, unit=unit)

    def get_axis_array(self) -> np.ndarray:
        """兼容旧逻辑的主轴读取别名。"""

        return self.get_axis()

    def get_value_array(self) -> np.ndarray:
        """兼容旧逻辑的主值读取别名。"""

        return self.get_value()

    def convert_units(
        self,
        units: Mapping[str, str | None],
        *,
        replace: bool = True,
    ) -> Self:
        """返回一个仅更新当前单位的新对象。"""

        raise NotImplementedError(f"{self.__class__.__name__} 未实现 convert_units(units, replace=...)。")

    def to_xarray(self) -> Any:
        """导出为 xarray 对象。"""

        xr_obj = getattr(self, "xr", None)
        if xr_obj is not None:
            return xr_obj
        try:
            import xarray as xr  # type: ignore[import-not-found]
        except ImportError as exc:  # pragma: no cover
            raise ImportError("导出 xarray 需要安装 xarray") from exc

        payload = self.to_dict()
        units = payload.get("_units", {})
        data_vars: dict[str, Any] = {}
        for key, value in payload.items():
            if key == "_units" or value is None:
                continue
            if isinstance(value, Mapping):
                continue
            data_vars[key] = np.asarray(value)
        if not data_vars:
            raise TypeError(f"{self.__class__.__name__} 无法自动导出为 xarray")
        ds = xr.Dataset({name: (("dim_0",), arr.flatten()) for name, arr in data_vars.items()})
        ds.attrs["_units"] = dict(units) if isinstance(units, Mapping) else {}
        ds.attrs["_category"] = self._normalize_category(self.category)
        ds.attrs["_model_type"] = self.__class__.__name__
        return ds

    @classmethod
    def from_xarray(
        cls,
        xr_obj: Any,
        *,
        units: Mapping[str, str | None] | None = None,
    ) -> Self:
        """从 xarray 对象恢复模型。"""

        try:
            import xarray as xr  # type: ignore[import-not-found]
        except ImportError as exc:  # pragma: no cover
            raise ImportError("导入 xarray 需要安装 xarray") from exc

        if isinstance(xr_obj, xr.DataArray):
            dim_name = xr_obj.dims[0] if xr_obj.dims else "dim_0"
            axis = (
                np.asarray(xr_obj.coords[dim_name].to_numpy())
                if dim_name in xr_obj.coords
                else np.arange(np.asarray(xr_obj.to_numpy()).shape[0], dtype=float)
            )
            values = np.asarray(xr_obj.to_numpy())
            merged_units = units
            attrs_units = xr_obj.attrs.get("_units")
            if merged_units is None and isinstance(attrs_units, Mapping):
                merged_units = attrs_units
            if merged_units is None:
                inferred_units: dict[str, str] = {}
                axis_key = cls.axis_field or dim_name
                if dim_name in xr_obj.coords:
                    axis_unit = xr_obj.coords[dim_name].attrs.get("units")
                    if isinstance(axis_unit, str) and axis_unit:
                        inferred_units[axis_key] = axis_unit
                value_key = cls.value_field
                value_unit = xr_obj.attrs.get("units")
                if value_key is not None and isinstance(value_unit, str) and value_unit:
                    inferred_units[value_key] = value_unit
                if inferred_units:
                    merged_units = inferred_units
            return cls.from_arrays(axis, values, units=merged_units)

        if isinstance(xr_obj, xr.Dataset):
            payload: dict[str, Any] = {}
            for name in xr_obj.data_vars:
                payload[name] = np.asarray(xr_obj[name].to_numpy())
            if xr_obj.coords:
                first_coord = next(iter(xr_obj.coords))
                payload[first_coord] = np.asarray(xr_obj.coords[first_coord].to_numpy())
            merged_units = units
            attrs_units = xr_obj.attrs.get("_units")
            if merged_units is None and isinstance(attrs_units, Mapping):
                merged_units = attrs_units
            if merged_units is not None:
                payload["_units"] = dict(merged_units)
            try:
                return cls.from_dict(payload, units=merged_units)
            except TypeError:
                return cls.from_dict(payload)

        raise TypeError(f"不支持的 xarray 对象类型: {type(xr_obj).__name__}")

    def to_dict(self) -> dict[str, Any]:
        """导出为字典。"""

        raise NotImplementedError(f"{self.__class__.__name__} 未实现 to_dict()。")

    @classmethod
    def from_dict(
        cls,
        data: Mapping[str, Any],
        *,
        units: Mapping[str, str | None] | None = None,
    ) -> Self:
        """从字典恢复模型。"""

        raise NotImplementedError(f"{cls.__name__} 未实现 from_dict()。")

    def to_structured_payload(self) -> Any:
        """转换为 `StructuredPayload`。"""

        from ..serialization import StructuredPayload

        raw_dict = self.to_dict()
        units = raw_dict.get("_units", {})
        coords: dict[str, Any] = {}
        data_vars: dict[str, Any] = {}
        try:
            xr_obj = self.to_xarray()
        except Exception:
            xr_obj = None

        if xr_obj is not None:
            try:
                import xarray as xr  # type: ignore[import-not-found]
            except ImportError:  # pragma: no cover
                xr = None  # type: ignore[assignment]
            if xr is not None and isinstance(xr_obj, xr.DataArray):
                for name in xr_obj.coords:
                    coords[name] = np.asarray(xr_obj.coords[name].to_numpy())
                data_name = xr_obj.name or self.value_field or "value"
                data_vars[data_name] = np.asarray(xr_obj.to_numpy())
            elif xr is not None and isinstance(xr_obj, xr.Dataset):
                for name in xr_obj.coords:
                    coords[name] = np.asarray(xr_obj.coords[name].to_numpy())
                for name in xr_obj.data_vars:
                    data_vars[name] = np.asarray(xr_obj[name].to_numpy())

        if not data_vars:
            for key, value in raw_dict.items():
                if key == "_units" or value is None or isinstance(value, Mapping):
                    continue
                data_vars[key] = np.asarray(value)

        return StructuredPayload(
            entity_type=self.__class__.__name__,
            domain="default",
            category=self._normalize_category(self.category),
            coords=coords,
            data_vars=data_vars,
            units=dict(units) if isinstance(units, Mapping) else {},
            attrs={
                "model_type": self.__class__.__name__,
                "category": self._normalize_category(self.category),
            },
            meta={"raw_dict": raw_dict},
        )

    @classmethod
    def from_structured_payload(cls, payload: Any) -> Self:
        """从 `StructuredPayload` 恢复数据模型。"""

        from ..serialization import StructuredPayload, normalize_payload

        normalized: StructuredPayload = (
            normalize_payload(payload) if not isinstance(payload, StructuredPayload) else payload
        )

        raw = normalized.meta.get("raw_dict")
        if isinstance(raw, Mapping):
            try:
                return cls.from_dict(dict(raw), units=normalized.units or None)
            except TypeError:
                return cls.from_dict(dict(raw))

        merged: dict[str, Any] = dict(normalized.coords)
        merged.update(normalized.data_vars)
        if normalized.units:
            merged["_units"] = dict(normalized.units)
        try:
            return cls.from_dict(merged, units=normalized.units or None)
        except TypeError:
            return cls.from_dict(merged)

    def to_file(self, path: PathLike, *, fmt: str = "h5", **options: Any) -> None:
        """将模型保存到文件。"""

        resolve_model_runtime(self, action="save").save_model(
            self,
            Path(path),
            fmt=fmt,
            **options,
        )

    @classmethod
    def from_file(cls, path: PathLike, *, fmt: str = "h5", **options: Any) -> Self:
        """从文件加载数据模型。

        Args:
            path: 待读取的文件路径。
            fmt: 存储格式，主线支持 `csv` 和 `h5`。
            **options: 透传给底层运行时的附加参数。常见键包括 `units`、
                `csv_read_options` 和格式控制项。

        Returns:
            当前类型对应的数据模型实例。

        Raises:
            TypeError: 底层运行时返回的对象与 `cls` 不匹配时抛出。

        Notes:
            该入口只负责统一运行时分发，不直接解析 CSV/H5。显式传入的
            `options` 会原样传给已绑定的模型运行时实现。
        """

        data = resolve_model_runtime(cls, action="load").load_model(
            cls,
            Path(path),
            fmt=fmt,
            **options,
        )
        if not isinstance(data, cls):
            raise TypeError(f"加载类型不匹配: 期望 {cls.__name__}，实际得到 {type(data).__name__}。")
        return data

    @classmethod
    def inspect_units(
        cls,
        path: PathLike,
        *,
        fmt: str = "h5",
        axis_unit: str | None = None,
        data_unit: str | None = None,
        units: Mapping[str, str | None] | None = None,
        csv_read_options: Mapping[str, Any] | None = None,
        skiprows: int | list[int] | None = None,
        sep: str | None = None,
        delimiter: str | None = None,
        header: int | list[int] | None = 0,
        names: list[str] | None = None,
        index_col: int | str | None = 0,
        encoding: str | None = "utf-8",
        comment: str | None = None,
        decimal: str | None = None,
        **options: Any,
    ) -> dict[str, str]:
        """在不完整加载对象的前提下检查文件单位。

        Args:
            path: 待读取的文件路径。
            fmt: 存储格式，主线支持 `csv` 和 `h5`。
            axis_unit: 主轴字段的显式输入单位，会覆盖 `units` 中同字段的值。
            data_unit: 主值字段的显式输入单位，会覆盖 `units` 中同字段的值。
            units: 字段级单位映射，用于补充或覆盖文件中的单位解释。
            csv_read_options: 传给 CSV 解析器的原始参数映射。
            skiprows: CSV 跳过行设置；仅在 `csv_read_options` 未声明同名键时生效。
            sep: CSV 分隔符；优先级低于 `csv_read_options` 中的同名键。
            delimiter: CSV 备用分隔符；优先级低于 `csv_read_options` 中的同名键。
            header: CSV 表头行配置；优先级低于 `csv_read_options` 中的同名键。
            names: CSV 列名列表；优先级低于 `csv_read_options` 中的同名键。
            index_col: CSV 索引列配置；优先级低于 `csv_read_options` 中的同名键。
            encoding: CSV 文件编码；优先级低于 `csv_read_options` 中的同名键。
            comment: CSV 注释符；优先级低于 `csv_read_options` 中的同名键。
            decimal: CSV 小数点符号；优先级低于 `csv_read_options` 中的同名键。
            **options: 额外透传给底层运行时的参数。

        Returns:
            字段名到单位字符串的映射，通常至少覆盖轴字段和值字段。

        Notes:
            当 `fmt="csv"` 时，显式 CSV 参数会先与 `csv_read_options` 合并，再交给
            底层运行时；其中 `csv_read_options` 中已声明的键优先级更高。
        """

        resolved_units = cls._merge_input_units(
            axis_unit=axis_unit,
            data_unit=data_unit,
            units=units,
        )
        if fmt == "csv":
            options = {
                **options,
                "units": resolved_units,
                "csv_read_options": cls._merge_csv_options(
                    csv_read_options=csv_read_options,
                    skiprows=skiprows,
                    sep=sep,
                    delimiter=delimiter,
                    header=header,
                    names=names,
                    index_col=index_col,
                    encoding=encoding,
                    comment=comment,
                    decimal=decimal,
                ),
            }
        elif resolved_units:
            options = {**options, "units": resolved_units}
        return cast(
            dict[str, str],
            resolve_model_runtime(cls, action="inspect_units").inspect_model_units(
                cls,
                Path(path),
                fmt=fmt,
                **options,
            ),
        )

    def to_csv(self, path: PathLike, **options: Any) -> None:
        """保存为 CSV。"""

        self.to_file(path, fmt="csv", **options)

    def to_h5(self, path: PathLike, **options: Any) -> None:
        """保存为 HDF5。"""

        self.to_file(path, fmt="h5", **options)

    @classmethod
    def from_csv(
        cls,
        path: PathLike,
        *,
        axis_unit: str | None = None,
        data_unit: str | None = None,
        units: Mapping[str, str | None] | None = None,
        csv_read_options: Mapping[str, Any] | None = None,
        skiprows: int | list[int] | None = None,
        sep: str | None = None,
        delimiter: str | None = None,
        header: int | list[int] | None = 0,
        names: list[str] | None = None,
        index_col: int | str | None = 0,
        encoding: str | None = "utf-8",
        comment: str | None = None,
        decimal: str | None = None,
        **options: Any,
    ) -> Self:
        """从 CSV 文件恢复数据模型。

        Args:
            path: 待读取的 CSV 文件路径。
            axis_unit: 主轴字段的显式输入单位，会覆盖 `units` 中同字段的值。
            data_unit: 主值字段的显式输入单位，会覆盖 `units` 中同字段的值。
            units: 字段级单位映射，用于补充或覆盖文件中的单位解释。
            csv_read_options: 传给 CSV 解析器的原始参数映射。
            skiprows: CSV 跳过行设置；仅在 `csv_read_options` 未声明同名键时生效。
            sep: CSV 分隔符；优先级低于 `csv_read_options` 中的同名键。
            delimiter: CSV 备用分隔符；优先级低于 `csv_read_options` 中的同名键。
            header: CSV 表头行配置；优先级低于 `csv_read_options` 中的同名键。
            names: CSV 列名列表；优先级低于 `csv_read_options` 中的同名键。
            index_col: CSV 索引列配置；优先级低于 `csv_read_options` 中的同名键。
            encoding: CSV 文件编码；优先级低于 `csv_read_options` 中的同名键。
            comment: CSV 注释符；优先级低于 `csv_read_options` 中的同名键。
            decimal: CSV 小数点符号；优先级低于 `csv_read_options` 中的同名键。
            **options: 额外透传给底层运行时的参数。

        Returns:
            当前类型对应的数据模型实例。

        Notes:
            `axis_unit`、`data_unit` 与 `units` 会先合并成字段级单位映射，再与
            CSV 参数一并透传给 `from_file(..., fmt="csv")`。显式 CSV 参数仅在
            `csv_read_options` 未声明同名键时才会写入最终解析配置。
        """

        resolved_units = cls._merge_input_units(
            axis_unit=axis_unit,
            data_unit=data_unit,
            units=units,
        )
        parser_options = cls._merge_csv_options(
            csv_read_options=csv_read_options,
            skiprows=skiprows,
            sep=sep,
            delimiter=delimiter,
            header=header,
            names=names,
            index_col=index_col,
            encoding=encoding,
            comment=comment,
            decimal=decimal,
        )
        return cls.from_file(
            path,
            fmt="csv",
            units=resolved_units,
            csv_read_options=parser_options,
            **options,
        )

    @classmethod
    def from_h5(
        cls,
        path: PathLike,
        *,
        axis_unit: str | None = None,
        data_unit: str | None = None,
        units: Mapping[str, str | None] | None = None,
        **options: Any,
    ) -> Self:
        """从 HDF5 文件恢复数据模型。"""

        return cls.from_file(
            path,
            fmt="h5",
            units=cls._merge_input_units(
                axis_unit=axis_unit,
                data_unit=data_unit,
                units=units,
            ),
            **options,
        )

    @staticmethod
    def _convert_field(
        values: Any,
        *,
        source_unit: str | None,
        target_unit: str | None,
    ) -> np.ndarray:
        """按源单位和目标单位转换字段数组。"""

        return convert_array(values, from_unit=source_unit, to_unit=target_unit)

    @staticmethod
    def _normalize_units_map(
        units: Mapping[str, str | None] | None,
    ) -> dict[str, str]:
        """将输入单位映射规范化为字段到单位的字典。"""

        return normalize_unit_map(units)

    @classmethod
    def _merge_input_units(
        cls,
        *,
        axis_unit: str | None = None,
        data_unit: str | None = None,
        units: Mapping[str, str | None] | None = None,
    ) -> dict[str, str] | None:
        """合并轴单位、值单位和字段级单位映射。"""

        resolved = normalize_unit_map(units)
        if axis_unit is not None and cls.axis_field is not None:
            resolved[cls.axis_field] = normalize_unit(axis_unit) or axis_unit
        if data_unit is not None and cls.value_field is not None:
            resolved[cls.value_field] = normalize_unit(data_unit) or data_unit
        return resolved or None

    @staticmethod
    def _merge_csv_options(
        *,
        csv_read_options: Mapping[str, Any] | None = None,
        skiprows: int | list[int] | None = None,
        sep: str | None = None,
        delimiter: str | None = None,
        header: int | list[int] | None = 0,
        names: list[str] | None = None,
        index_col: int | str | None = 0,
        encoding: str | None = "utf-8",
        comment: str | None = None,
        decimal: str | None = None,
    ) -> dict[str, Any]:
        """合并标准 CSV 读取参数。"""

        merged = dict(csv_read_options or {})
        explicit = {
            "skiprows": skiprows,
            "sep": sep,
            "delimiter": delimiter,
            "header": header,
            "names": names,
            "index_col": index_col,
            "encoding": encoding,
            "comment": comment,
            "decimal": decimal,
        }
        for key, value in explicit.items():
            if value is not None and key not in merged:
                merged[key] = value
        return merged

    def to_plot_payload(
        self,
        *,
        kind: object | None = None,
    ) -> dict[str, object]:
        """导出与 plotting 模块兼容的标准绘图 payload。"""

        from ..plot_types import PlotKind
        from .plot_payloads import model_to_plot_payload

        if kind is not None and not isinstance(kind, PlotKind):
            raise TypeError("kind 必须是 PlotKind 枚举")
        return model_to_plot_payload(self, kind=kind)

    @classmethod
    def from_arrays(cls, axis: np.ndarray, value: np.ndarray, **kwargs: Any) -> Self:
        """从轴数组和值数组构建模型。"""

        raise NotImplementedError(f"{cls.__name__} 尚未实现 from_arrays()。")


__all__ = ["DataModelBase", "MagnitudeConversion"]
