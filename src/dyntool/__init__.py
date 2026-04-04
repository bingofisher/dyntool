"""AdvDynTool 顶层正式公开入口。"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

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
    DefaultSample,
    DefaultSampleSet,
    OperationResult,
    VibrationTestSample,
    VibrationTestSampleSet,
)
from .logging import LoggingMode
from .domain.plot_types import PlotKind
from .storage.types import AttrDataFormat, ContainerFormat, StorageConnectOptions, StorageMode, StorageScheme

if TYPE_CHECKING:
    from . import config, logging, plotting, resources, storage


_LAZY_MODULE_EXPORTS = {"config", "logging", "plotting", "resources", "storage"}


def _initialize_default_bindings() -> None:
    """按需导入并执行默认 runtime 绑定。"""

    runtime_binding = importlib.import_module(".application.runtime_binding", __name__)
    runtime_binding._initialize_default_bindings()


def __getattr__(name: str) -> object:
    """按需加载正式模块导出，避免顶层导入产生额外副作用。"""

    if name in _LAZY_MODULE_EXPORTS:
        module = importlib.import_module(f".{name}", __name__)
        globals()[name] = module
        return module
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# 顶层导入只注册默认 runtime 初始化器，不直接触发默认 runtime 绑定。
register_default_runtime_initializer(_initialize_default_bindings)

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
    "DefaultSample",
    "DefaultSampleSet",
    "VibrationTestSample",
    "VibrationTestSampleSet",
    "SampleDomain",
    "UnitSystem",
    "StorageScheme",
    "StorageMode",
    "StorageConnectOptions",
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
