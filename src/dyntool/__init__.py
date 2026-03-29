"""AdvDynTool 顶层正式公开入口。"""

from __future__ import annotations

import importlib

from . import config, logging, plotting, resources, storage
from ._version import __version__
from .domain.constants import UnitSystem
from .domain.enums import SampleDomain
from .domain.limits import (
    FDMVLLimit,
    FDMVLLimitStandard,
    FPVDVLimit,
    FPVDVLimitStandard,
    OTOVLLimit,
    OTOVLLimitStandard,
    ZVLLimit,
    ZVLLimitStandard,
)
from .domain.metadata import Metadata, VibrationTestMetadata
from .domain.models import (
    AccelSeries,
    DispSeries,
    FDMVLEval,
    FPVDVEval,
    ForceSeries,
    FreqAmpSeries,
    FreqPhaSeries,
    FreqSpec,
    MagnitudeConversion,
    OTOVLEval,
    PSpecAccelSeries,
    PSpecVelSeries,
    RespSpec,
    ResponseSpectrum,
    SpecAccelSeries,
    SpecDispSeries,
    SpecVelSeries,
    TimeSeries,
    TransferFunctionAnalyzer,
    TransferFunctionResult,
    VelSeries,
    ZVLEval,
)
from .domain.runtime import register_default_runtime_initializer
from .domain.samples import (
    BatchOperationReport,
    DefaultSample as _DefaultSample,
    DefaultSampleSet as _DefaultSampleSet,
    OperationResult,
    Sample,
    SampleSet,
    VibrationTestSample,
    VibrationTestSampleSet,
)
from .logging import LoggingMode
from .plotting.types import PlotKind
from .storage.types import AttrDataFormat, ContainerFormat, StorageMode, StorageScheme


def _initialize_default_bindings() -> None:
    """按需导入并执行默认 runtime 绑定。"""

    runtime_binding = importlib.import_module(".application.runtime_binding", __name__)
    runtime_binding._initialize_default_bindings()


# 顶层导入只注册默认 runtime 初始化器，不直接触发默认 runtime 绑定。
register_default_runtime_initializer(_initialize_default_bindings)

DefaultSample = _DefaultSample
DefaultSampleSet = _DefaultSampleSet

__all__ = [
    "__version__",
    "MagnitudeConversion",
    "TimeSeries",
    "AccelSeries",
    "VelSeries",
    "DispSeries",
    "ForceSeries",
    "FreqAmpSeries",
    "FreqPhaSeries",
    "FreqSpec",
    "ResponseSpectrum",
    "SpecAccelSeries",
    "SpecVelSeries",
    "SpecDispSeries",
    "PSpecAccelSeries",
    "PSpecVelSeries",
    "RespSpec",
    "BatchOperationReport",
    "OperationResult",
    "TransferFunctionAnalyzer",
    "TransferFunctionResult",
    "ZVLEval",
    "OTOVLEval",
    "FPVDVEval",
    "FDMVLEval",
    "ZVLLimit",
    "OTOVLLimit",
    "FPVDVLimit",
    "FDMVLLimit",
    "ZVLLimitStandard",
    "OTOVLLimitStandard",
    "FPVDVLimitStandard",
    "FDMVLLimitStandard",
    "Metadata",
    "VibrationTestMetadata",
    "Sample",
    "SampleSet",
    "VibrationTestSample",
    "VibrationTestSampleSet",
    "SampleDomain",
    "UnitSystem",
    "StorageScheme",
    "StorageMode",
    "AttrDataFormat",
    "ContainerFormat",
    "LoggingMode",
    "logging",
    "storage",
    "config",
    "resources",
    "PlotKind",
    "plotting",
]
