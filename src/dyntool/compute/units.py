"""单位换算与规范化工具。"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any, Mapping

import numpy as np
import pint

_HEADER_UNIT_PATTERN = re.compile(r"^(?P<name>[^\[\(]+?)\s*(?:\[(?P<bracket>[^\]]+)\]|\((?P<paren>[^\)]+)\))?\s*$")


@dataclass(slots=True)
class UnitSystem:
    """常用单位制定义。"""

    time: str = "second"
    frequency: str = "hertz"
    period: str = "second"
    acceleration: str = "meter/second**2"
    velocity: str = "meter/second"
    displacement: str = "meter"
    force: str = "newton"
    spectrum_amplitude: str = "dimensionless"
    phase: str = "radian"
    level: str = "decibel"
    weighted_acceleration: str = "meter/second**2"
    vibration_dose_value: str = "m_per_s_1p75"

    @classmethod
    def si(cls) -> UnitSystem:
        """返回 SI 单位制。"""

        return cls()

    @classmethod
    def engineering(cls) -> UnitSystem:
        """返回常用工程单位制。"""

        return cls(
            acceleration="g_force",
            velocity="centimeter/second",
            displacement="centimeter",
            weighted_acceleration="g_force",
            vibration_dose_value="mm_per_s_1p75",
        )

    def to_dict(self) -> dict[str, str]:
        """导出为字段到单位的映射。"""

        return dict(asdict(self))


def _build_unit_registry() -> pint.UnitRegistry:
    registry = pint.UnitRegistry()
    registry.define("m_per_s_1p75 = meter / second ** 1.75 = m/s^1.75")
    registry.define("mm_per_s_1p75 = millimeter / second ** 1.75 = mm/s^1.75")
    registry.define("g_force = 9.80665 meter / second ** 2")
    registry.define("decibel = [] = dB")
    return registry


ureg = _build_unit_registry()
_DEFAULT_UNIT_SYSTEM = UnitSystem.si()

_CANONICAL_UNIT_CANDIDATES = tuple(UnitSystem.si().to_dict().values()) + tuple(
    UnitSystem.engineering().to_dict().values()
)


def get_unit_registry() -> pint.UnitRegistry:
    """返回共享的 pint 单位注册表。"""

    return ureg


def get_default_unit_system() -> UnitSystem:
    """返回全局默认单位制。"""

    return _DEFAULT_UNIT_SYSTEM


def set_default_unit_system(unit_system: UnitSystem) -> None:
    """设置全局默认单位制。"""

    global _DEFAULT_UNIT_SYSTEM
    _DEFAULT_UNIT_SYSTEM = unit_system


def normalize_unit(unit: str | pint.Unit | None) -> str | None:
    """将单位输入规范化为字符串。"""

    if unit is None:
        return None
    if isinstance(unit, str):
        stripped = unit.strip()
        if not stripped:
            return None
        return str(ureg.Unit(stripped))
    return str(ureg.Unit(unit))


def canonicalize_unit(
    unit: str | pint.Unit | None,
    *,
    fallback: str | pint.Unit | None = None,
) -> str | None:
    """按维度映射到候选中的规范单位。"""

    resolved = normalize_unit(unit)
    if resolved is None:
        return normalize_unit(fallback)
    resolved_dim = ureg.Unit(resolved).dimensionality
    for candidate in _CANONICAL_UNIT_CANDIDATES:
        if ureg.Unit(candidate).dimensionality == resolved_dim:
            return candidate
    return resolved


def normalize_unit_map(
    units: Mapping[str, str | pint.Unit | None] | None,
) -> dict[str, str]:
    """规范化字段级单位映射。"""

    if units is None:
        return {}
    normalized: dict[str, str] = {}
    for key, value in units.items():
        resolved = normalize_unit(value)
        if resolved is not None:
            normalized[str(key)] = resolved
    return normalized


def ensure_ndarray(data: Any, *, dtype: Any = np.float64) -> np.ndarray:
    """将输入转换为 `numpy.ndarray`。"""

    if isinstance(data, np.ndarray):
        return data.astype(dtype, copy=False) if dtype is not None else data
    if hasattr(data, "magnitude"):
        magnitude = np.asarray(getattr(data, "magnitude"))
        return magnitude.astype(dtype, copy=False) if dtype is not None else magnitude
    array = np.asarray(data)
    return array.astype(dtype, copy=False) if dtype is not None else array


def infer_input_unit(
    data: Any,
    *,
    explicit_unit: str | pint.Unit | None = None,
    default_unit: str | pint.Unit | None = None,
) -> str | None:
    """推断输入数据当前使用的单位。"""

    if explicit_unit is not None:
        return normalize_unit(explicit_unit)
    if hasattr(data, "units"):
        return normalize_unit(getattr(data, "units"))
    return normalize_unit(default_unit)


def convert_array(
    values: Any,
    *,
    from_unit: str | pint.Unit | None,
    to_unit: str | pint.Unit | None,
    dtype: Any = np.float64,
) -> np.ndarray:
    """按单位转换数组。"""

    array = ensure_ndarray(values, dtype=dtype)
    source = normalize_unit(from_unit)
    target = normalize_unit(to_unit)
    if source is None or target is None or source == target:
        return array
    quantity = array * ureg.Unit(source)
    converted = quantity.to(ureg.Unit(target)).magnitude
    return np.asarray(converted, dtype=dtype)


def convert_to_base_unit(
    data: Any,
    *,
    current_unit: str | pint.Unit | None,
    base_unit: str | pint.Unit | None,
    default_current_unit: str | pint.Unit | None = None,
    dtype: Any = np.float64,
) -> tuple[np.ndarray, str | None]:
    """转换到基准单位，并返回原始单位。"""

    resolved_current = infer_input_unit(
        data,
        explicit_unit=current_unit,
        default_unit=default_current_unit or base_unit,
    ) or normalize_unit(base_unit)
    resolved_base = normalize_unit(base_unit)
    if resolved_base is None:
        raise ValueError("base_unit 必须能解析为具体单位")
    return (
        convert_array(
            data,
            from_unit=resolved_current,
            to_unit=resolved_base,
            dtype=dtype,
        ),
        resolved_current,
    )


def coerce_array_with_unit(
    data: Any,
    *,
    current_unit: str | pint.Unit | None,
    default_current_unit: str | pint.Unit | None = None,
    dtype: Any = np.float64,
) -> tuple[np.ndarray, str | None]:
    """返回数组和解析后的当前单位。"""

    resolved_current = infer_input_unit(
        data,
        explicit_unit=current_unit,
        default_unit=default_current_unit,
    )
    return ensure_ndarray(data, dtype=dtype), resolved_current


def parse_label_unit(label: str) -> tuple[str, str | None]:
    """解析 `name [unit]` 或 `name(unit)` 标签。"""

    raw = str(label).strip()
    if not raw:
        return "", None
    match = _HEADER_UNIT_PATTERN.match(raw)
    if not match:
        return raw, None
    name = match.group("name").strip()
    unit = match.group("bracket") or match.group("paren")
    return name, normalize_unit(unit) if unit else None


def format_label_with_unit(name: str, unit: str | pint.Unit | None) -> str:
    """将字段名格式化为带单位的列名。"""

    resolved = normalize_unit(unit)
    return f"{name} [{resolved}]" if resolved else name


def build_unit_overrides(
    defaults: Mapping[str, str | pint.Unit | None] | None,
    units: Mapping[str, str | pint.Unit | None] | None,
) -> dict[str, str]:
    """合并默认单位和显式覆盖。"""

    resolved = normalize_unit_map(defaults)
    resolved.update(normalize_unit_map(units))
    return resolved


def resolve_current_units(
    defaults: Mapping[str, str | pint.Unit | None] | None,
    *,
    units: Mapping[str, str | pint.Unit | None] | None = None,
) -> dict[str, str]:
    """解析当前视图单位。"""

    return build_unit_overrides(defaults, units)


def resolve_file_units(
    required_fields: set[str] | list[str] | tuple[str, ...],
    *,
    parsed_units: Mapping[str, str | pint.Unit | None] | None = None,
    units: Mapping[str, str | pint.Unit | None] | None = None,
    allow_partial: bool = False,
) -> dict[str, str]:
    """从文件标签和显式参数中解析字段单位。"""

    resolved = normalize_unit_map(parsed_units)
    explicit = normalize_unit_map(units)
    explicit.update(resolved)
    missing = [field for field in required_fields if field not in explicit]
    if missing and not allow_partial:
        joined = ", ".join(sorted(missing))
        raise ValueError(f"缺少字段单位信息: {joined}")
    return explicit


__all__ = [
    "UnitSystem",
    "build_unit_overrides",
    "canonicalize_unit",
    "coerce_array_with_unit",
    "convert_array",
    "convert_to_base_unit",
    "ensure_ndarray",
    "format_label_with_unit",
    "get_default_unit_system",
    "get_unit_registry",
    "infer_input_unit",
    "normalize_unit",
    "normalize_unit_map",
    "parse_label_unit",
    "resolve_current_units",
    "resolve_file_units",
    "set_default_unit_system",
    "ureg",
]
