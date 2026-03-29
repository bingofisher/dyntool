"""频谱模型。"""

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


class FreqAmpSeries(DataModelBase):
    """频率-幅值序列。"""

    category: ClassVar[DataCategory] = DataCategory.FS_AMP
    axis_field: ClassVar[str | None] = "freq"
    value_field: ClassVar[str | None] = "amp"

    def __init__(self, data: xr.DataArray) -> None:
        if "freq" not in data.dims and "freq" not in data.coords:
            raise ValueError("FreqAmpSeries requires a `freq` dimension or coordinate.")
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
    def freq(self) -> np.ndarray:
        """返回当前单位下的频率轴。"""

        return self.get_axis()

    @property
    def amp(self) -> np.ndarray:
        """返回当前单位下的幅值数组。"""

        return self.get_value()

    @classmethod
    def _base_axis_unit(cls) -> str:
        return "hertz"

    @classmethod
    def _default_current_units(cls, unit_system: UnitSystem | None = None) -> dict[str, str]:
        units = unit_system or get_default_unit_system()
        return {"freq": units.frequency, "amp": units.spectrum_amplitude}

    @classmethod
    def _resolve_current_units(
        cls,
        *,
        units: Mapping[str, str | None] | None = None,
        unit_system: UnitSystem | None = None,
    ) -> dict[str, str]:
        current = resolve_current_units(cls._default_current_units(unit_system), units=units)
        if "freq" not in current:
            current["freq"] = cls._base_axis_unit()
        return current

    def current_units(self) -> dict[str, str]:
        """返回当前实例的单位映射。"""

        return self.base_units()

    def base_units(self) -> dict[str, str]:
        """返回频率和幅值的内部存储单位。"""

        return {
            "freq": str(self._data.coords["freq"].attrs.get("units", self._base_axis_unit())),
            "amp": str(self._data.attrs.get("units", "dimensionless")),
        }

    def _base_axis_values(self) -> np.ndarray:
        return MagnitudeConversion.to_magnitude(self._data.coords["freq"]).flatten()

    def _base_value_values(self) -> np.ndarray:
        return MagnitudeConversion.to_magnitude(self._data)

    def get_field(self, name: str, unit: str | None = None) -> np.ndarray:
        """返回目标单位或当前单位下的字段数组。"""

        base = self.base_units()
        if name == "freq":
            return convert_array(
                self._base_axis_values(),
                from_unit=base["freq"],
                to_unit=unit or base["freq"],
            )
        if name == "amp":
            return convert_array(
                self._base_value_values(),
                from_unit=base["amp"],
                to_unit=unit or base["amp"],
            )
        raise KeyError(f"{self.__class__.__name__} does not expose field {name!r}.")

    def convert_units(
        self,
        units: Mapping[str, str | None],
        *,
        replace: bool = True,
    ) -> Self:
        """转换单位，默认原地修改当前对象。"""

        current = self.current_units().copy()
        current.update(normalize_unit_map(units))
        converted = self.__class__._from_base_data(
            convert_array(
                self._base_axis_values(),
                from_unit=self.base_units()["freq"],
                to_unit=current["freq"],
            ),
            convert_array(
                self._base_value_values(),
                from_unit=self.base_units()["amp"],
                to_unit=current["amp"],
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
        freq: np.ndarray | list | Any,
        amp: np.ndarray | list | Any,
        *,
        units: Mapping[str, str | None] | None = None,
        unit_system: UnitSystem | None = None,
    ) -> Self:
        current = cls._resolve_current_units(units=units, unit_system=unit_system)
        freq_arr = np.asarray(freq, dtype=np.float64).flatten()
        amp_arr = np.asarray(amp, dtype=np.float64)
        if amp_arr.ndim == 1:
            dims = ["freq"]
            data = amp_arr
        elif amp_arr.ndim == 2:
            dims = ["freq", "channel"]
            data = amp_arr
        else:
            raise ValueError("amp only supports 1D or 2D arrays.")
        if len(freq_arr) != data.shape[0]:
            raise ValueError("freq length must match the first dimension of amp.")
        da = xr.DataArray(
            data,
            dims=dims,
            coords={"freq": ("freq", freq_arr, {"units": current["freq"]})},
            attrs={"units": current["amp"], _CURRENT_UNITS_ATTR: current},
        )
        return cls(da)

    @classmethod
    def from_data(
        cls,
        freq: np.ndarray | list | Any,
        amp: np.ndarray | list | Any,
        *,
        axis_unit: str | None = None,
        data_unit: str | None = None,
        units: Mapping[str, str | None] | None = None,
        unit_system: UnitSystem | None = None,
    ) -> Self:
        """按输入单位构造频率-幅值序列。"""

        current = cls._resolve_current_units(
            units=cls._merge_input_units(
                axis_unit=axis_unit,
                data_unit=data_unit,
                units=units,
            ),
            unit_system=unit_system,
        )
        freq_arr = np.asarray(freq, dtype=np.float64).flatten()
        amp_arr = np.asarray(amp, dtype=np.float64)
        return cls._from_base_data(
            freq_arr,
            amp_arr,
            units=current,
            unit_system=unit_system,
        )

    @classmethod
    def from_arrays(cls, axis: np.ndarray, value: np.ndarray, **options: Any) -> Self:
        """从原始数组重建频率-幅值序列。"""

        return cls.from_data(axis, value, **options)

    def slice_freq(self, f_low: float, f_high: float) -> Self:
        """按频率范围截取频谱。"""

        if f_low >= f_high:
            raise ValueError("f_low must be less than f_high.")
        freq_hz = self.get_axis(unit="hertz")
        amp = self._base_value_values()
        mask = (freq_hz >= f_low) & (freq_hz <= f_high)
        if not np.any(mask):
            raise ValueError("No data found in the requested frequency range.")
        return self.__class__._from_base_data(
            convert_array(
                freq_hz[mask],
                from_unit="hertz",
                to_unit=self.axis_unit,
            ),
            amp[mask],
            units=self.current_units(),
        )

    def to_pandas(self) -> pd.DataFrame:
        """将频谱转换为带当前单位标签的 DataFrame。"""

        index = pd.Index(self.get_axis(), name=format_label_with_unit("freq", self.axis_unit))
        value_name = format_label_with_unit("amp", self.value_unit)
        values = self.get_value()
        if values.ndim > 1:
            values = values.squeeze()
        return pd.DataFrame({value_name: values}, index=index)

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
        """根据 DataFrame 构造频率-幅值序列。"""

        _, parsed_axis_unit = parse_label_unit(df.index.name or "freq")
        _, parsed_value_unit = parse_label_unit(df.columns[0] if len(df.columns) > 0 else "amp")
        current = resolve_file_units(
            {"freq", "amp"},
            parsed_units={"freq": parsed_axis_unit, "amp": parsed_value_unit},
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
        """序列化当前单位数组及其单位元数据。"""

        return {
            "freq": self.get_axis(),
            "amp": self.get_value(),
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
        """根据字典负载反序列化频率-幅值序列。"""

        del category
        current = resolve_file_units(
            {"freq", "amp"},
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
        model = cls.from_data(
            data["freq"],
            data["amp"],
            units=default_current,
            unit_system=unit_system,
        )
        return model


class FreqPhaSeries(DataModelBase):
    """基于 `xarray.DataArray` 的频率-相位序列。"""

    category: ClassVar[DataCategory] = DataCategory.FS_PHA
    axis_field: ClassVar[str | None] = "freq"
    value_field: ClassVar[str | None] = "phase"

    def __init__(self, data: xr.DataArray) -> None:
        if "freq" not in data.dims and "freq" not in data.coords:
            raise ValueError("FreqPhaSeries requires a `freq` dimension or coordinate.")
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
    def freq(self) -> np.ndarray:
        """返回当前单位下的频率轴。"""

        return self.get_axis()

    @property
    def phase(self) -> np.ndarray:
        """返回当前单位下的相位数组。"""

        return self.get_value()

    @classmethod
    def _base_axis_unit(cls) -> str:
        return "hertz"

    @classmethod
    def _base_value_unit(cls) -> str:
        return "radian"

    @classmethod
    def _default_current_units(cls, unit_system: UnitSystem | None = None) -> dict[str, str]:
        units = unit_system or get_default_unit_system()
        return {"freq": units.frequency, "phase": units.phase}

    @classmethod
    def _resolve_current_units(
        cls,
        *,
        units: Mapping[str, str | None] | None = None,
        unit_system: UnitSystem | None = None,
    ) -> dict[str, str]:
        current = resolve_current_units(cls._default_current_units(unit_system), units=units)
        if "freq" not in current:
            current["freq"] = cls._base_axis_unit()
        if "phase" not in current:
            current["phase"] = cls._base_value_unit()
        return current

    def current_units(self) -> dict[str, str]:
        """返回当前实例的单位映射。"""

        return self.base_units()

    def base_units(self) -> dict[str, str]:
        """返回内部存储单位。"""

        return {
            "freq": str(self._data.coords["freq"].attrs.get("units", self._base_axis_unit())),
            "phase": str(self._data.attrs.get("units", self._base_value_unit())),
        }

    def _base_axis_values(self) -> np.ndarray:
        return MagnitudeConversion.to_magnitude(self._data.coords["freq"]).flatten()

    def _base_value_values(self) -> np.ndarray:
        return MagnitudeConversion.to_magnitude(self._data)

    def get_field(self, name: str, unit: str | None = None) -> np.ndarray:
        """返回目标单位或当前单位下的字段数组。"""

        base = self.base_units()
        if name == "freq":
            return convert_array(
                self._base_axis_values(),
                from_unit=base["freq"],
                to_unit=unit or base["freq"],
            )
        if name == "phase":
            return convert_array(
                self._base_value_values(),
                from_unit=base["phase"],
                to_unit=unit or base["phase"],
            )
        raise KeyError(f"{self.__class__.__name__} does not expose field {name!r}.")

    def convert_units(
        self,
        units: Mapping[str, str | None],
        *,
        replace: bool = True,
    ) -> Self:
        """转换单位，默认原地修改当前对象。"""

        current = self.current_units().copy()
        current.update(normalize_unit_map(units))
        converted = self.__class__._from_base_data(
            convert_array(
                self._base_axis_values(),
                from_unit=self.base_units()["freq"],
                to_unit=current["freq"],
            ),
            convert_array(
                self._base_value_values(),
                from_unit=self.base_units()["phase"],
                to_unit=current["phase"],
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
        freq: np.ndarray | list | Any,
        phase: np.ndarray | list | Any,
        *,
        units: Mapping[str, str | None] | None = None,
        unit_system: UnitSystem | None = None,
    ) -> Self:
        current = cls._resolve_current_units(units=units, unit_system=unit_system)
        freq_arr = np.asarray(freq, dtype=np.float64).flatten()
        phase_arr = np.asarray(phase, dtype=np.float64)
        if phase_arr.ndim == 1:
            dims = ["freq"]
            data = phase_arr
        elif phase_arr.ndim == 2:
            dims = ["freq", "channel"]
            data = phase_arr
        else:
            raise ValueError("phase only supports 1D or 2D arrays.")
        if len(freq_arr) != data.shape[0]:
            raise ValueError("freq length must match the first dimension of phase.")
        da = xr.DataArray(
            data,
            dims=dims,
            coords={"freq": ("freq", freq_arr, {"units": current["freq"]})},
            attrs={"units": current["phase"], _CURRENT_UNITS_ATTR: current},
        )
        return cls(da)

    @classmethod
    def from_data(
        cls,
        freq: np.ndarray | list | Any,
        phase: np.ndarray | list | Any,
        *,
        axis_unit: str | None = None,
        data_unit: str | None = None,
        units: Mapping[str, str | None] | None = None,
        unit_system: UnitSystem | None = None,
    ) -> Self:
        """按输入单位构造频率-相位序列。"""

        current = cls._resolve_current_units(
            units=cls._merge_input_units(
                axis_unit=axis_unit,
                data_unit=data_unit,
                units=units,
            ),
            unit_system=unit_system,
        )
        freq_arr = np.asarray(freq, dtype=np.float64).flatten()
        phase_arr = np.asarray(phase, dtype=np.float64)
        return cls._from_base_data(freq_arr, phase_arr, units=current, unit_system=unit_system)

    @classmethod
    def from_arrays(cls, axis: np.ndarray, value: np.ndarray, **options: Any) -> Self:
        """从原始数组重建频率-相位序列。"""

        return cls.from_data(axis, value, **options)

    def slice_freq(self, f_low: float, f_high: float) -> Self:
        """按频率范围截取相位频谱。"""

        if f_low >= f_high:
            raise ValueError("f_low must be less than f_high.")
        freq_hz = self.get_axis(unit="hertz")
        phase = self._base_value_values()
        mask = (freq_hz >= f_low) & (freq_hz <= f_high)
        if not np.any(mask):
            raise ValueError("No data found in the requested frequency range.")
        return self.__class__._from_base_data(
            convert_array(
                freq_hz[mask],
                from_unit="hertz",
                to_unit=self.axis_unit,
            ),
            phase[mask],
            units=self.current_units(),
        )

    def to_pandas(self) -> pd.DataFrame:
        """将相位频谱转换为带当前单位标签的 DataFrame。"""

        index = pd.Index(self.get_axis(), name=format_label_with_unit("freq", self.axis_unit))
        value_name = format_label_with_unit("phase", self.value_unit)
        values = self.get_value()
        if values.ndim > 1:
            values = values.squeeze()
        return pd.DataFrame({value_name: values}, index=index)

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
        """根据 DataFrame 构造频率-相位序列。"""

        _, parsed_axis_unit = parse_label_unit(df.index.name or "freq")
        _, parsed_value_unit = parse_label_unit(df.columns[0] if len(df.columns) > 0 else "phase")
        current = resolve_file_units(
            {"freq", "phase"},
            parsed_units={"freq": parsed_axis_unit, "phase": parsed_value_unit},
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
        """序列化当前单位数组及其单位元数据。"""

        return {
            "freq": self.get_axis(),
            "phase": self.get_value(),
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
        """根据字典负载反序列化频率-相位序列。"""

        del category
        current = resolve_file_units(
            {"freq", "phase"},
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
        model = cls.from_data(
            data["freq"],
            data["phase"],
            units=default_current,
            unit_system=unit_system,
        )
        return model


class FreqSpec(DataModelBase):
    """包含幅值与相位的组合频谱。"""

    category: ClassVar[DataCategory] = DataCategory.FS_SPEC
    axis_field: ClassVar[str | None] = "freq"
    value_field: ClassVar[str | None] = None

    def __init__(self, amp: FreqAmpSeries | None = None, pha: FreqPhaSeries | None = None) -> None:
        if amp is None and pha is None:
            raise ValueError("FreqSpec requires at least one of amp or pha.")
        self.amp = amp
        self.pha = pha

    @property
    def freq(self) -> np.ndarray:
        """返回共享频率轴。"""

        return self.get_axis()

    def _first_component(self) -> FreqAmpSeries | FreqPhaSeries:
        source = self.amp or self.pha
        if source is None:
            raise ValueError("FreqSpec has no frequency data.")
        return source

    def current_units(self) -> dict[str, str]:
        """返回共享轴及各分量的当前单位。"""

        units = {"freq": self._first_component().axis_unit or "hertz"}
        if self.amp is not None:
            units["amp"] = self.amp.value_unit or self.amp.base_units()["amp"]
        if self.pha is not None:
            units["phase"] = self.pha.value_unit or "radian"
        return units

    def base_units(self) -> dict[str, str]:
        """返回共享轴及各分量的内部基准单位。"""

        units = {"freq": "hertz"}
        if self.amp is not None:
            units["amp"] = self.amp.base_units()["amp"]
        if self.pha is not None:
            units["phase"] = "radian"
        return units

    def get_field(self, name: str, unit: str | None = None) -> np.ndarray:
        """返回目标单位下的指定分量字段。"""

        if name == "freq":
            return self._first_component().get_axis(unit=unit)
        if name == "amp":
            if self.amp is None:
                raise KeyError("FreqSpec has no amplitude data.")
            return self.amp.get_value(unit=unit)
        if name == "phase":
            if self.pha is None:
                raise KeyError("FreqSpec has no phase data.")
            return self.pha.get_value(unit=unit)
        raise KeyError(f"FreqSpec does not expose field {name!r}.")

    def get_value(self, unit: str | None = None) -> np.ndarray:
        """返回当前单位下的分量堆叠矩阵。"""

        del unit
        columns: list[np.ndarray] = []
        if self.amp is not None:
            columns.append(np.asarray(self.amp.get_value()).squeeze())
        if self.pha is not None:
            columns.append(np.asarray(self.pha.get_value()).squeeze())
        if not columns:
            raise ValueError("FreqSpec has no spectral values.")
        return np.column_stack(columns) if len(columns) > 1 else np.asarray(columns[0])

    def convert_units(
        self,
        units: Mapping[str, str | None],
        *,
        replace: bool = True,
    ) -> Self:
        """转换组合频谱的单位。"""

        normalized = normalize_unit_map(units)
        freq_unit = normalized.get("freq")
        amp_unit = normalized.get("amp")
        phase_unit = normalized.get("phase")
        converted = self.__class__(
            amp=self.amp.convert_units(
                {"freq": freq_unit, "amp": amp_unit},
                replace=replace,
            )
            if self.amp is not None
            else None,
            pha=self.pha.convert_units(
                {"freq": freq_unit, "phase": phase_unit},
                replace=replace,
            )
            if self.pha is not None
            else None,
        )
        if replace:
            self.amp = converted.amp
            self.pha = converted.pha
            return self
        return converted

    @classmethod
    def from_series(
        cls,
        *,
        amp: FreqAmpSeries | None = None,
        pha: FreqPhaSeries | None = None,
    ) -> Self:
        """根据幅值和相位序列构建组合频谱。"""

        return cls(amp=amp, pha=pha)

    @classmethod
    def from_data(
        cls,
        freq: np.ndarray | list | Any,
        *,
        amp: np.ndarray | list | Any | None = None,
        pha: np.ndarray | list | Any | None = None,
        units: Mapping[str, str | None] | None = None,
        unit_system: UnitSystem | None = None,
    ) -> Self:
        """根据原始数组构建组合频谱。"""

        unit_map = normalize_unit_map(units)
        amp_series = (
            FreqAmpSeries.from_data(
                freq,
                amp,
                units={"freq": unit_map.get("freq"), "amp": unit_map.get("amp")},
                unit_system=unit_system,
            )
            if amp is not None
            else None
        )
        pha_series = (
            FreqPhaSeries.from_data(
                freq,
                pha,
                units={"freq": unit_map.get("freq"), "phase": unit_map.get("phase")},
                unit_system=unit_system,
            )
            if pha is not None
            else None
        )
        return cls(amp=amp_series, pha=pha_series)

    @classmethod
    def from_compute_result(
        cls,
        result: Mapping[str, Any],
        *,
        unit_system: UnitSystem | None = None,
    ) -> Self:
        """从底层 compute 命名字典装配组合频谱。"""

        return cls.from_data(
            result["freq"],
            amp=result.get("amp"),
            pha=result.get("pha"),
            units=result.get("units"),
            unit_system=unit_system or result.get("unit_system"),
        )

    @classmethod
    def from_arrays(
        cls,
        axis: np.ndarray,
        value: np.ndarray,
        **options: Any,
    ) -> Self:
        """根据共享轴和矩阵构建组合频谱。"""

        matrix = np.asarray(value)
        if matrix.ndim == 1:
            return cls.from_data(axis, amp=matrix, **options)
        if matrix.ndim != 2 or matrix.shape[1] < 2:
            raise ValueError("FreqSpec.from_arrays expects a Nx2 array for amp/pha.")
        return cls.from_data(axis, amp=matrix[:, 0], pha=matrix[:, 1], **options)

    def to_pandas(self) -> pd.DataFrame:
        """将组合频谱转换为 DataFrame。"""

        data: dict[str, Any] = {}
        if self.amp is not None:
            data[format_label_with_unit("amp", self.amp.value_unit)] = np.asarray(self.amp.get_value()).squeeze()
        if self.pha is not None:
            data[format_label_with_unit("phase", self.pha.value_unit)] = np.asarray(self.pha.get_value()).squeeze()
        return pd.DataFrame(
            data,
            index=pd.Index(
                self.get_axis(),
                name=format_label_with_unit("freq", self.current_units()["freq"]),
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
        """从 DataFrame 构建组合频谱。"""

        _, axis_unit = parse_label_unit(df.index.name or "freq")
        parsed_units: dict[str, str | None] = {"freq": axis_unit}
        amp_col = next(
            (col for col in df.columns if parse_label_unit(col)[0].startswith("amp")),
            None,
        )
        pha_col = next(
            (col for col in df.columns if parse_label_unit(col)[0].startswith("phase")),
            None,
        )
        _, parsed_units["amp"] = parse_label_unit(amp_col) if amp_col is not None else ("amp", None)
        _, parsed_units["phase"] = parse_label_unit(pha_col) if pha_col is not None else ("phase", None)
        current = resolve_file_units(
            {"freq"} | {name for name in ("amp", "phase") if parsed_units.get(name) is not None},
            parsed_units=parsed_units,
            units=units,
            allow_partial=True,
        )
        model = cls.from_data(
            df.index.to_numpy(),
            amp=df[amp_col].to_numpy() if amp_col is not None else None,
            pha=df[pha_col].to_numpy() if pha_col is not None else None,
            units=current if current else units,
            unit_system=unit_system,
        )
        return model

    def to_dict(self) -> dict[str, Any]:
        """序列化组合频谱。"""

        return {
            "amp": self.amp.to_dict() if self.amp is not None else None,
            "pha": self.pha.to_dict() if self.pha is not None else None,
        }

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
        category: DataCategory | None = None,
        *,
        unit_system: UnitSystem | None = None,
    ) -> Self:
        """反序列化组合频谱。"""

        del category, unit_system
        amp = FreqAmpSeries.from_dict(data["amp"]) if data.get("amp") else None
        pha = FreqPhaSeries.from_dict(data["pha"]) if data.get("pha") else None
        model = cls(amp=amp, pha=pha)
        return model

    def slice_freq(self, f_low: float, f_high: float) -> Self:
        """按频率范围截取全部可用分量。"""

        return self.__class__(
            amp=self.amp.slice_freq(f_low, f_high) if self.amp is not None else None,
            pha=self.pha.slice_freq(f_low, f_high) if self.pha is not None else None,
        )
