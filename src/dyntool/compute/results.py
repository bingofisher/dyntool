"""计算层纯结果对象。"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .units import UnitSystem


@dataclass(slots=True, frozen=True)
class ZVLComputeResult:
    """Z 振级纯结果。"""

    zvl: float
    aw: float
    units: dict[str, str]
    unit_system: UnitSystem


@dataclass(slots=True, frozen=True)
class OTOVLComputeResult:
    """1/3 倍频程振级纯结果。"""

    freq: np.ndarray
    comps: np.ndarray
    env: np.ndarray
    units: dict[str, str]
    unit_system: UnitSystem


@dataclass(slots=True, frozen=True)
class FDMVLComputeResult:
    """分频最大振级纯结果。"""

    fdmvl: float
    freq: np.ndarray
    fdvls: np.ndarray
    units: dict[str, str]
    unit_system: UnitSystem


@dataclass(slots=True, frozen=True)
class FPVDVComputeResult:
    """四次方振动剂量值纯结果。"""

    fpvdv: float
    aw_time: np.ndarray
    aw_value: np.ndarray
    units: dict[str, str]
    unit_system: UnitSystem
