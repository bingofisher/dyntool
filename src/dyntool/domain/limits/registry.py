"""规范驱动限值注册表。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from functools import lru_cache
from typing import Callable

import numpy as np
import pandas as pd

from ...compute.solver_support import load_resource_csv
from ..constants import normalize_unit, parse_label_unit
from .enums import FPVDVLimitStandard, OTOVLLimitStandard, ZVLLimitStandard


@dataclass(frozen=True, slots=True)
class LimitResolvedPayload:
    """单个规范场景解析后的限值载荷。"""

    clause: str
    resource_key: str
    scene: str
    fields: dict[str, np.ndarray]
    units: dict[str, str]


@dataclass(frozen=True, slots=True)
class LimitStandardSpec:
    """单个标准条目注册描述。"""

    standard: StrEnum
    clause: str
    resource_key: str
    list_scenes: Callable[[pd.DataFrame], tuple[str, ...]]
    resolve_scene: Callable[[pd.DataFrame, str], LimitResolvedPayload]


@lru_cache(maxsize=None)
def _load_standard_csv(resource_key: str) -> pd.DataFrame:
    """缓存读取标准资源表。"""

    return load_resource_csv(resource_key)


def _get_standard_csv(resource_key: str) -> pd.DataFrame:
    """返回标准资源表副本，避免原地修改缓存对象。"""

    return _load_standard_csv(resource_key).copy()


def _normalize_unit_label(unit: str | None, fallback: str) -> str:
    """将 CSV 中的单位标签规范化为可转换单位。"""

    return normalize_unit(unit) or unit or fallback


def _list_scalar_scenes(df: pd.DataFrame) -> tuple[str, ...]:
    """从标量限值表读取场景名称。"""

    return tuple(str(item) for item in df["区域类别"].tolist())


def _resolve_scalar_scene(
    df: pd.DataFrame, scene: str, *, value_field: str, fallback_unit: str
) -> LimitResolvedPayload:
    """从标量限值表解析单个场景。"""

    rows = df.loc[df["区域类别"].astype(str) == scene]
    if rows.empty:
        raise ValueError(f"未找到场景：{scene}")
    value_column = str(df.columns[1])
    _, unit = parse_label_unit(value_column)
    value = float(rows.iloc[0][value_column])
    return LimitResolvedPayload(
        clause="",
        resource_key="",
        scene=scene,
        fields={value_field: np.asarray(value, dtype=np.float64)},
        units={value_field: _normalize_unit_label(unit, fallback_unit)},
    )


def _strip_scene_name(column_label: str) -> str:
    """将带“限值”后缀的列名转换为公开场景名。"""

    name, _ = parse_label_unit(column_label)
    return name.removesuffix("限值").strip()


def _list_curve_scenes(df: pd.DataFrame) -> tuple[str, ...]:
    """从曲线限值表读取场景名称。"""

    return tuple(_strip_scene_name(str(col)) for col in df.columns[1:])


def _resolve_curve_scene(
    df: pd.DataFrame,
    scene: str,
    *,
    axis_field: str,
    value_field: str,
    axis_fallback_unit: str,
    value_fallback_unit: str,
) -> LimitResolvedPayload:
    """从曲线限值表解析单个场景。"""

    scene_columns = {_strip_scene_name(str(col)): str(col) for col in df.columns[1:]}
    if scene not in scene_columns:
        raise ValueError(f"未找到场景：{scene}")
    axis_column = str(df.columns[0])
    value_column = scene_columns[scene]
    _, axis_unit = parse_label_unit(axis_column)
    _, value_unit = parse_label_unit(value_column)
    return LimitResolvedPayload(
        clause="",
        resource_key="",
        scene=scene,
        fields={
            axis_field: df[axis_column].to_numpy(dtype=np.float64),
            value_field: df[value_column].to_numpy(dtype=np.float64),
        },
        units={
            axis_field: _normalize_unit_label(axis_unit, axis_fallback_unit),
            value_field: _normalize_unit_label(value_unit, value_fallback_unit),
        },
    )


_LIMIT_STANDARD_REGISTRY: dict[str, dict[StrEnum, LimitStandardSpec]] = {
    "zvl": {
        ZVLLimitStandard.GB_10070_1988: LimitStandardSpec(
            standard=ZVLLimitStandard.GB_10070_1988,
            clause="3.1.1",
            resource_key="limit_city_zvl",
            list_scenes=_list_scalar_scenes,
            resolve_scene=lambda df, scene: _resolve_scalar_scene(
                df,
                scene,
                value_field="zvl",
                fallback_unit="decibel",
            ),
        ),
        ZVLLimitStandard.GB_T_50355_2018: LimitStandardSpec(
            standard=ZVLLimitStandard.GB_T_50355_2018,
            clause="3.0.1",
            resource_key="limit_residential_zvl",
            list_scenes=_list_scalar_scenes,
            resolve_scene=lambda df, scene: _resolve_scalar_scene(
                df,
                scene,
                value_field="zvl",
                fallback_unit="decibel",
            ),
        ),
    },
    "otovl": {
        OTOVLLimitStandard.GB_T_50355_2018: LimitStandardSpec(
            standard=OTOVLLimitStandard.GB_T_50355_2018,
            clause="3.0.2",
            resource_key="limit_residential_otovl",
            list_scenes=_list_curve_scenes,
            resolve_scene=lambda df, scene: _resolve_curve_scene(
                df,
                scene,
                axis_field="freq",
                value_field="otovl",
                axis_fallback_unit="hertz",
                value_fallback_unit="decibel",
            ),
        ),
    },
    "fpvdv": {
        FPVDVLimitStandard.GB_50868_2013: LimitStandardSpec(
            standard=FPVDVLimitStandard.GB_50868_2013,
            clause="7.2.3",
            resource_key="limit_transport_fpvdv",
            list_scenes=_list_scalar_scenes,
            resolve_scene=lambda df, scene: _resolve_scalar_scene(
                df,
                scene,
                value_field="fpvdv",
                fallback_unit="meter/second**1.75",
            ),
        ),
    },
    "fdmvl": {},
}


def get_supported_standards(family: str) -> tuple[StrEnum, ...]:
    """返回指定评价族已注册标准。"""

    return tuple(_LIMIT_STANDARD_REGISTRY.get(family, {}).keys())


def get_supported_scenes(family: str, standard: StrEnum) -> tuple[str, ...]:
    """返回指定标准下可用的场景名称。"""

    spec = _LIMIT_STANDARD_REGISTRY[family][standard]
    return spec.list_scenes(_get_standard_csv(spec.resource_key))


def resolve_limit_payload(family: str, standard: StrEnum, scene: str) -> LimitResolvedPayload:
    """解析指定标准与场景的限值数据。"""

    spec = _LIMIT_STANDARD_REGISTRY[family][standard]
    payload = spec.resolve_scene(_get_standard_csv(spec.resource_key), scene)
    return LimitResolvedPayload(
        clause=spec.clause,
        resource_key=spec.resource_key,
        scene=payload.scene,
        fields=payload.fields,
        units=payload.units,
    )


__all__ = [
    "LimitResolvedPayload",
    "LimitStandardSpec",
    "get_supported_scenes",
    "get_supported_standards",
    "resolve_limit_payload",
]
