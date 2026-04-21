"""plotting 正式轴语义配置。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


class _AxisConfigParser:
    """收拢 axis schema 解析与类型归一化。"""

    def optional_float_tuple(self, values: object, *, path: str) -> tuple[float, ...] | None:
        if values is None:
            return None
        if not isinstance(values, list | tuple) or len(values) == 0:
            raise ValueError(f"{path} 必须为非空数字序列。")
        normalized: list[float] = []
        for item in values:
            if isinstance(item, bool) or not isinstance(item, int | float):
                raise ValueError(f"{path} 必须为非空数字序列。")
            normalized.append(float(item))
        return tuple(normalized)

    def optional_string_tuple(self, values: object, *, path: str) -> tuple[str, ...] | None:
        if values is None:
            return None
        if not isinstance(values, list | tuple) or len(values) == 0:
            raise ValueError(f"{path} 必须为非空字符串序列。")
        normalized: list[str] = []
        for item in values:
            if not isinstance(item, str):
                raise ValueError(f"{path} 必须为非空字符串序列。")
            normalized.append(item)
        return tuple(normalized)

    def optional_float(self, value: object, *, path: str) -> float | None:
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise ValueError(f"{path} 必须为数字。")
        return float(value)

    def optional_int(self, value: object, *, path: str) -> int | None:
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise ValueError(f"{path} 必须为整数。")
        return int(value)

    def optional_bool(self, value: object, *, path: str) -> bool | None:
        if value is None:
            return None
        if not isinstance(value, bool):
            raise ValueError(f"{path} 必须为布尔值。")
        return value

    def raise_unknown_keys(self, *, path: str, payload: Mapping[str, Any], allowed: set[str]) -> None:
        unknown = {str(key) for key in payload.keys() if str(key) not in allowed}
        if unknown:
            raise ValueError(f"{path} 存在未支持的字段: {'、'.join(sorted(unknown))}")

    def mapping_or_empty(self, value: object, *, path: str) -> Mapping[str, Any]:
        if value is None:
            return {}
        if not isinstance(value, Mapping):
            raise ValueError(f"{path} 必须为映射。")
        return value


_AXIS_CONFIG_PARSER = _AxisConfigParser()


@dataclass(slots=True)
class ContinuousAxisSpec:
    """连续数值轴配置。"""

    ticks: tuple[float, ...] | None = None
    major_step: float | None = None
    major_origin: float = 0.0
    num_segments: int | None = None
    tick_min: float | None = None
    tick_max: float | None = None
    minor_step: float | None = None
    minor_origin: float = 0.0
    baseline: float | None = None
    height_ratio: float | None = None
    decimals: int | None = None
    trim_trailing_zeros: bool = True
    scientific: bool | None = None
    scientific_fontsize: float | None = None
    scientific_exponent: int | None = None
    scientific_offset_x: float | None = None
    scientific_offset_y: float | None = None

    def __post_init__(self) -> None:
        self.ticks = _AXIS_CONFIG_PARSER.optional_float_tuple(self.ticks, path="ContinuousAxisSpec.ticks")
        self.major_step = _AXIS_CONFIG_PARSER.optional_float(self.major_step, path="ContinuousAxisSpec.major_step")
        if self.major_step is not None and self.major_step <= 0.0:
            raise ValueError("ContinuousAxisSpec.major_step 必须大于 0。")
        self.major_origin = _AXIS_CONFIG_PARSER.optional_float(
            self.major_origin,
            path="ContinuousAxisSpec.major_origin",
        )
        if self.major_origin is None:
            self.major_origin = 0.0
        self.num_segments = _AXIS_CONFIG_PARSER.optional_int(self.num_segments, path="ContinuousAxisSpec.num_segments")
        if self.num_segments is not None and self.num_segments <= 0:
            raise ValueError("ContinuousAxisSpec.num_segments 必须大于 0。")
        self.tick_min = _AXIS_CONFIG_PARSER.optional_float(self.tick_min, path="ContinuousAxisSpec.tick_min")
        self.tick_max = _AXIS_CONFIG_PARSER.optional_float(self.tick_max, path="ContinuousAxisSpec.tick_max")
        self.minor_step = _AXIS_CONFIG_PARSER.optional_float(self.minor_step, path="ContinuousAxisSpec.minor_step")
        if self.minor_step is not None and self.minor_step <= 0.0:
            raise ValueError("ContinuousAxisSpec.minor_step 必须大于 0。")
        self.minor_origin = _AXIS_CONFIG_PARSER.optional_float(
            self.minor_origin,
            path="ContinuousAxisSpec.minor_origin",
        )
        if self.minor_origin is None:
            self.minor_origin = 0.0
        self.baseline = _AXIS_CONFIG_PARSER.optional_float(self.baseline, path="ContinuousAxisSpec.baseline")
        self.height_ratio = _AXIS_CONFIG_PARSER.optional_float(
            self.height_ratio,
            path="ContinuousAxisSpec.height_ratio",
        )
        self.decimals = _AXIS_CONFIG_PARSER.optional_int(self.decimals, path="ContinuousAxisSpec.decimals")
        if self.decimals is not None and self.decimals < 0:
            raise ValueError("ContinuousAxisSpec.decimals 不能小于 0。")
        if not isinstance(self.trim_trailing_zeros, bool):
            raise ValueError("ContinuousAxisSpec.trim_trailing_zeros 必须为布尔值。")
        self.scientific = _AXIS_CONFIG_PARSER.optional_bool(self.scientific, path="ContinuousAxisSpec.scientific")
        self.scientific_fontsize = _AXIS_CONFIG_PARSER.optional_float(
            self.scientific_fontsize,
            path="ContinuousAxisSpec.scientific_fontsize",
        )
        self.scientific_exponent = _AXIS_CONFIG_PARSER.optional_int(
            self.scientific_exponent,
            path="ContinuousAxisSpec.scientific_exponent",
        )
        self.scientific_offset_x = _AXIS_CONFIG_PARSER.optional_float(
            self.scientific_offset_x,
            path="ContinuousAxisSpec.scientific_offset_x",
        )
        self.scientific_offset_y = _AXIS_CONFIG_PARSER.optional_float(
            self.scientific_offset_y,
            path="ContinuousAxisSpec.scientific_offset_y",
        )


@dataclass(slots=True)
class OctaveAxisSpec:
    """倍频程轴配置。"""

    show_every: int | None = None
    positions: tuple[float, ...] | None = None
    labels: tuple[str, ...] | None = None

    def __post_init__(self) -> None:
        self.show_every = _AXIS_CONFIG_PARSER.optional_int(self.show_every, path="OctaveAxisSpec.show_every")
        if self.show_every is not None and self.show_every <= 0:
            raise ValueError("OctaveAxisSpec.show_every 必须大于 0。")
        self.positions = _AXIS_CONFIG_PARSER.optional_float_tuple(self.positions, path="OctaveAxisSpec.positions")
        self.labels = _AXIS_CONFIG_PARSER.optional_string_tuple(self.labels, path="OctaveAxisSpec.labels")
        if (self.positions is None) != (self.labels is None):
            raise ValueError("OctaveAxisSpec.positions 与 OctaveAxisSpec.labels 必须同时提供。")
        if self.positions is not None and self.labels is not None and len(self.positions) != len(self.labels):
            raise ValueError("OctaveAxisSpec.positions 与 OctaveAxisSpec.labels 长度必须一致。")


AxisSpec = ContinuousAxisSpec | OctaveAxisSpec


@dataclass(slots=True)
class AxisConfig:
    """绘图坐标轴语义配置。"""

    x: AxisSpec | None = None
    y: AxisSpec | None = None

    def __post_init__(self) -> None:
        if self.x is not None and not isinstance(self.x, ContinuousAxisSpec | OctaveAxisSpec):
            raise TypeError("AxisConfig.x 必须是 ContinuousAxisSpec、OctaveAxisSpec 或 None。")
        if self.y is not None and not isinstance(self.y, ContinuousAxisSpec | OctaveAxisSpec):
            raise TypeError("AxisConfig.y 必须是 ContinuousAxisSpec、OctaveAxisSpec 或 None。")

    @classmethod
    def merge(cls, *configs: AxisConfig | None) -> AxisConfig | None:
        """按顺序合并多个坐标轴配置。"""

        x: AxisSpec | None = None
        y: AxisSpec | None = None
        for config in configs:
            if config is None:
                continue
            if config.x is not None:
                x = config.x
            if config.y is not None:
                y = config.y
        if x is None and y is None:
            return None
        return cls(x=x, y=y)


_ALLOWED_AXIS_KEYS = {"x", "y"}
_ALLOWED_SIDE_KEYS = {"kind", "label", "ticks", "limits", "formatter"}
_ALLOWED_CONTINUOUS_TICKS_KEYS = {"values", "major", "minor", "num_segments"}
_ALLOWED_STEP_KEYS = {"step", "origin"}
_ALLOWED_LIMITS_KEYS = {"min", "max", "baseline", "height_ratio"}
_ALLOWED_FORMATTER_KEYS = {"decimals", "trim_trailing_zeros", "scientific"}
_ALLOWED_SCIENTIFIC_KEYS = {"enabled", "fontsize", "exponent", "offset"}
_ALLOWED_OFFSET_KEYS = {"x", "y"}
_ALLOWED_OCTAVE_TICKS_KEYS = {"positions", "labels"}
_ALLOWED_OCTAVE_FORMATTER_KEYS = {"show_every"}


def _parse_continuous_axis(payload: Mapping[str, Any], *, path: str) -> ContinuousAxisSpec:
    ticks = _AXIS_CONFIG_PARSER.mapping_or_empty(payload.get("ticks"), path=f"{path}.ticks")
    limits = _AXIS_CONFIG_PARSER.mapping_or_empty(payload.get("limits"), path=f"{path}.limits")
    formatter = _AXIS_CONFIG_PARSER.mapping_or_empty(payload.get("formatter"), path=f"{path}.formatter")
    scientific = _AXIS_CONFIG_PARSER.mapping_or_empty(
        formatter.get("scientific"),
        path=f"{path}.formatter.scientific",
    )
    offset = _AXIS_CONFIG_PARSER.mapping_or_empty(
        scientific.get("offset"),
        path=f"{path}.formatter.scientific.offset",
    )
    major = _AXIS_CONFIG_PARSER.mapping_or_empty(ticks.get("major"), path=f"{path}.ticks.major")
    minor = _AXIS_CONFIG_PARSER.mapping_or_empty(ticks.get("minor"), path=f"{path}.ticks.minor")

    _AXIS_CONFIG_PARSER.raise_unknown_keys(path=path, payload=payload, allowed=_ALLOWED_SIDE_KEYS)
    _AXIS_CONFIG_PARSER.raise_unknown_keys(
        path=f"{path}.ticks",
        payload=ticks,
        allowed=_ALLOWED_CONTINUOUS_TICKS_KEYS,
    )
    _AXIS_CONFIG_PARSER.raise_unknown_keys(path=f"{path}.ticks.major", payload=major, allowed=_ALLOWED_STEP_KEYS)
    _AXIS_CONFIG_PARSER.raise_unknown_keys(path=f"{path}.ticks.minor", payload=minor, allowed=_ALLOWED_STEP_KEYS)
    _AXIS_CONFIG_PARSER.raise_unknown_keys(path=f"{path}.limits", payload=limits, allowed=_ALLOWED_LIMITS_KEYS)
    _AXIS_CONFIG_PARSER.raise_unknown_keys(
        path=f"{path}.formatter",
        payload=formatter,
        allowed=_ALLOWED_FORMATTER_KEYS,
    )
    _AXIS_CONFIG_PARSER.raise_unknown_keys(
        path=f"{path}.formatter.scientific",
        payload=scientific,
        allowed=_ALLOWED_SCIENTIFIC_KEYS,
    )
    _AXIS_CONFIG_PARSER.raise_unknown_keys(
        path=f"{path}.formatter.scientific.offset",
        payload=offset,
        allowed=_ALLOWED_OFFSET_KEYS,
    )

    return ContinuousAxisSpec(
        ticks=ticks.get("values"),
        major_step=major.get("step"),
        major_origin=major.get("origin", 0.0),
        num_segments=ticks.get("num_segments"),
        tick_min=limits.get("min"),
        tick_max=limits.get("max"),
        minor_step=minor.get("step"),
        minor_origin=minor.get("origin", 0.0),
        baseline=limits.get("baseline"),
        height_ratio=limits.get("height_ratio"),
        decimals=formatter.get("decimals"),
        trim_trailing_zeros=formatter.get("trim_trailing_zeros", True),
        scientific=scientific.get("enabled"),
        scientific_fontsize=scientific.get("fontsize"),
        scientific_exponent=scientific.get("exponent"),
        scientific_offset_x=offset.get("x"),
        scientific_offset_y=offset.get("y"),
    )


def _parse_octave_axis(payload: Mapping[str, Any], *, path: str) -> OctaveAxisSpec:
    ticks = _AXIS_CONFIG_PARSER.mapping_or_empty(payload.get("ticks"), path=f"{path}.ticks")
    formatter = _AXIS_CONFIG_PARSER.mapping_or_empty(payload.get("formatter"), path=f"{path}.formatter")
    _AXIS_CONFIG_PARSER.raise_unknown_keys(path=path, payload=payload, allowed=_ALLOWED_SIDE_KEYS)
    _AXIS_CONFIG_PARSER.raise_unknown_keys(
        path=f"{path}.ticks",
        payload=ticks,
        allowed=_ALLOWED_OCTAVE_TICKS_KEYS,
    )
    _AXIS_CONFIG_PARSER.raise_unknown_keys(
        path=f"{path}.formatter",
        payload=formatter,
        allowed=_ALLOWED_OCTAVE_FORMATTER_KEYS,
    )
    return OctaveAxisSpec(
        show_every=formatter.get("show_every"),
        positions=ticks.get("positions"),
        labels=ticks.get("labels"),
    )


def _parse_axis_spec(payload: object, *, path: str) -> AxisSpec | None:
    if payload is None:
        return None
    if not isinstance(payload, Mapping):
        raise ValueError(f"{path} 必须为映射。")
    _AXIS_CONFIG_PARSER.raise_unknown_keys(path=path, payload=payload, allowed=_ALLOWED_SIDE_KEYS)

    raw_kind = payload.get("kind")
    non_label_keys = {str(key) for key in payload.keys() if str(key) != "label"}
    if raw_kind is None:
        if not non_label_keys:
            return None
        raise ValueError(f"{path}.kind 必须为字符串。")
    if not isinstance(raw_kind, str):
        raise ValueError(f"{path}.kind 必须为字符串。")
    kind = raw_kind.strip().lower()
    if kind == "continuous":
        return _parse_continuous_axis(payload, path=path)
    if kind == "octave":
        return _parse_octave_axis(payload, path=path)
    raise ValueError(f"{path}.kind 仅支持 continuous 或 octave。")


def parse_axis_config(payload: object) -> AxisConfig | None:
    """从新的 axis 顶层块读取正式轴配置。"""

    if payload is None:
        return None
    if not isinstance(payload, Mapping):
        raise ValueError("axis 必须为映射。")
    _AXIS_CONFIG_PARSER.raise_unknown_keys(path="axis", payload=payload, allowed=_ALLOWED_AXIS_KEYS)
    axis_config = AxisConfig(
        x=_parse_axis_spec(payload.get("x"), path="axis.x"),
        y=_parse_axis_spec(payload.get("y"), path="axis.y"),
    )
    if axis_config.x is None and axis_config.y is None:
        return None
    return axis_config


__all__ = [
    "AxisConfig",
    "ContinuousAxisSpec",
    "OctaveAxisSpec",
    "parse_axis_config",
]
