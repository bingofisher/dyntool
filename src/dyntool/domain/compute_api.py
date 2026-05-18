"""领域对象统一计算入口与计算计划定义。"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Iterable, Mapping, Self

import pandas as pd

from ..compute.features import (
    absmax_feature,
    band_rms_feature,
    crest_factor_feature,
    envelope_feature,
    mean_feature,
    peak_feature,
    peaks_feature,
    rms_feature,
    std_feature,
    zero_crossings_feature,
)
from ..compute.flow import ComputeFlow

if TYPE_CHECKING:
    from .models import DataModelBase, TimeSeries
    from .samples.base import SampleBase
    from .samples.batch import BatchOperationReport, OperationResult
    from .samples.sets import SampleSetBase


class ComputeSource(StrEnum):
    """时程序列计算源枚举。"""

    ACCEL = "accel"
    VEL = "vel"
    DISP = "disp"
    FORCE = "force"


class ComputeOperation(StrEnum):
    """统一计算操作枚举。"""

    PROCESS = "process"
    DERIVE = "derive"
    SPECTRUM = "spectrum"
    RESPONSE = "response"
    EVALUATE_ZVL = "evaluate_zvl"
    EVALUATE_OTOVL = "evaluate_otovl"
    EVALUATE_FDMVL = "evaluate_fdmvl"
    EVALUATE_FPVDV = "evaluate_fpvdv"
    FEATURE = "feature"


@dataclass(frozen=True, slots=True)
class ComputeStep:
    """表示计算计划中的单个步骤。"""

    group: str
    method: str
    params: dict[str, Any] = field(default_factory=dict)
    source: ComputeSource | str | None = None
    stage: str | None = None
    commit_mode: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """导出字典载荷。"""

        return {
            "group": self.group,
            "method": self.method,
            "params": dict(self.params),
            "source": None if self.source is None else str(self.source),
            "stage": self.stage,
            "commit_mode": self.commit_mode,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Self:
        """从字典恢复步骤。"""

        return cls(
            group=str(data["group"]),
            method=str(data["method"]),
            params=dict(data.get("params", {})),
            source=data.get("source"),
            stage=data.get("stage"),
            commit_mode=data.get("commit_mode"),
        )


@dataclass(frozen=True, slots=True)
class ComputePlan:
    """表示可复用的计算计划。"""

    name: str
    steps: tuple[ComputeStep, ...]
    default_source: ComputeSource | str | None = None
    schema_version: int = 1
    plan_kind: str = "compute_plan"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """导出字典载荷。"""

        return {
            "name": self.name,
            "default_source": None if self.default_source is None else str(self.default_source),
            "schema_version": self.schema_version,
            "plan_kind": self.plan_kind,
            "metadata": dict(self.metadata),
            "steps": [step.to_dict() for step in self.steps],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Self:
        """从字典恢复计划。"""

        steps = tuple(ComputeStep.from_dict(item) for item in data.get("steps", ()))
        return cls(
            name=str(data["name"]),
            default_source=data.get("default_source"),
            schema_version=int(data.get("schema_version", 1)),
            plan_kind=str(data.get("plan_kind", "compute_plan")),
            metadata=dict(data.get("metadata", {})),
            steps=steps,
        )


class _ComputeSourceResolver:
    """集中处理样本中的时程序列来源解析。"""

    _TIME_SERIES_SLOTS = ("accel", "vel", "disp", "force")

    def normalize(self, source: ComputeSource | str | None) -> str | None:
        """统一规范化来源名称。"""

        if source is None:
            return None
        return str(source)

    def time_series_slots(self, sample: "SampleBase") -> tuple[str, ...]:
        """返回样本已声明的时程序列槽位。"""

        return tuple(name for name in self._TIME_SERIES_SLOTS if sample.sample_schema.has_slot(name))

    def resolve_sample_source(self, sample: "SampleBase", source: ComputeSource | str | None) -> str:
        """解析样本实际可用的时程序列来源。"""

        normalized = self.normalize(source)
        if normalized is not None:
            return normalized
        for name in self.time_series_slots(sample):
            if sample.get_data_var(name) is not None:
                return name
        raise ValueError("当前样本没有可用于计算的时程序列槽位。")

    def resolve_sample_timeseries(
        self,
        sample: "SampleBase",
        source: ComputeSource | str | None,
    ) -> tuple[str, "TimeSeries"]:
        """解析并返回样本中的时程序列对象。"""

        from .models import TimeSeries

        resolved = self.resolve_sample_source(sample, source)
        if not sample.sample_schema.has_slot(resolved):
            raise ValueError(f"当前样本不支持时程序列槽位 '{resolved}'。")
        model = sample.get_data_var(resolved)
        if model is None:
            raise ValueError(f"槽位 '{resolved}' 没有已加载的数据。")
        if not isinstance(model, TimeSeries):
            raise TypeError(f"槽位 '{resolved}' 不是时程序列模型。")
        return resolved, model


_SOURCE_RESOLVER = _ComputeSourceResolver()


class DataModelComputeNamespace:
    """`DataModelBase` 的统一计算入口。"""

    def __init__(self, model: "DataModelBase") -> None:
        self._model = model

    @property
    def process(self) -> Self:
        """返回处理分组视图。"""

        return self

    @property
    def derive(self) -> Self:
        """返回派生分组视图。"""

        return self

    @property
    def spectrum(self) -> Self:
        """返回频谱分组视图。"""

        return self

    @property
    def response(self) -> Self:
        """返回响应谱分组视图。"""

        return self

    @property
    def evaluate(self) -> Self:
        """返回评价分组视图。"""

        return self

    @property
    def feature(self) -> Self:
        """返回特征分组视图。"""

        return self

    def flow(self) -> ComputeFlow:
        """以当前模型启动处理流。"""

        return ComputeFlow(_result=self._model)

    def pipeline(self, **kwargs: Any) -> "DataModelBase":
        """执行 one-shot 处理流水线。"""

        flow = self.flow()
        truncate_range = kwargs.get("truncate_range")
        baseline = kwargs.get("baseline")
        baseline_order = kwargs.get("baseline_order", 1)
        highpass = kwargs.get("highpass")
        lowpass = kwargs.get("lowpass")
        bandpass = kwargs.get("bandpass")
        filter_order = kwargs.get("filter_order", 4)
        if truncate_range is not None:
            flow.truncate(*truncate_range)
        if baseline is not None:
            flow.baseline(method=baseline, order=baseline_order)
        if highpass is not None:
            flow.highpass(highpass, order=filter_order)
        if lowpass is not None:
            flow.lowpass(lowpass, order=filter_order)
        if bandpass is not None:
            flow.bandpass(bandpass[0], bandpass[1], order=filter_order)
        result = flow.commit(replace=False)
        if not isinstance(result, type(self._model)):
            raise TypeError("处理流未返回同类模型对象。")
        return result

    def _call_model_method(self, method_name: str, **kwargs: Any) -> Any:
        method = getattr(self._model, method_name, None)
        if method is None:
            raise TypeError(f"{type(self._model).__name__} 不支持 {method_name}。")
        return method(**kwargs)

    def _model_values(self) -> Any:
        getter = getattr(self._model, "get_value", None)
        if getter is None:
            raise TypeError(f"{type(self._model).__name__} 不支持通用数值特征计算。")
        return getter()

    def vel(self, **kwargs: Any) -> Any:
        """计算速度。"""

        return self._call_model_method("calc_vel", **kwargs)

    def disp(self, **kwargs: Any) -> Any:
        """计算位移。"""

        return self._call_model_method("calc_disp", **kwargs)

    def accel(self, **kwargs: Any) -> Any:
        """计算加速度。"""

        return self._call_model_method("calc_accel", **kwargs)

    def freqspec(self, **kwargs: Any) -> Any:
        """计算频谱。"""

        return self._call_model_method("calc_freqspec", **kwargs)

    def respspec(self, **kwargs: Any) -> Any:
        """计算响应谱。"""

        return self._call_model_method("calc_respspec", **kwargs)

    def zvl(self, **kwargs: Any) -> Any:
        """执行 ZVL 评价。"""

        return self._call_model_method("eval_zvl", **kwargs)

    def otovl(self, **kwargs: Any) -> Any:
        """执行 OTOVL 评价。"""

        return self._call_model_method("eval_otovl", **kwargs)

    def fdmvl(self, **kwargs: Any) -> Any:
        """执行 FDMVL 评价。"""

        return self._call_model_method("eval_fdmvl", **kwargs)

    def fpvdv(self, **kwargs: Any) -> Any:
        """执行 FPVDV 评价。"""

        return self._call_model_method("eval_fpvdv", **kwargs)

    def absmax(self) -> float:
        """返回绝对峰值。"""

        return absmax_feature(self._model_values())["absmax"]

    def rms(self) -> float:
        """返回均方根。"""

        return rms_feature(self._model_values())["rms"]

    def mean(self) -> float:
        """返回均值。"""

        return mean_feature(self._model_values())["mean"]

    def std(self) -> float:
        """返回标准差。"""

        return std_feature(self._model_values())["std"]

    def crest_factor(self) -> float:
        """返回峰值因子。"""

        return crest_factor_feature(self._model_values())["crest_factor"]

    def zero_crossings(self) -> int:
        """返回零交叉次数。"""

        return zero_crossings_feature(self._model_values())["zero_crossings"]

    def peak(self, **kwargs: Any) -> dict[str, float | int]:
        """返回主峰结果。"""

        return peak_feature(self._model_values(), **kwargs)

    def peaks(self, **kwargs: Any) -> dict[str, Any]:
        """返回多峰检测结果。"""

        return peaks_feature(self._model_values(), **kwargs)

    def envelope(self) -> dict[str, Any]:
        """返回包络序列。"""

        return envelope_feature(self._model_values())

    def band_rms(self, *, fs: float, center_freq: float, octave: float = 1.0 / 3.0) -> float:
        """返回指定倍频带的均方根。"""

        return band_rms_feature(
            self._model_values(),
            fs=fs,
            center_freq=center_freq,
            octave=octave,
        )["band_rms"]

    def available(self) -> tuple[ComputeOperation, ...]:
        """返回当前模型可执行的能力列表。"""

        operations: list[ComputeOperation] = []
        if all(hasattr(self._model, name) for name in ("truncate", "baseline_correct", "filter_highpass")):
            operations.append(ComputeOperation.PROCESS)
        if any(hasattr(self._model, name) for name in ("calc_vel", "calc_disp", "calc_accel")):
            operations.append(ComputeOperation.DERIVE)
        if hasattr(self._model, "calc_freqspec"):
            operations.append(ComputeOperation.SPECTRUM)
        if hasattr(self._model, "calc_respspec"):
            operations.append(ComputeOperation.RESPONSE)
        if hasattr(self._model, "eval_zvl"):
            operations.append(ComputeOperation.EVALUATE_ZVL)
        if hasattr(self._model, "eval_otovl"):
            operations.append(ComputeOperation.EVALUATE_OTOVL)
        if hasattr(self._model, "eval_fdmvl"):
            operations.append(ComputeOperation.EVALUATE_FDMVL)
        if hasattr(self._model, "eval_fpvdv"):
            operations.append(ComputeOperation.EVALUATE_FPVDV)
        if hasattr(self._model, "get_value"):
            operations.append(ComputeOperation.FEATURE)
        return tuple(dict.fromkeys(operations))

    def supports(self, operation: ComputeOperation | str, *, source: ComputeSource | str | None = None) -> bool:
        """判断当前模型是否支持指定能力。"""

        del source
        try:
            normalized = ComputeOperation(str(operation))
        except ValueError:
            return False
        return normalized in self.available()

    def run(self, operation: ComputeOperation | str, **kwargs: Any) -> Any:
        """按统一枚举入口调度模型计算。"""

        normalized = ComputeOperation(str(operation))
        if normalized is ComputeOperation.PROCESS:
            return self.pipeline(**kwargs)
        if normalized is ComputeOperation.DERIVE:
            raise ValueError("derive 需要显式指定具体方法。")
        if normalized is ComputeOperation.SPECTRUM:
            return self.freqspec(**kwargs)
        if normalized is ComputeOperation.RESPONSE:
            return self.respspec(**kwargs)
        if normalized is ComputeOperation.EVALUATE_ZVL:
            return self.zvl(**kwargs)
        if normalized is ComputeOperation.EVALUATE_OTOVL:
            return self.otovl(**kwargs)
        if normalized is ComputeOperation.EVALUATE_FDMVL:
            return self.fdmvl(**kwargs)
        if normalized is ComputeOperation.EVALUATE_FPVDV:
            return self.fpvdv(**kwargs)
        if normalized is ComputeOperation.FEATURE:
            return self.absmax()
        raise ValueError(f"不支持的计算操作: {normalized}")


class SampleComputeNamespace:
    """`SampleBase` 的统一计算入口。"""

    def __init__(self, sample: "SampleBase") -> None:
        self._sample = sample

    @property
    def process(self) -> Self:
        """返回处理分组视图。"""

        return self

    @property
    def spectrum(self) -> Self:
        """返回频谱分组视图。"""

        return self

    @property
    def response(self) -> Self:
        """返回响应谱分组视图。"""

        return self

    @property
    def evaluate(self) -> Self:
        """返回评价分组视图。"""

        return self

    @property
    def feature(self) -> Self:
        """返回特征分组视图。"""

        return self

    @property
    def plan(self) -> Self:
        """返回计划分组视图。"""

        return self

    def _series(self, source: ComputeSource | str | None = None) -> "TimeSeries":
        _, model = _SOURCE_RESOLVER.resolve_sample_timeseries(self._sample, source)
        return model

    def _ensure_accel_only(self, source: ComputeSource | str | None) -> None:
        normalized = _SOURCE_RESOLVER.normalize(source)
        if normalized not in {None, ComputeSource.ACCEL.value}:
            raise ValueError("当前操作仅支持 accel 作为计算源。")

    def flow(self, *, source: ComputeSource | str | None = None) -> ComputeFlow:
        """以指定时程序列槽位启动处理流。"""

        resolved, model = _SOURCE_RESOLVER.resolve_sample_timeseries(self._sample, source)

        def _commit_handler(result: Any, *, replace: bool) -> Any:
            if not replace:
                return result
            self._sample.set_data_var(resolved, result)
            return self._sample

        return ComputeFlow(_result=model, commit_handler=_commit_handler, source=resolved)

    def pipeline(
        self,
        *,
        source: ComputeSource | str | None = None,
        replace: bool = True,
        strict: bool | None = None,
        **kwargs: Any,
    ) -> "OperationResult[SampleBase]":
        """执行 one-shot 处理流水线。"""

        from .samples.batch import make_operation_result

        del strict
        try:
            flow = self.flow(source=source)
            truncate_range = kwargs.get("truncate_range")
            baseline = kwargs.get("baseline")
            baseline_order = kwargs.get("baseline_order", 1)
            highpass = kwargs.get("highpass")
            lowpass = kwargs.get("lowpass")
            bandpass = kwargs.get("bandpass")
            filter_order = kwargs.get("filter_order", 4)
            if truncate_range is not None:
                flow.truncate(*truncate_range)
            if baseline is not None:
                flow.baseline(method=baseline, order=baseline_order)
            if highpass is not None:
                flow.highpass(highpass, order=filter_order)
            if lowpass is not None:
                flow.lowpass(lowpass, order=filter_order)
            if bandpass is not None:
                flow.bandpass(bandpass[0], bandpass[1], order=filter_order)
            flow.commit(replace=replace)
            return make_operation_result(
                action="preprocess",
                success=True,
                message="处理完成",
                value=self._sample,
            )
        except Exception as exc:  # noqa: BLE001
            return make_operation_result(
                action="preprocess",
                success=False,
                message=f"处理失败: {exc}",
                value=self._sample,
                error=exc,
            )

    def freqspec(self, *, source: ComputeSource | str | None = None, **kwargs: Any) -> "OperationResult[SampleBase]":
        """计算频谱。"""

        self._ensure_accel_only(source)
        return self._sample.calc_freqspec(**kwargs)

    def respspec(self, *, source: ComputeSource | str | None = None, **kwargs: Any) -> "OperationResult[SampleBase]":
        """计算响应谱。"""

        self._ensure_accel_only(source)
        return self._sample.calc_respspec(**kwargs)

    def zvl(self, **kwargs: Any) -> "OperationResult[SampleBase]":
        """执行 ZVL 评价。"""

        return self._sample.eval_zvl(**kwargs)

    def otovl(self, **kwargs: Any) -> "OperationResult[SampleBase]":
        """执行 OTOVL 评价。"""

        return self._sample.eval_otovl(**kwargs)

    def fdmvl(self, **kwargs: Any) -> "OperationResult[SampleBase]":
        """执行 FDMVL 评价。"""

        return self._sample.eval_fdmvl(**kwargs)

    def fpvdv(self, **kwargs: Any) -> "OperationResult[SampleBase]":
        """执行 FPVDV 评价。"""

        return self._sample.eval_fpvdv(**kwargs)

    def absmax(self, *, source: ComputeSource | str | None = None) -> float:
        """返回时程序列绝对峰值。"""

        return absmax_feature(self._series(source).get_value())["absmax"]

    def rms(self, *, source: ComputeSource | str | None = None) -> float:
        """返回时程序列均方根。"""

        return rms_feature(self._series(source).get_value())["rms"]

    def mean(self, *, source: ComputeSource | str | None = None) -> float:
        """返回时程序列均值。"""

        return mean_feature(self._series(source).get_value())["mean"]

    def std(self, *, source: ComputeSource | str | None = None) -> float:
        """返回时程序列标准差。"""

        return std_feature(self._series(source).get_value())["std"]

    def crest_factor(self, *, source: ComputeSource | str | None = None) -> float:
        """返回时程序列峰值因子。"""

        return crest_factor_feature(self._series(source).get_value())["crest_factor"]

    def zero_crossings(self, *, source: ComputeSource | str | None = None) -> int:
        """返回时程序列零交叉次数。"""

        return zero_crossings_feature(self._series(source).get_value())["zero_crossings"]

    def peak(self, *, source: ComputeSource | str | None = None, **kwargs: Any) -> dict[str, float | int]:
        """返回时程序列主峰结果。"""

        return peak_feature(self._series(source).get_value(), **kwargs)

    def peaks(self, *, source: ComputeSource | str | None = None, **kwargs: Any) -> dict[str, Any]:
        """返回时程序列多峰检测结果。"""

        return peaks_feature(self._series(source).get_value(), **kwargs)

    def envelope(self, *, source: ComputeSource | str | None = None) -> dict[str, Any]:
        """返回时程序列包络结果。"""

        return envelope_feature(self._series(source).get_value())

    def band_rms(
        self,
        *,
        fs: float,
        center_freq: float,
        octave: float = 1.0 / 3.0,
        source: ComputeSource | str | None = None,
    ) -> float:
        """返回指定倍频带的均方根。"""

        return band_rms_feature(
            self._series(source).get_value(),
            fs=fs,
            center_freq=center_freq,
            octave=octave,
        )["band_rms"]

    def create(
        self,
        *,
        name: str,
        steps: Iterable[ComputeStep],
        default_source: ComputeSource | str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> ComputePlan:
        """构建计算计划。"""

        return ComputePlan(
            name=name,
            steps=tuple(steps),
            default_source=default_source,
            metadata=dict(metadata or {}),
        )

    def available(self) -> tuple[ComputeOperation, ...]:
        """返回当前样本可执行的能力列表。"""

        operations: list[ComputeOperation] = []
        if any(
            self._sample.get_data_var(name) is not None for name in _SOURCE_RESOLVER.time_series_slots(self._sample)
        ):
            operations.extend((ComputeOperation.PROCESS, ComputeOperation.SPECTRUM, ComputeOperation.FEATURE))
        accel = self._sample.get_data_var("accel") if self._sample.sample_schema.has_slot("accel") else None
        if accel is not None:
            operations.extend(
                (
                    ComputeOperation.RESPONSE,
                    ComputeOperation.EVALUATE_ZVL,
                    ComputeOperation.EVALUATE_OTOVL,
                    ComputeOperation.EVALUATE_FDMVL,
                    ComputeOperation.EVALUATE_FPVDV,
                )
            )
        if any(
            self._sample.get_data_var(name) is not None
            for name in ("accel", "vel", "disp")
            if self._sample.sample_schema.has_slot(name)
        ):
            operations.append(ComputeOperation.DERIVE)
        return tuple(dict.fromkeys(operations))

    def supports(self, operation: ComputeOperation | str, *, source: ComputeSource | str | None = None) -> bool:
        """判断当前样本是否支持指定能力。"""

        try:
            normalized = ComputeOperation(str(operation))
        except ValueError:
            return False
        if normalized not in self.available():
            return False
        if normalized in {
            ComputeOperation.RESPONSE,
            ComputeOperation.EVALUATE_ZVL,
            ComputeOperation.EVALUATE_OTOVL,
            ComputeOperation.EVALUATE_FDMVL,
            ComputeOperation.EVALUATE_FPVDV,
        }:
            return _SOURCE_RESOLVER.normalize(source) in {None, ComputeSource.ACCEL.value}
        if normalized in {ComputeOperation.PROCESS, ComputeOperation.SPECTRUM, ComputeOperation.FEATURE}:
            try:
                _SOURCE_RESOLVER.resolve_sample_timeseries(self._sample, source)
            except Exception:  # noqa: BLE001
                return False
        return True

    def run(self, operation: ComputeOperation | str, **kwargs: Any) -> Any:
        """按统一枚举入口调度样本计算。"""

        normalized = ComputeOperation(str(operation))
        if normalized is ComputeOperation.PROCESS:
            return self.pipeline(**kwargs)
        if normalized is ComputeOperation.SPECTRUM:
            return self.freqspec(**kwargs)
        if normalized is ComputeOperation.RESPONSE:
            return self.respspec(**kwargs)
        if normalized is ComputeOperation.EVALUATE_ZVL:
            return self.zvl(**kwargs)
        if normalized is ComputeOperation.EVALUATE_OTOVL:
            return self.otovl(**kwargs)
        if normalized is ComputeOperation.EVALUATE_FDMVL:
            return self.fdmvl(**kwargs)
        if normalized is ComputeOperation.EVALUATE_FPVDV:
            return self.fpvdv(**kwargs)
        if normalized is ComputeOperation.FEATURE:
            return self.absmax(source=kwargs.get("source"))
        raise ValueError(f"不支持的计算操作: {normalized}")

    def run_plan(
        self,
        plan: ComputePlan,
        *,
        overwrite: bool = False,
        strict: bool | None = None,
    ) -> "OperationResult[SampleBase]":
        """按顺序执行计算计划。"""

        from .samples.batch import make_operation_result

        del strict
        try:
            for step in plan.steps:
                source = step.source or plan.default_source
                group = step.group.strip().lower()
                if group == "process":
                    self.pipeline(source=source, replace=True, **step.params)
                    continue
                if group == "spectrum":
                    self.freqspec(source=source, overwrite=overwrite, **step.params)
                    continue
                if group == "response":
                    self.respspec(source=source, overwrite=overwrite, **step.params)
                    continue
                if group == "evaluate":
                    runner = getattr(self, step.method)
                    runner(overwrite=overwrite, **step.params)
                    continue
                raise ValueError(f"不支持的计划步骤分组: {step.group}")
            return make_operation_result(
                action="run_plan",
                success=True,
                message=f"计划 '{plan.name}' 执行完成",
                value=self._sample,
            )
        except Exception as exc:  # noqa: BLE001
            return make_operation_result(
                action="run_plan",
                success=False,
                message=f"计划 '{plan.name}' 执行失败: {exc}",
                value=self._sample,
                error=exc,
            )


class SampleSetComputeNamespace:
    """`SampleSetBase` 的统一计算入口。"""

    def __init__(self, sample_set: "SampleSetBase[Any]") -> None:
        self._sample_set = sample_set

    @property
    def process(self) -> Self:
        """返回处理分组视图。"""

        return self

    @property
    def spectrum(self) -> Self:
        """返回频谱分组视图。"""

        return self

    @property
    def response(self) -> Self:
        """返回响应谱分组视图。"""

        return self

    @property
    def evaluate(self) -> Self:
        """返回评价分组视图。"""

        return self

    @property
    def plan(self) -> Self:
        """返回计划分组视图。"""

        return self

    def flow(self) -> ComputeFlow:
        """以当前样本集启动批处理流。"""

        return ComputeFlow(_result=self._sample_set)

    def pipeline(self, **kwargs: Any) -> "BatchOperationReport[Any]":
        """执行批量处理流水线。"""

        return self._sample_set._batch_process_pipeline(**kwargs)

    def freqspec(self, **kwargs: Any) -> "BatchOperationReport[Any]":
        """执行批量频谱计算。"""

        return self._sample_set.calc_freqspec(**kwargs)

    def respspec(self, **kwargs: Any) -> "BatchOperationReport[Any]":
        """执行批量响应谱计算。"""

        return self._sample_set.calc_respspec(**kwargs)

    def zvl(self, **kwargs: Any) -> "BatchOperationReport[Any]":
        """执行批量 ZVL 评价。"""

        return self._sample_set.eval_zvl(**kwargs)

    def otovl(self, **kwargs: Any) -> "BatchOperationReport[Any]":
        """执行批量 OTOVL 评价。"""

        return self._sample_set.eval_otovl(**kwargs)

    def fdmvl(self, **kwargs: Any) -> "BatchOperationReport[Any]":
        """执行批量 FDMVL 评价。"""

        return self._sample_set.eval_fdmvl(**kwargs)

    def fpvdv(self, **kwargs: Any) -> "BatchOperationReport[Any]":
        """执行批量 FPVDV 评价。"""

        return self._sample_set.eval_fpvdv(**kwargs)

    def create(
        self,
        *,
        name: str,
        steps: Iterable[ComputeStep],
        default_source: ComputeSource | str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> ComputePlan:
        """构建批量计算计划。"""

        return ComputePlan(
            name=name,
            steps=tuple(steps),
            default_source=default_source,
            metadata=dict(metadata or {}),
        )

    def available(self) -> tuple[ComputeOperation, ...]:
        """返回样本集中至少一个样本可执行的能力列表。"""

        operations: list[ComputeOperation] = []
        for sample in self._sample_set.values():
            operations.extend(sample.compute.available())
        return tuple(dict.fromkeys(operations))

    def supports(self, operation: ComputeOperation | str, *, source: ComputeSource | str | None = None) -> bool:
        """判断样本集中是否存在可执行指定能力的样本。"""

        try:
            normalized = ComputeOperation(str(operation))
        except ValueError:
            return False
        return any(sample.compute.supports(normalized, source=source) for sample in self._sample_set.values())

    def run(self, operation: ComputeOperation | str, **kwargs: Any) -> Any:
        """按统一枚举入口调度批量计算。"""

        normalized = ComputeOperation(str(operation))
        if normalized is ComputeOperation.PROCESS:
            return self.pipeline(**kwargs)
        if normalized is ComputeOperation.SPECTRUM:
            return self.freqspec(**kwargs)
        if normalized is ComputeOperation.RESPONSE:
            return self.respspec(**kwargs)
        if normalized is ComputeOperation.EVALUATE_ZVL:
            return self.zvl(**kwargs)
        if normalized is ComputeOperation.EVALUATE_OTOVL:
            return self.otovl(**kwargs)
        if normalized is ComputeOperation.EVALUATE_FDMVL:
            return self.fdmvl(**kwargs)
        if normalized is ComputeOperation.EVALUATE_FPVDV:
            return self.fpvdv(**kwargs)
        raise ValueError(f"不支持的计算操作: {normalized}")


def ensure_multiindex_metadata(
    sample: "SampleBase",
    *,
    metadata_fields: Iterable[str] | None = None,
) -> tuple[str, ...]:
    """生成用于多重索引列的 metadata 元组。"""

    flattened = sample.metadata.to_flatten_dict(sep="@")
    values = [sample.uid, sample.alias]
    for metadata_field in metadata_fields or ():
        values.append(str(flattened.get(metadata_field, "")))
    return tuple(values)


def normalize_series_frame(model: "DataModelBase") -> pd.DataFrame:
    """按模型自身协议导出序列表格。"""

    frame = model.to_series_frame()
    if not isinstance(frame, pd.DataFrame):
        raise TypeError(f"{type(model).__name__} 的序列导出结果必须是 DataFrame。")
    return frame


__all__ = [
    "ComputeOperation",
    "ComputePlan",
    "ComputeSource",
    "ComputeStep",
    "DataModelComputeNamespace",
    "SampleComputeNamespace",
    "SampleSetComputeNamespace",
    "ensure_multiindex_metadata",
    "normalize_series_frame",
]
