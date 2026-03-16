"""振动评价结果模型，内部使用固定基准单位，外部暴露可配置当前单位。"""

from __future__ import annotations

from typing import Any, ClassVar, Mapping, Self

import numpy as np
import pandas as pd
import xarray as xr

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


class ZVLEval(DataModelBase):
    """Z 振级评价结果。"""

    category: ClassVar[DataCategory] = DataCategory.ZVL_EVAL
    axis_field: ClassVar[str | None] = None
    value_field: ClassVar[str | None] = "zvl"

    def __init__(
        self,
        dataset: xr.Dataset | None = None,
        *,
        zvl: float | None = None,
        aw: float | None = None,
        units: Mapping[str, str | None] | None = None,
        unit_system: UnitSystem | None = None,
    ) -> None:
        if dataset is None:
            if zvl is None or aw is None:
                raise ValueError("ZVLEval requires either a dataset or both zvl and aw.")
            built = self.__class__.from_data(
                zvl=zvl,
                aw=aw,
                units=units,
                unit_system=unit_system,
            )
            self._ds = built._ds
            return
        self._ds = dataset

    @classmethod
    def _default_current_units(cls, unit_system: UnitSystem | None = None) -> dict[str, str]:
        units = unit_system or get_default_unit_system()
        return {"zvl": units.level, "aw": units.weighted_acceleration}

    @classmethod
    def _resolve_current_units(
        cls,
        *,
        units: Mapping[str, str | None] | None = None,
        unit_system: UnitSystem | None = None,
    ) -> dict[str, str]:
        return resolve_current_units(cls._default_current_units(unit_system), units=units)

    def current_units(self) -> dict[str, str]:
        """返回当前对象对外暴露的单位映射。"""
        return self.base_units()

    def base_units(self) -> dict[str, str]:
        """返回内部数据集记录的基础单位映射。"""
        return {
            "zvl": str(self._ds["zvl"].attrs.get("units", "decibel")),
            "aw": str(self._ds["aw"].attrs.get("units", "meter/second**2")),
        }

    @classmethod
    def _from_base_data(
        cls,
        *,
        zvl: float,
        aw: float,
        units: Mapping[str, str | None] | None = None,
        unit_system: UnitSystem | None = None,
    ) -> Self:
        current = cls._resolve_current_units(units=units, unit_system=unit_system)
        ds = xr.Dataset(
            {
                "zvl": ((), float(zvl), {"units": current["zvl"]}),
                "aw": ((), float(aw), {"units": current["aw"]}),
            },
            attrs={_CURRENT_UNITS_ATTR: current},
        )
        return cls(ds)

    @classmethod
    def from_data(
        cls,
        *,
        zvl: float,
        aw: float,
        units: Mapping[str, str | None] | None = None,
        unit_system: UnitSystem | None = None,
    ) -> Self:
        """根据当前单位输入构建标量评价结果。"""

        current = cls._resolve_current_units(units=units, unit_system=unit_system)
        return cls._from_base_data(
            zvl=float(zvl),
            aw=float(aw),
            units=current,
            unit_system=unit_system,
        )

    def get_field(self, name: str, unit: str | None = None) -> np.ndarray:
        """读取指定字段，并按目标单位完成换算。"""
        if name not in self._ds:
            raise KeyError(f"ZVLEval does not expose field {name!r}.")
        source = self.base_units()[name]
        target = unit or source
        return convert_array(np.asarray(self._ds[name].values), from_unit=source, to_unit=target)

    def convert_units(
        self,
        units: Mapping[str, str | None],
        *,
        replace: bool = True,
    ) -> Self:
        """将评价结果转换到目标单位视图。"""
        current = self.current_units().copy()
        current.update(normalize_unit_map(units))
        converted = self.__class__._from_base_data(
            zvl=float(
                convert_array(
                    np.asarray(self._ds["zvl"].values),
                    from_unit=self.base_units()["zvl"],
                    to_unit=current["zvl"],
                ).flat[0]
            ),
            aw=float(
                convert_array(
                    np.asarray(self._ds["aw"].values),
                    from_unit=self.base_units()["aw"],
                    to_unit=current["aw"],
                ).flat[0]
            ),
            units=current,
        )
        if replace:
            self._ds = converted._ds
            return self
        return converted

    @property
    def zvl(self) -> np.ndarray:
        """返回 Z 振级标量结果。"""
        return self.get_field("zvl")

    @property
    def aw(self) -> np.ndarray:
        """返回加权加速度标量结果。"""
        return self.get_field("aw")

    def to_dict(self) -> dict[str, Any]:
        """导出便于持久化的字典载荷。"""
        return {
            "zvl": self.get_field("zvl"),
            "aw": self.get_field("aw"),
            "_units": self.current_units(),
        }

    def to_pandas(self) -> pd.DataFrame:
        """将标量评价结果转换为单行 DataFrame。"""

        return pd.DataFrame(
            [
                {
                    format_label_with_unit("zvl", self.current_units()["zvl"]): float(self.zvl.flat[0]),
                    format_label_with_unit("aw", self.current_units()["aw"]): float(self.aw.flat[0]),
                }
            ]
        )

    @classmethod
    def from_pandas(
        cls,
        df: pd.DataFrame,
        *,
        units: Mapping[str, str | None] | None = None,
        unit_system: UnitSystem | None = None,
    ) -> Self:
        """从单行 DataFrame 构建标量评价结果。"""

        if df.empty:
            raise ValueError("ZVLEval.from_pandas requires at least one row.")
        columns_by_name: dict[str, str] = {}
        parsed_units: dict[str, str | None] = {}
        for col in df.columns:
            name, unit = parse_label_unit(col)
            columns_by_name[name] = col
            parsed_units[name] = unit
        current = resolve_file_units(
            {"zvl", "aw"},
            parsed_units=parsed_units,
            units=units,
            allow_partial=True,
        )
        default_current = cls._resolve_current_units(
            units=current if current else units,
            unit_system=unit_system,
        )
        model = cls.from_data(
            zvl=float(df.iloc[0][columns_by_name["zvl"]]),
            aw=float(df.iloc[0][columns_by_name["aw"]]),
            units=default_current,
            unit_system=unit_system,
        )
        return model

    @classmethod
    def from_dict(
        cls,
        data: dict,
        category: DataCategory | None = None,
        *,
        units: Mapping[str, str | None] | None = None,
    ) -> Self:
        """从字典载荷重建 Z 振级评价结果。"""
        del category
        current = resolve_file_units(
            {"zvl", "aw"},
            parsed_units=data.get("_units", {}),
            units=units,
            allow_partial=True,
        )
        default_current = cls._resolve_current_units(units=current if current else units)
        return cls.from_data(
            zvl=float(np.asarray(data.get("zvl", [0.0])).flat[0]),
            aw=float(np.asarray(data.get("aw", [0.0])).flat[0]),
            units=default_current,
        )


