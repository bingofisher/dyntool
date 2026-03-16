"""反应谱模型。"""

from __future__ import annotations
from typing import Any, ClassVar, Mapping, Self

import numpy as np
import pandas as pd
import xarray as xr

from .conversion import MagnitudeConversion
from .base import DataModelBase
from ..constants import (
    DataCategory,
    UnitSystem,
    convert_array,
    format_label_with_unit,
    get_default_unit_system,
    normalize_unit_map,
    parse_label_unit,
    resolve_current_units,
    resolve_file_units,
)


_CURRENT_UNITS_ATTR = "_current_units"


class ResponseSpectrum(DataModelBase):
    """反应谱容器基类。"""

    category: ClassVar[DataCategory] = DataCategory.RS
    axis_field: ClassVar[str | None] = "period"
    value_field: ClassVar[str | None] = "value"

    def __init__(self, data: xr.DataArray) -> None:
        if "T" not in data.dims and "T" not in data.coords:
            raise ValueError("ResponseSpectrum requires a `T` dimension or coordinate.")
        self._data = data

    @property
    def xr(self) -> xr.DataArray:
        """暴露底层 `xarray.DataArray` 对象。"""

        return self._data

    @property
    def xr_base(self) -> xr.DataArray:
        """返回内部基础单位存储的底层 ``xarray.DataArray``。"""

        return self._data

    @property
    def T(self) -> np.ndarray:
        """返回当前单位下的响应谱周期轴。"""

        return self.get_axis()

    @property
    def value(self) -> np.ndarray:
        """返回当前单位下的响应谱取值。"""

        return self.get_value()

    @classmethod
    def _base_axis_unit(cls) -> str:
        return "second"

    @classmethod
    def _base_value_unit(cls) -> str:
        return "dimensionless"

    @classmethod
    def _default_current_units(cls, unit_system: UnitSystem | None = None) -> dict[str, str]:
        units = unit_system or get_default_unit_system()
        return {"period": units.period, "value": cls._base_value_unit()}

    @classmethod
    def _resolve_current_units(
        cls,
        *,
        units: Mapping[str, str | None] | None = None,
        unit_system: UnitSystem | None = None,
    ) -> dict[str, str]:
        current = resolve_current_units(cls._default_current_units(unit_system), units=units)
        if "period" not in current:
            current["period"] = cls._base_axis_unit()
        if "value" not in current:
            current["value"] = cls._base_value_unit()
        return current

    def current_units(self) -> dict[str, str]:
        """返回当前实例的单位映射。"""

        return self.base_units()

    def base_units(self) -> dict[str, str]:
        """返回模型内部固定使用的基准单位。"""

        period_unit = str(self._data.coords["T"].attrs.get("units", self._base_axis_unit()))
        value_unit = str(self._data.attrs.get("units", self._base_value_unit()))
        return {"period": period_unit, "value": value_unit}

    def _base_axis_values(self) -> np.ndarray:
        return MagnitudeConversion.to_magnitude(self._data.coords["T"]).flatten()

    def _base_value_values(self) -> np.ndarray:
        return MagnitudeConversion.to_magnitude(self._data)

    def get_field(self, name: str, unit: str | None = None) -> np.ndarray:
        """返回目标单位或当前单位下的字段数组。"""

        base = self.base_units()
        if name in {"period", "T"}:
            return convert_array(
                self._base_axis_values(),
                from_unit=base["period"],
                to_unit=unit or base["period"],
            )
        if name == "value":
            return convert_array(
                self._base_value_values(),
                from_unit=base["value"],
                to_unit=unit or base["value"],
            )
        raise KeyError(f"{self.__class__.__name__} does not expose field {name!r}.")

    def convert_units(
        self,
        units: Mapping[str, str | None],
        *,
        replace: bool = True,
    ) -> Self:
        """转换单位，默认原地修改响应谱对象。"""

        current = self.current_units().copy()
        normalized = normalize_unit_map(units)
        if "T" in normalized and "period" not in normalized:
            normalized["period"] = normalized.pop("T")
        current.update(normalized)
        converted = self.__class__._from_base_data(
            convert_array(
                self._base_axis_values(),
                from_unit=self.base_units()["period"],
                to_unit=current["period"],
            ),
            convert_array(
                self._base_value_values(),
                from_unit=self.base_units()["value"],
                to_unit=current["value"],
            ),
            units=current,
        )
        if replace:
            self._data = converted._data
            return self
        return converted

    @classmethod
    def _from_base_data(
        cls,
        T: np.ndarray | list | Any,
        value: np.ndarray | list | Any,
        *,
        units: Mapping[str, str | None] | None = None,
        unit_system: UnitSystem | None = None,
    ) -> Self:
        current = cls._resolve_current_units(units=units, unit_system=unit_system)
        period_arr = np.asarray(T, dtype=np.float64).flatten()
        value_arr = np.asarray(value, dtype=np.float64)
        if value_arr.ndim == 1:
            dims = ["T"]
            data = value_arr
        elif value_arr.ndim == 2:
            dims = ["T", "channel"]
            data = value_arr
        else:
            raise ValueError("value only supports 1D or 2D arrays.")
        if len(period_arr) != data.shape[0]:
            raise ValueError("T length must match the first dimension of value.")
        da = xr.DataArray(
            data,
            dims=dims,
            coords={"T": ("T", period_arr, {"units": current["period"]})},
            attrs={"units": current["value"], _CURRENT_UNITS_ATTR: current},
        )
        return cls(da)

    @classmethod
    def from_data(
        cls,
        T: np.ndarray | list | Any,
        value: np.ndarray | list | Any,
        *,
        axis_unit: str | None = None,
        data_unit: str | None = None,
        units: Mapping[str, str | None] | None = None,
        unit_system: UnitSystem | None = None,
    ) -> Self:
        """按输入单位构造反应谱。"""

        current = cls._resolve_current_units(
            units=cls._merge_input_units(
                axis_unit=axis_unit,
                data_unit=data_unit,
                units=units,
            ),
            unit_system=unit_system,
        )
        period_arr = np.asarray(T, dtype=np.float64).flatten()
        value_arr = np.asarray(value, dtype=np.float64)
        return cls._from_base_data(period_arr, value_arr, units=current, unit_system=unit_system)

    @classmethod
    def from_arrays(cls, axis: np.ndarray, value: np.ndarray, **kwargs: object) -> Self:
        """从数组重建响应谱。"""

        return cls.from_data(axis, value, **kwargs)

    def slice_period(self, t_min: float, t_max: float) -> Self:
        """按周期范围截取响应谱。"""

        if t_min >= t_max:
            raise ValueError("t_min must be less than t_max.")
        periods = self.get_axis(unit="second")
        values = self._base_value_values()
        mask = (periods >= t_min) & (periods <= t_max)
        if not np.any(mask):
            raise ValueError("No data found in the requested period range.")
        return self.__class__._from_base_data(
            convert_array(
                periods[mask],
                from_unit="second",
                to_unit=self.axis_unit,
            ),
            values[mask],
            units=self.current_units(),
        )

    def to_pandas(self) -> pd.DataFrame:
        """将响应谱转换为带当前单位标签的 DataFrame。"""

        index = pd.Index(
            self.get_axis(),
            name=format_label_with_unit("period", self.current_units()["period"]),
        )
        values = self.get_value()
        if values.ndim > 1:
            values = values.squeeze()
        return pd.DataFrame(
            {format_label_with_unit("value", self.current_units()["value"]): values},
            index=index,
        )

    @classmethod
    def from_pandas(
        cls,
        df: pd.DataFrame,
        *,
        axis_unit: str | None = None,
        data_unit: str | None = None,
        units: Mapping[str, str | None] | None = None,
        unit_system: UnitSystem | None = None,
    ) -> Self:
        """根据 DataFrame 构造反应谱。"""

        _, parsed_axis_unit = parse_label_unit(df.index.name or "period")
        _, parsed_value_unit = parse_label_unit(df.columns[0] if len(df.columns) > 0 else "value")
        current = resolve_file_units(
            {"period", "value"},
            parsed_units={"period": parsed_axis_unit, "value": parsed_value_unit},
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
        model = cls.from_data(
            df.index.to_numpy(),
            df.iloc[:, 0].to_numpy() if len(df.columns) == 1 else df.to_numpy(),
            units=default_current,
            unit_system=unit_system,
        )
        return model

    def to_dict(self) -> dict[str, Any]:
        """序列化响应谱及其当前单位元数据。"""

        return {
            "T": self.get_axis(),
            "value": self.get_value(),
            "_units": self.current_units(),
        }

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
        category: DataCategory | None = None,
        *,
        axis_unit: str | None = None,
        data_unit: str | None = None,
        units: Mapping[str, str | None] | None = None,
        unit_system: UnitSystem | None = None,
    ) -> Self:
        """根据字典负载反序列化反应谱。"""

        del category
        parsed_units = data.get("_units", {})
        if "T" in parsed_units and "period" not in parsed_units:
            parsed_units = dict(parsed_units)
            parsed_units["period"] = parsed_units["T"]
        current = resolve_file_units(
            {"period", "value"},
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
        model = cls.from_data(
            data["T"],
            data["value"],
            units=default_current,
            unit_system=unit_system,
        )
        return model


class SpecAccelSeries(ResponseSpectrum):
    """谱加速度序列。"""

    category: ClassVar[DataCategory] = DataCategory.RS_SA

    @classmethod
    def _base_value_unit(cls) -> str:
        return "meter/second**2"

    @classmethod
    def _default_current_units(cls, unit_system: UnitSystem | None = None) -> dict[str, str]:
        units = unit_system or get_default_unit_system()
        return {"period": units.period, "value": units.acceleration}


class SpecVelSeries(ResponseSpectrum):
    """谱速度序列。"""

    category: ClassVar[DataCategory] = DataCategory.RS_SV

    @classmethod
    def _base_value_unit(cls) -> str:
        return "meter/second"

    @classmethod
    def _default_current_units(cls, unit_system: UnitSystem | None = None) -> dict[str, str]:
        units = unit_system or get_default_unit_system()
        return {"period": units.period, "value": units.velocity}


class SpecDispSeries(ResponseSpectrum):
    """谱位移序列。"""

    category: ClassVar[DataCategory] = DataCategory.RS_SD

    @classmethod
    def _base_value_unit(cls) -> str:
        return "meter"

    @classmethod
    def _default_current_units(cls, unit_system: UnitSystem | None = None) -> dict[str, str]:
        units = unit_system or get_default_unit_system()
        return {"period": units.period, "value": units.displacement}


class PSpecAccelSeries(ResponseSpectrum):
    """伪谱加速度序列。"""

    category: ClassVar[DataCategory] = DataCategory.RS_PSA

    @classmethod
    def _base_value_unit(cls) -> str:
        return "meter/second**2"

    @classmethod
    def _default_current_units(cls, unit_system: UnitSystem | None = None) -> dict[str, str]:
        units = unit_system or get_default_unit_system()
        return {"period": units.period, "value": units.acceleration}


class PSpecVelSeries(ResponseSpectrum):
    """伪谱速度序列。"""

    category: ClassVar[DataCategory] = DataCategory.RS_PSV

    @classmethod
    def _base_value_unit(cls) -> str:
        return "meter/second"

    @classmethod
    def _default_current_units(cls, unit_system: UnitSystem | None = None) -> dict[str, str]:
        units = unit_system or get_default_unit_system()
        return {"period": units.period, "value": units.velocity}


class RespSpec(DataModelBase):
    """组合响应谱对象。"""

    category: ClassVar[DataCategory] = DataCategory.RS_SPEC
    axis_field: ClassVar[str | None] = "period"
    value_field: ClassVar[str | None] = None

    def __init__(
        self,
        *,
        sa: SpecAccelSeries | None = None,
        sv: SpecVelSeries | None = None,
        sd: SpecDispSeries | None = None,
        psa: PSpecAccelSeries | None = None,
        psv: PSpecVelSeries | None = None,
    ) -> None:
        if all(item is None for item in (sa, sv, sd, psa, psv)):
            raise ValueError("RespSpec requires at least one component.")
        self.sa = sa
        self.sv = sv
        self.sd = sd
        self.psa = psa
        self.psv = psv

    def _first_component(self) -> ResponseSpectrum:
        for item in (self.sa, self.sv, self.sd, self.psa, self.psv):
            if item is not None:
                return item
        raise ValueError("RespSpec has no available components.")

    @property
    def T(self) -> np.ndarray:
        """返回共享响应谱周期轴。"""

        return self.get_axis()

    def current_units(self) -> dict[str, str]:
        """返回共享轴及各分量的当前单位。"""

        units = {"period": self._first_component().current_units()["period"]}
        for name, item in (
            ("sa", self.sa),
            ("sv", self.sv),
            ("sd", self.sd),
            ("psa", self.psa),
            ("psv", self.psv),
        ):
            if item is not None:
                units[name] = item.current_units()["value"]
        return units

    def base_units(self) -> dict[str, str]:
        """返回共享轴及各分量的内部基准单位。"""

        units = {"period": "second"}
        if self.sa is not None:
            units["sa"] = self.sa.base_units()["value"]
        if self.sv is not None:
            units["sv"] = self.sv.base_units()["value"]
        if self.sd is not None:
            units["sd"] = self.sd.base_units()["value"]
        if self.psa is not None:
            units["psa"] = self.psa.base_units()["value"]
        if self.psv is not None:
            units["psv"] = self.psv.base_units()["value"]
        return units

    def get_field(self, name: str, unit: str | None = None) -> np.ndarray:
        """返回目标单位下的响应谱分量。"""

        if name in {"period", "T"}:
            return self._first_component().get_axis(unit=unit)
        component = getattr(self, name, None)
        if component is None:
            raise KeyError(f"RespSpec is missing field {name!r}.")
        return component.get_value(unit=unit)

    def get_value(self, unit: str | None = None) -> np.ndarray:
        """返回当前单位下的分量堆叠矩阵。"""

        del unit
        columns: list[np.ndarray] = []
        for item in (self.sa, self.sv, self.sd, self.psa, self.psv):
            if item is not None:
                columns.append(np.asarray(item.get_value()).squeeze())
        if not columns:
            raise ValueError("RespSpec has no available values.")
        return np.column_stack(columns)

    def convert_units(
        self,
        units: Mapping[str, str | None],
        *,
        replace: bool = True,
    ) -> Self:
        """转换组合响应谱的单位。"""

        normalized = normalize_unit_map(units)
        period_unit = normalized.get("period") or normalized.get("T")
        converted = self.__class__(
            sa=self.sa.convert_units(
                {"period": period_unit, "value": normalized.get("sa")},
                replace=replace,
            )
            if self.sa is not None
            else None,
            sv=self.sv.convert_units(
                {"period": period_unit, "value": normalized.get("sv")},
                replace=replace,
            )
            if self.sv is not None
            else None,
            sd=self.sd.convert_units(
                {"period": period_unit, "value": normalized.get("sd")},
                replace=replace,
            )
            if self.sd is not None
            else None,
            psa=self.psa.convert_units(
                {"period": period_unit, "value": normalized.get("psa")},
                replace=replace,
            )
            if self.psa is not None
            else None,
            psv=self.psv.convert_units(
                {"period": period_unit, "value": normalized.get("psv")},
                replace=replace,
            )
            if self.psv is not None
            else None,
        )
        if replace:
            self.sa = converted.sa
            self.sv = converted.sv
            self.sd = converted.sd
            self.psa = converted.psa
            self.psv = converted.psv
            return self
        return converted

    @classmethod
    def from_series(
        cls,
        *,
        sa: SpecAccelSeries | None = None,
        sv: SpecVelSeries | None = None,
        sd: SpecDispSeries | None = None,
        psa: PSpecAccelSeries | None = None,
        psv: PSpecVelSeries | None = None,
    ) -> Self:
        """根据各分量构建组合响应谱。"""

        return cls(sa=sa, sv=sv, sd=sd, psa=psa, psv=psv)

    @classmethod
    def from_data(
        cls,
        T: np.ndarray | list | Any,
        *,
        sa: np.ndarray | list | Any | None = None,
        sv: np.ndarray | list | Any | None = None,
        sd: np.ndarray | list | Any | None = None,
        psa: np.ndarray | list | Any | None = None,
        psv: np.ndarray | list | Any | None = None,
        units: Mapping[str, str | None] | None = None,
        unit_system: UnitSystem | None = None,
    ) -> Self:
        """根据原始数组构建组合响应谱。"""

        unit_map = normalize_unit_map(units)
        return cls(
            sa=SpecAccelSeries.from_data(
                T,
                sa,
                units={
                    "period": unit_map.get("period") or unit_map.get("T"),
                    "value": unit_map.get("sa"),
                },
                unit_system=unit_system,
            )
            if sa is not None
            else None,
            sv=SpecVelSeries.from_data(
                T,
                sv,
                units={
                    "period": unit_map.get("period") or unit_map.get("T"),
                    "value": unit_map.get("sv"),
                },
                unit_system=unit_system,
            )
            if sv is not None
            else None,
            sd=SpecDispSeries.from_data(
                T,
                sd,
                units={
                    "period": unit_map.get("period") or unit_map.get("T"),
                    "value": unit_map.get("sd"),
                },
                unit_system=unit_system,
            )
            if sd is not None
            else None,
            psa=PSpecAccelSeries.from_data(
                T,
                psa,
                units={
                    "period": unit_map.get("period") or unit_map.get("T"),
                    "value": unit_map.get("psa"),
                },
                unit_system=unit_system,
            )
            if psa is not None
            else None,
            psv=PSpecVelSeries.from_data(
                T,
                psv,
                units={
                    "period": unit_map.get("period") or unit_map.get("T"),
                    "value": unit_map.get("psv"),
                },
                unit_system=unit_system,
            )
            if psv is not None
            else None,
        )

    @classmethod
    def from_arrays(
        cls,
        axis: np.ndarray,
        value: np.ndarray,
        **kwargs: Any,
    ) -> Self:
        """根据周期轴和矩阵构建组合响应谱。"""

        matrix = np.asarray(value)
        if matrix.ndim != 2 or matrix.shape[1] < 5:
            raise ValueError("RespSpec.from_arrays expects a Nx5 array.")
        return cls.from_data(
            axis,
            sa=matrix[:, 0],
            sv=matrix[:, 1],
            sd=matrix[:, 2],
            psa=matrix[:, 3],
            psv=matrix[:, 4],
            **kwargs,
        )

    def to_pandas(self) -> pd.DataFrame:
        """将组合响应谱转换为带单位标签的 DataFrame。"""

        data: dict[str, Any] = {}
        for name, item in (
            ("sa", self.sa),
            ("sv", self.sv),
            ("sd", self.sd),
            ("psa", self.psa),
            ("psv", self.psv),
        ):
            if item is not None:
                data[format_label_with_unit(name, item.value_unit)] = np.asarray(item.get_value()).squeeze()
        return pd.DataFrame(
            data,
            index=pd.Index(
                self.get_axis(),
                name=format_label_with_unit("period", self.current_units()["period"]),
            ),
        )

    @classmethod
    def from_pandas(
        cls,
        df: pd.DataFrame,
        *,
        units: Mapping[str, str | None] | None = None,
        unit_system: UnitSystem | None = None,
    ) -> Self:
        """从 DataFrame 构建组合响应谱。"""

        _, axis_unit = parse_label_unit(df.index.name or "period")
        parsed_units: dict[str, str | None] = {"period": axis_unit}
        columns_by_name: dict[str, str] = {}
        for col in df.columns:
            field_name, field_unit = parse_label_unit(col)
            parsed_units[field_name] = field_unit
            columns_by_name[field_name] = col
        required = {"period"} | set(columns_by_name.keys())
        current = resolve_file_units(
            required,
            parsed_units=parsed_units,
            units=units,
            allow_partial=True,
        )
        model = cls.from_data(
            df.index.to_numpy(),
            sa=df[columns_by_name["sa"]].to_numpy() if "sa" in columns_by_name else None,
            sv=df[columns_by_name["sv"]].to_numpy() if "sv" in columns_by_name else None,
            sd=df[columns_by_name["sd"]].to_numpy() if "sd" in columns_by_name else None,
            psa=df[columns_by_name["psa"]].to_numpy() if "psa" in columns_by_name else None,
            psv=df[columns_by_name["psv"]].to_numpy() if "psv" in columns_by_name else None,
            units=current if current else units,
            unit_system=unit_system,
        )
        return model

    def to_dict(self) -> dict[str, Any]:
        """序列化组合响应谱。"""

        return {
            "sa": self.sa.to_dict() if self.sa is not None else None,
            "sv": self.sv.to_dict() if self.sv is not None else None,
            "sd": self.sd.to_dict() if self.sd is not None else None,
            "psa": self.psa.to_dict() if self.psa is not None else None,
            "psv": self.psv.to_dict() if self.psv is not None else None,
        }

    @classmethod
    def from_dict(
        cls,
        data: dict,
        category: DataCategory | None = None,
    ) -> Self:
        """反序列化组合响应谱。"""

        del category
        model = cls(
            sa=SpecAccelSeries.from_dict(data["sa"]) if data.get("sa") else None,
            sv=SpecVelSeries.from_dict(data["sv"]) if data.get("sv") else None,
            sd=SpecDispSeries.from_dict(data["sd"]) if data.get("sd") else None,
            psa=PSpecAccelSeries.from_dict(data["psa"]) if data.get("psa") else None,
            psv=PSpecVelSeries.from_dict(data["psv"]) if data.get("psv") else None,
        )
        return model

    def slice_period(self, t_min: float, t_max: float) -> Self:
        """按周期范围截取全部可用分量。"""

        return self.__class__(
            sa=self.sa.slice_period(t_min, t_max) if self.sa is not None else None,
            sv=self.sv.slice_period(t_min, t_max) if self.sv is not None else None,
            sd=self.sd.slice_period(t_min, t_max) if self.sd is not None else None,
            psa=self.psa.slice_period(t_min, t_max) if self.psa is not None else None,
            psv=self.psv.slice_period(t_min, t_max) if self.psv is not None else None,
        )
