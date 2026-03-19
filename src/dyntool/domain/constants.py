"""领域层常量、统一数据类别和单位工具导出。"""

from __future__ import annotations

from enum import StrEnum, unique

from ..compute.units import (
    UnitSystem,
    build_unit_overrides,
    canonicalize_unit,
    coerce_array_with_unit,
    convert_array,
    convert_to_base_unit,
    ensure_ndarray,
    format_label_with_unit,
    get_default_unit_system,
    get_unit_registry,
    infer_input_unit,
    normalize_unit,
    normalize_unit_map,
    parse_label_unit,
    resolve_current_units,
    resolve_file_units,
    set_default_unit_system,
    ureg,
)
from .enums import SampleDomain


class TimeSeriesCategory(StrEnum):
    """时程序列类别枚举。

    枚举值说明:
        - ``BASE``: 通用时程序列基类标签。
        - ``ACCEL``: 加速度时程。
        - ``VEL``: 速度时程。
        - ``DISP``: 位移时程。
        - ``FORCE``: 力时程。
    """

    BASE = "ts"
    ACCEL = "accel"
    VEL = "vel"
    DISP = "disp"
    FORCE = "force"


class ResponseSpectrumCategory(StrEnum):
    """反应谱类别枚举。

    枚举值说明:
        - ``BASE``: 反应谱基类标签。
        - ``SA``/``SV``/``SD``: 绝对加速度、速度、位移谱分量。
        - ``PSA``/``PSV``: 伪反应谱分量。
        - ``SPEC``: 统一反应谱容器。
    """

    BASE = "rs"
    SA = "sa"
    SV = "sv"
    SD = "sd"
    PSA = "psa"
    PSV = "psv"
    SPEC = "rs_spec"


class FrequencySpectrumCategory(StrEnum):
    """频谱类别枚举。

    枚举值说明:
        - ``BASE``: 频谱基类标签。
        - ``AMP``: 幅值谱分量。
        - ``PHA``: 相位谱分量。
        - ``SPEC``: 统一频谱容器。
    """

    BASE = "fs"
    AMP = "fs_amp"
    PHA = "fs_pha"
    SPEC = "fs_spec"


@unique
class DataCategory(StrEnum):
    """统一数据类别枚举。

    该枚举是模型注册、样本槽位映射、存储持久化和运行时反序列化的共同类别标签。

    枚举值说明:
        - ``TS_*``: 时程序列相关数据。
        - ``RS_*``: 反应谱相关数据。
        - ``FS_*``: 频谱相关数据。
        - ``*_EVAL`` 与其派生值: 振动评价结果及其分量。

    影响:
        该枚举会影响 ``DataModelBase`` 的类型注册、样本槽位名解析、存储类别标记，
        以及 ``from_storage`` / ``from_dict`` / ``inspect_units`` 等运行时分派行为。
    """

    UNDEFINED = "undefined"

    TS = TimeSeriesCategory.BASE
    TS_ACCEL = TimeSeriesCategory.ACCEL
    TS_VEL = TimeSeriesCategory.VEL
    TS_DISP = TimeSeriesCategory.DISP
    TS_FORCE = TimeSeriesCategory.FORCE

    RS = ResponseSpectrumCategory.BASE
    RS_SA = ResponseSpectrumCategory.SA
    RS_SV = ResponseSpectrumCategory.SV
    RS_SD = ResponseSpectrumCategory.SD
    RS_PSA = ResponseSpectrumCategory.PSA
    RS_PSV = ResponseSpectrumCategory.PSV
    RS_SPEC = ResponseSpectrumCategory.SPEC

    FS = FrequencySpectrumCategory.BASE
    FS_AMP = FrequencySpectrumCategory.AMP
    FS_PHA = FrequencySpectrumCategory.PHA
    FS_SPEC = FrequencySpectrumCategory.SPEC

    ZVL_EVAL = "zvl_eval"
    ZVL_V = "zvl_v"
    ZVL_AW = "zvl_aw"

    OTOVL_EVAL = "otovl_eval"
    OTOVL_COMP = "otovl_comp"
    OTOVL_ENV = "otovl_env"

    FPVDV_EVAL = "fpvdv_eval"
    FPVDV_V = "fpvdv_v"
    FPVDV_AW = "fpvdv_aw"

    FDMVL_EVAL = "fdmvl_eval"
    FDVL_MAX = "fdvl_max"
    FDVL_COMP = "fdvl_comp"

    ZVL_LIMIT = "zvl_limit"
    OTOVL_LIMIT = "otovl_limit"
    FPVDV_LIMIT = "fpvdv_limit"
    FDMVL_LIMIT = "fdmvl_limit"

    @staticmethod
    def list_categories() -> list[str]:
        """返回全部标准类别值列表。"""

        return [category.value for category in DataCategory]

    @staticmethod
    def to_sample_attr_name(category: "DataCategory") -> str:
        """将数据类别映射为样本对象上的标准属性名。"""

        return _DATA_CATEGORY_TO_SAMPLE_ATTR.get(category, category.value)


_DATA_CATEGORY_TO_SAMPLE_ATTR: dict[DataCategory, str] = {
    DataCategory.TS_ACCEL: "accel",
    DataCategory.TS_VEL: "vel",
    DataCategory.TS_DISP: "disp",
    DataCategory.TS_FORCE: "force",
    DataCategory.FS_SPEC: "freqspec",
    DataCategory.RS_SPEC: "respspec",
    DataCategory.ZVL_EVAL: "zvl",
    DataCategory.OTOVL_EVAL: "otovl",
    DataCategory.FPVDV_EVAL: "fpvdv",
    DataCategory.FDMVL_EVAL: "fdmvl",
}

SAMPLE_ATTR_TO_DATA_CATEGORY: dict[str, DataCategory] = {
    value: key for key, value in _DATA_CATEGORY_TO_SAMPLE_ATTR.items()
}
"""样本属性名到统一数据类别的反向映射。"""


def resolve_unit_system(
    explicit: UnitSystem | None = None,
    *,
    model_default: UnitSystem | None = None,
    global_default: UnitSystem | None = None,
) -> UnitSystem:
    """按显式参数、模型默认值和全局默认值解析最终单位制。"""

    if explicit is not None:
        return explicit
    if model_default is not None:
        return model_default
    return global_default or get_default_unit_system()


__all__ = [
    "SampleDomain",
    "TimeSeriesCategory",
    "ResponseSpectrumCategory",
    "FrequencySpectrumCategory",
    "DataCategory",
    "SAMPLE_ATTR_TO_DATA_CATEGORY",
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
    "resolve_unit_system",
    "set_default_unit_system",
    "ureg",
]