class OTOVLEval(DataModelBase):
    """三分之一倍频程振级评价结果。"""

    category: ClassVar[DataCategory] = DataCategory.OTOVL_EVAL
    axis_field: ClassVar[str | None] = "freq"
    value_field: ClassVar[str | None] = "env"

    def __init__(self, dataset: xr.Dataset) -> None:
        self._ds = dataset

    @classmethod
    def _default_current_units(cls, unit_system: UnitSystem | None = None) -> dict[str, str]:
        units = unit_system or get_default_unit_system()
        return {"freq": units.frequency, "comps": units.level, "env": units.level}

    @classmethod
    def _resolve_current_units(
        cls,
        *,
        units: Mapping[str, str | None] | None = None,
        unit_system: UnitSystem | None = None,
    ) -> dict[str, str]:
        current = resolve_current_units(cls._default_current_units(unit_system), units=units)
        current.setdefault("env", current.get("comps", "decibel"))
        return current

    def current_units(self) -> dict[str, str]:
        """返回当前对象对外暴露的单位映射。"""
        return self.base_units()

    def base_units(self) -> dict[str, str]:
        """返回内部数据集记录的基础单位映射。"""
        comps_unit = str(self._ds["comps"].attrs.get("units", "decibel"))
        env_unit = str(self._ds["env"].attrs.get("units", comps_unit)) if "env" in self._ds.data_vars else comps_unit
        return {
            "freq": str(self._ds.coords["freq"].attrs.get("units", "hertz")),
            "comps": comps_unit,
            "env": env_unit,
        }

    @classmethod
    def _from_base_data(
        cls,
        *,
        freq: np.ndarray,
        comps: np.ndarray,
        env: np.ndarray | None = None,
        units: Mapping[str, str | None] | None = None,
        unit_system: UnitSystem | None = None,
    ) -> Self:
        current = cls._resolve_current_units(units=units, unit_system=unit_system)
        comps_arr = np.asarray(comps, dtype=np.float64)
        if comps_arr.ndim == 1 and len(comps_arr) > 0:
            comps_arr = comps_arr.reshape(-1, 1)
        comps_dims = ["freq", "window"] if comps_arr.ndim > 1 and comps_arr.shape[1] > 1 else ["freq"]
        if comps_arr.ndim > 1 and comps_arr.shape[1] == 1:
            comps_arr = comps_arr.squeeze(axis=1)
        data_vars: dict[str, Any] = {
            "comps": (comps_dims, comps_arr, {"units": current["comps"]}),
        }
        if env is not None:
            data_vars["env"] = (
                ["freq"],
                np.asarray(env, dtype=np.float64).flatten(),
                {"units": current["env"]},
            )
        ds = xr.Dataset(
            data_vars,
            coords={
                "freq": (
                    "freq",
                    np.asarray(freq, dtype=np.float64).flatten(),
                    {"units": current["freq"]},
                )
            },
            attrs={_CURRENT_UNITS_ATTR: current},
        )
        return cls(ds)

    @classmethod
    def from_data(
        cls,
        *,
        freq: np.ndarray,
        comps: np.ndarray,
        env: np.ndarray | None = None,
        units: Mapping[str, str | None] | None = None,
        unit_system: UnitSystem | None = None,
    ) -> Self:
        """根据当前单位输入数组构建 OTOVL 结果。"""

        current = cls._resolve_current_units(units=units, unit_system=unit_system)
        env_arr = np.asarray(env, dtype=np.float64).flatten() if env is not None else None
        return cls._from_base_data(
            freq=np.asarray(freq, dtype=np.float64).flatten(),
            comps=np.asarray(comps, dtype=np.float64),
            env=env_arr,
            units=current,
            unit_system=unit_system,
        )

    def get_field(self, name: str, unit: str | None = None) -> np.ndarray:
        """读取指定字段，并按目标单位完成换算。"""
        if name == "freq":
            return convert_array(
                np.asarray(self._ds.coords["freq"].values),
                from_unit=self.base_units()["freq"],
                to_unit=unit or self.base_units()["freq"],
            )
        if name == "env" and "env" not in self._ds.data_vars:
            name = "comps"
        if name not in self._ds.data_vars:
            raise KeyError(f"OTOVLEval does not expose field {name!r}.")
        base_name = "env" if name == "env" else "comps"
        return convert_array(
            np.asarray(self._ds[name].values),
            from_unit=self.base_units()[base_name],
            to_unit=unit or self.base_units()[base_name],
        )

    def convert_units(
        self,
        units: Mapping[str, str | None],
        *,
        replace: bool = True,
    ) -> Self:
        """将 OTOVL 结果转换到目标单位视图。"""
        current = self.current_units().copy()
        current.update(normalize_unit_map(units))
        converted = self.__class__._from_base_data(
            freq=convert_array(
                np.asarray(self._ds.coords["freq"].values),
                from_unit=self.base_units()["freq"],
                to_unit=current["freq"],
            ),
            comps=convert_array(
                np.asarray(self._ds["comps"].values),
                from_unit=self.base_units()["comps"],
                to_unit=current["comps"],
            ),
            env=(
                convert_array(
                    np.asarray(self._ds["env"].values),
                    from_unit=self.base_units()["env"],
                    to_unit=current["env"],
                )
                if "env" in self._ds.data_vars
                else None
            ),
            units=current,
        )
        if replace:
            self._ds = converted._ds
            return self
        return converted

    @property
    def xr(self) -> xr.Dataset:
        """返回按当前单位导出的 ``xarray.Dataset``。"""

        return self._ds

    @property
    def xr_base(self) -> xr.Dataset:
        """返回内部基础单位存储的底层 ``xarray.Dataset``。"""

        return self._ds

    @property
    def freq(self) -> np.ndarray:
        """返回频率轴数组。"""
        return self.get_axis()

    @property
    def comps(self) -> np.ndarray:
        """返回各频带分量结果。"""
        return self.get_field("comps")

    @property
    def env(self) -> np.ndarray:
        """返回各频带包络结果。"""
        return self.get_value()

    def to_pandas(self) -> pd.DataFrame:
        """导出带单位列名和索引名的 DataFrame。"""
        data = {format_label_with_unit("comps", self.current_units()["comps"]): self.get_field("comps").squeeze()}
        if "env" in self._ds.data_vars:
            data[format_label_with_unit("env", self.current_units()["env"])] = self.get_field("env").flatten()
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
        """从 DataFrame 重建 OTOVL 评价结果。"""
        _, freq_unit = parse_label_unit(df.index.name or "freq")
        comps_col = next((col for col in df.columns if parse_label_unit(col)[0] == "comps"), None)
        env_col = next((col for col in df.columns if parse_label_unit(col)[0] == "env"), None)
        _, comps_unit = parse_label_unit(comps_col) if comps_col is not None else ("comps", None)
        _, env_unit = parse_label_unit(env_col) if env_col is not None else ("env", None)
        current = resolve_file_units(
            {"freq", "comps"} | ({"env"} if env_col is not None else set()),
            parsed_units={"freq": freq_unit, "comps": comps_unit, "env": env_unit},
            units=units,
            allow_partial=True,
        )
        default_current = cls._resolve_current_units(
            units=current if current else units,
            unit_system=unit_system,
        )
        return cls.from_data(
            freq=df.index.to_numpy(),
            comps=df[comps_col].to_numpy() if comps_col is not None else np.array([]),
            env=df[env_col].to_numpy() if env_col is not None else None,
            units=default_current,
            unit_system=unit_system,
        )

    def to_dict(self) -> dict[str, Any]:
        """导出便于持久化的字典载荷。"""
        result = {
            "freq": self.get_field("freq"),
            "comps": self.get_field("comps"),
            "_units": self.current_units(),
        }
        if "env" in self._ds.data_vars:
            result["env"] = self.get_field("env")
        return result

    @classmethod
    def from_dict(
        cls,
        data: dict,
        category: DataCategory | None = None,
        *,
        units: Mapping[str, str | None] | None = None,
    ) -> Self:
        """从字典载荷重建 OTOVL 评价结果。"""
        del category
        current = resolve_file_units(
            {"freq", "comps"} | ({"env"} if "env" in data else set()),
            parsed_units=data.get("_units", {}),
            units=units,
            allow_partial=True,
        )
        default_current = cls._resolve_current_units(units=current if current else units)
        return cls.from_data(
            freq=np.asarray(data.get("freq", [])),
            comps=np.asarray(data.get("comps", [])),
            env=np.asarray(data.get("env", [])) if "env" in data else None,
            units=default_current,
        )


class FPVDVEval(DataModelBase):
    """四次方振动剂量值评价结果。"""

    category: ClassVar[DataCategory] = DataCategory.FPVDV_EVAL
    axis_field: ClassVar[str | None] = "aw_time"
    value_field: ClassVar[str | None] = "aw_value"

    def __init__(self, dataset: xr.Dataset) -> None:
        self._ds = dataset

    @classmethod
    def _default_current_units(cls, unit_system: UnitSystem | None = None) -> dict[str, str]:
        units = unit_system or get_default_unit_system()
        return {
            "fpvdv": units.vibration_dose_value,
            "aw_time": units.time,
            "aw_value": units.weighted_acceleration,
        }

    @classmethod
    def _resolve_current_units(
        cls,
        *,
        units: Mapping[str, str | None] | None = None,
        unit_system: UnitSystem | None = None,
    ) -> dict[str, str]:
        return resolve_current_units(cls._default_current_units(unit_system), units=units)

    def current_units(self) -> dict[str, str]:
        """返回当前对象对外暴露的单位映射。"""
        return self.base_units()

    def base_units(self) -> dict[str, str]:
        """返回内部数据集记录的基础单位映射。"""
        return {
            "fpvdv": str(self._ds["fpvdv"].attrs.get("units", "m_per_s_1p75")),
            "aw_time": str(self._ds["aw_time"].attrs.get("units", "second")),
            "aw_value": str(self._ds["aw_value"].attrs.get("units", "meter/second**2")),
        }

    @classmethod
    def _from_base_data(
        cls,
        *,
        fpvdv: float,
        aw_time: np.ndarray,
        aw_value: np.ndarray,
        units: Mapping[str, str | None] | None = None,
        unit_system: UnitSystem | None = None,
    ) -> Self:
        current = cls._resolve_current_units(units=units, unit_system=unit_system)
        aw_value_arr = np.asarray(aw_value, dtype=np.float64)
        if aw_value_arr.ndim == 1 and len(aw_value_arr) > 0:
            aw_value_arr = aw_value_arr.reshape(-1, 1)
        dims = ["n", "channel"] if aw_value_arr.ndim > 1 and aw_value_arr.shape[1] > 1 else ["n"]
        if aw_value_arr.ndim > 1 and aw_value_arr.shape[1] == 1:
            aw_value_arr = aw_value_arr.squeeze(axis=1)
        ds = xr.Dataset(
            {
                "fpvdv": ((), float(fpvdv), {"units": current["fpvdv"]}),
                "aw_time": (
                    ["n"],
                    np.asarray(aw_time, dtype=np.float64).flatten(),
                    {"units": current["aw_time"]},
                ),
                "aw_value": (dims, aw_value_arr, {"units": current["aw_value"]}),
            },
            coords={"n": np.arange(max(len(aw_time), len(np.asarray(aw_value).reshape(-1))))},
            attrs={_CURRENT_UNITS_ATTR: current},
        )
        return cls(ds)

    @classmethod
    def from_data(
        cls,
        *,
        fpvdv: float,
        aw_time: np.ndarray,
        aw_value: np.ndarray,
        units: Mapping[str, str | None] | None = None,
        unit_system: UnitSystem | None = None,
    ) -> Self:
        """根据当前单位输入数据构建 FPVDV 结果。"""

        current = cls._resolve_current_units(units=units, unit_system=unit_system)
        return cls._from_base_data(
            fpvdv=float(fpvdv),
            aw_time=np.asarray(aw_time, dtype=np.float64).flatten(),
            aw_value=np.asarray(aw_value, dtype=np.float64),
            units=current,
            unit_system=unit_system,
        )

    def get_field(self, name: str, unit: str | None = None) -> np.ndarray:
        """读取指定字段，并按目标单位完成换算。"""
        if name not in self._ds:
            raise KeyError(f"FPVDVEval does not expose field {name!r}.")
        return convert_array(
            np.asarray(self._ds[name].values),
            from_unit=self.base_units()[name],
            to_unit=unit or self.base_units()[name],
        )

    def convert_units(
        self,
        units: Mapping[str, str | None],
        *,
        replace: bool = True,
    ) -> Self:
        """将 FPVDV 结果转换到目标单位视图。"""
        current = self.current_units().copy()
        current.update(normalize_unit_map(units))
        converted = self.__class__._from_base_data(
            fpvdv=float(
                convert_array(
                    np.asarray(self._ds["fpvdv"].values),
                    from_unit=self.base_units()["fpvdv"],
                    to_unit=current["fpvdv"],
                ).flat[0]
            ),
            aw_time=convert_array(
                np.asarray(self._ds["aw_time"].values),
                from_unit=self.base_units()["aw_time"],
                to_unit=current["aw_time"],
            ),
            aw_value=convert_array(
                np.asarray(self._ds["aw_value"].values),
                from_unit=self.base_units()["aw_value"],
                to_unit=current["aw_value"],
            ),
            units=current,
        )
        if replace:
            self._ds = converted._ds
            return self
        return converted

    @property
    def fpvdv(self) -> np.ndarray:
        """返回四次方振动剂量值标量结果。"""
        return self.get_field("fpvdv")

    def to_pandas(self) -> pd.DataFrame:
        """将评价结果转换为 DataFrame。"""

        return pd.DataFrame(
            {
                format_label_with_unit("aw_value", self.current_units()["aw_value"]): np.asarray(
                    self.get_field("aw_value")
                ).squeeze(),
                format_label_with_unit("fpvdv", self.current_units()["fpvdv"]): np.repeat(
                    float(self.fpvdv.flat[0]),
                    len(self.get_field("aw_time")),
                ),
            },
            index=pd.Index(
                self.get_field("aw_time"),
                name=format_label_with_unit("aw_time", self.current_units()["aw_time"]),
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        """导出便于持久化的字典载荷。"""
        return {
            "fpvdv": self.get_field("fpvdv"),
            "aw_time": self.get_field("aw_time"),
            "aw_value": self.get_field("aw_value"),
            "_units": self.current_units(),
        }

    @classmethod
    def from_dict(
        cls,
        data: dict,
        category: DataCategory | None = None,
        *,
        units: Mapping[str, str | None] | None = None,
    ) -> Self:
        """从字典载荷重建 FPVDV 评价结果。"""
        del category
        current = resolve_file_units(
            {"fpvdv", "aw_time", "aw_value"},
            parsed_units=data.get("_units", {}),
            units=units,
            allow_partial=True,
        )
        default_current = cls._resolve_current_units(units=current if current else units)
        return cls.from_data(
            fpvdv=float(np.asarray(data.get("fpvdv", [0.0])).flat[0]),
            aw_time=np.asarray(data.get("aw_time", [])),
            aw_value=np.asarray(data.get("aw_value", [])),
            units=default_current,
        )

    @classmethod
    def from_pandas(
        cls,
        df: pd.DataFrame,
        *,
        units: Mapping[str, str | None] | None = None,
        unit_system: UnitSystem | None = None,
    ) -> Self:
        """从 DataFrame 构建 FPVDV 结果。"""

        _, aw_time_unit = parse_label_unit(df.index.name or "aw_time")
        columns_by_name: dict[str, str] = {}
        parsed_units: dict[str, str | None] = {"aw_time": aw_time_unit}
        for col in df.columns:
            name, unit = parse_label_unit(col)
            columns_by_name[name] = col
            parsed_units[name] = unit
        current = resolve_file_units(
            {"fpvdv", "aw_time", "aw_value"},
            parsed_units=parsed_units,
            units=units,
            allow_partial=True,
        )
        default_current = cls._resolve_current_units(
            units=current if current else units,
            unit_system=unit_system,
        )
        model = cls.from_data(
            fpvdv=float(df[columns_by_name["fpvdv"]].iloc[0]),
            aw_time=df.index.to_numpy(),
            aw_value=df[columns_by_name["aw_value"]].to_numpy(),
            units=default_current,
            unit_system=unit_system,
        )
        return model


class FDMVLEval(DataModelBase):
    """分频最大振级评价结果。"""

    category: ClassVar[DataCategory] = DataCategory.FDMVL_EVAL
    axis_field: ClassVar[str | None] = "freq"
    value_field: ClassVar[str | None] = "fdvls"

    def __init__(self, dataset: xr.Dataset) -> None:
        self._ds = dataset

    @classmethod
    def _default_current_units(cls, unit_system: UnitSystem | None = None) -> dict[str, str]:
        units = unit_system or get_default_unit_system()
        return {"fdmvl": units.level, "freq": units.frequency, "fdvls": units.level}

    @classmethod
    def _resolve_current_units(
        cls,
        *,
        units: Mapping[str, str | None] | None = None,
        unit_system: UnitSystem | None = None,
    ) -> dict[str, str]:
        return resolve_current_units(cls._default_current_units(unit_system), units=units)

    def current_units(self) -> dict[str, str]:
        """返回当前对象对外暴露的单位映射。"""
        return self.base_units()

    def base_units(self) -> dict[str, str]:
        """返回内部数据集记录的基础单位映射。"""
        return {
            "fdmvl": str(self._ds["fdmvl"].attrs.get("units", "decibel")),
            "freq": str(self._ds.coords["freq"].attrs.get("units", "hertz")),
            "fdvls": str(self._ds["fdvls"].attrs.get("units", "decibel")),
        }

    @classmethod
    def _from_base_data(
        cls,
        *,
        fdmvl: float,
        freq: np.ndarray,
        fdvls: np.ndarray,
        units: Mapping[str, str | None] | None = None,
        unit_system: UnitSystem | None = None,
    ) -> Self:
        current = cls._resolve_current_units(units=units, unit_system=unit_system)
        fdvls_arr = np.asarray(fdvls, dtype=np.float64)
        if fdvls_arr.ndim == 1 and len(fdvls_arr) > 0:
            fdvls_arr = fdvls_arr.reshape(-1, 1)
        dims = ["freq", "channel"] if fdvls_arr.ndim > 1 and fdvls_arr.shape[1] > 1 else ["freq"]
        if fdvls_arr.ndim > 1 and fdvls_arr.shape[1] == 1:
            fdvls_arr = fdvls_arr.squeeze(axis=1)
        ds = xr.Dataset(
            {
                "fdmvl": ((), float(fdmvl), {"units": current["fdmvl"]}),
                "fdvls": (dims, fdvls_arr, {"units": current["fdvls"]}),
            },
            coords={
                "freq": (
                    "freq",
                    np.asarray(freq, dtype=np.float64).flatten(),
                    {"units": current["freq"]},
                )
            },
            attrs={_CURRENT_UNITS_ATTR: current},
        )
        return cls(ds)

    @classmethod
    def from_data(
        cls,
        *,
        fdmvl: float,
        freq: np.ndarray,
        fdvls: np.ndarray,
        units: Mapping[str, str | None] | None = None,
        unit_system: UnitSystem | None = None,
    ) -> Self:
        """根据当前单位输入数据构建 FDMVL 结果。"""

        current = cls._resolve_current_units(units=units, unit_system=unit_system)
        return cls._from_base_data(
            fdmvl=float(fdmvl),
            freq=np.asarray(freq, dtype=np.float64).flatten(),
            fdvls=np.asarray(fdvls, dtype=np.float64),
            units=current,
            unit_system=unit_system,
        )

    def get_field(self, name: str, unit: str | None = None) -> np.ndarray:
        """读取指定字段，并按目标单位完成换算。"""
        if name == "freq":
            return convert_array(
                np.asarray(self._ds.coords["freq"].values),
                from_unit=self.base_units()["freq"],
                to_unit=unit or self.base_units()["freq"],
            )
        if name not in self._ds:
            raise KeyError(f"FDMVLEval does not expose field {name!r}.")
        return convert_array(
            np.asarray(self._ds[name].values),
            from_unit=self.base_units()[name],
            to_unit=unit or self.base_units()[name],
        )

    def convert_units(
        self,
        units: Mapping[str, str | None],
        *,
        replace: bool = True,
    ) -> Self:
        """将 FDMVL 结果转换到目标单位视图。"""
        current = self.current_units().copy()
        current.update(normalize_unit_map(units))
        converted = self.__class__._from_base_data(
            fdmvl=float(
                convert_array(
                    np.asarray(self._ds["fdmvl"].values),
                    from_unit=self.base_units()["fdmvl"],
                    to_unit=current["fdmvl"],
                ).flat[0]
            ),
            freq=convert_array(
                np.asarray(self._ds.coords["freq"].values),
                from_unit=self.base_units()["freq"],
                to_unit=current["freq"],
            ),
            fdvls=convert_array(
                np.asarray(self._ds["fdvls"].values),
                from_unit=self.base_units()["fdvls"],
                to_unit=current["fdvls"],
            ),
            units=current,
        )
        if replace:
            self._ds = converted._ds
            return self
        return converted

    @property
    def fdmvl(self) -> np.ndarray:
        """返回分频最大振级标量结果。"""
        return self.get_field("fdmvl")

    def to_pandas(self) -> pd.DataFrame:
        """将评价结果转换为 DataFrame。"""

        return pd.DataFrame(
            {
                format_label_with_unit("fdvls", self.current_units()["fdvls"]): np.asarray(
                    self.get_field("fdvls")
                ).squeeze(),
                format_label_with_unit("fdmvl", self.current_units()["fdmvl"]): np.repeat(
                    float(self.fdmvl.flat[0]),
                    len(self.get_field("freq")),
                ),
            },
            index=pd.Index(
                self.get_field("freq"),
                name=format_label_with_unit("freq", self.current_units()["freq"]),
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        """导出便于持久化的字典载荷。"""
        return {
            "fdmvl": self.get_field("fdmvl"),
            "freq": self.get_field("freq"),
            "fdvls": self.get_field("fdvls"),
            "_units": self.current_units(),
        }

    @classmethod
    def from_dict(
        cls,
        data: dict,
        category: DataCategory | None = None,
        *,
        units: Mapping[str, str | None] | None = None,
    ) -> Self:
        """从字典载荷重建 FDMVL 评价结果。"""
        del category
        current = resolve_file_units(
            {"fdmvl", "freq", "fdvls"},
            parsed_units=data.get("_units", {}),
            units=units,
            allow_partial=True,
        )
        default_current = cls._resolve_current_units(units=current if current else units)
        return cls.from_data(
            fdmvl=float(np.asarray(data.get("fdmvl", [0.0])).flat[0]),
            freq=np.asarray(data.get("freq", [])),
            fdvls=np.asarray(data.get("fdvls", [])),
            units=default_current,
        )

    @classmethod
    def from_pandas(
        cls,
        df: pd.DataFrame,
        *,
        units: Mapping[str, str | None] | None = None,
        unit_system: UnitSystem | None = None,
    ) -> Self:
        """从 DataFrame 构建 FDMVL 结果。"""

        _, freq_unit = parse_label_unit(df.index.name or "freq")
        columns_by_name: dict[str, str] = {}
        parsed_units: dict[str, str | None] = {"freq": freq_unit}
        for col in df.columns:
            name, unit = parse_label_unit(col)
            columns_by_name[name] = col
            parsed_units[name] = unit
        current = resolve_file_units(
            {"fdmvl", "freq", "fdvls"},
            parsed_units=parsed_units,
            units=units,
            allow_partial=True,
        )
        default_current = cls._resolve_current_units(
            units=current if current else units,
            unit_system=unit_system,
        )
        model = cls.from_data(
            fdmvl=float(df[columns_by_name["fdmvl"]].iloc[0]),
            freq=df.index.to_numpy(),
            fdvls=df[columns_by_name["fdvls"]].to_numpy(),
            units=default_current,
            unit_system=unit_system,
        )
        return model
