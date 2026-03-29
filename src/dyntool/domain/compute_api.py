"""领域对象统一计算入口与编排协议。"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Iterable, Mapping

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
    """时序计算源枚举。"""

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
    """计算计划中的单个步骤。"""

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
    def from_dict(cls, data: Mapping[str, Any]) -> "ComputeStep":
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
    """可复用的计算计划。"""

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
    def from_dict(cls, data: Mapping[str, Any]) -> "ComputePlan":
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


def _normalize_source(source: ComputeSource | str | None) -> str | None:
    if source is None:
        return None
    return str(source)


def _time_series_slots(sample: "SampleBase") -> tuple[str, ...]:
    slots: list[str] = []
    for name in ("accel", "vel", "disp", "force"):
        if sample.sample_schema.has_slot(name):
            slots.append(name)
    return tuple(slots)


def _resolve_sample_source(sample: "SampleBase", source: ComputeSource | str | None) -> str:
    if source is not None:
        return str(source)
    for name in ("accel", "vel", "disp", "force"):
        if sample.sample_schema.has_slot(name) and sample.get_data_var(name) is not None:
            return name
    raise ValueError("当前样本没有可用于计算的时序槽位")


def _resolve_sample_timeseries(sample: "SampleBase", source: ComputeSource | str | None) -> tuple[str, "TimeSeries"]:
    from .models import TimeSeries

    resolved = _resolve_sample_source(sample, source)
    if not sample.sample_schema.has_slot(resolved):
        raise ValueError(f"当前样本不支持时序槽位 '{resolved}'")
    model = sample.get_data_var(resolved)
    if model is None:
        raise ValueError(f"槽位 '{resolved}' 没有已加载的时序数据")
    if not isinstance(model, TimeSeries):
        raise TypeError(f"槽位 '{resolved}' 不是时序模型")
    return resolved, model


def _model_available_operations(model: "DataModelBase") -> tuple[ComputeOperation, ...]:
    operations: list[ComputeOperation] = []
    if all(hasattr(model, name) for name in ("truncate", "baseline_correct", "filter_highpass")):
        operations.append(ComputeOperation.PROCESS)
    if any(hasattr(model, name) for name in ("calc_vel", "calc_disp", "calc_accel")):
        operations.append(ComputeOperation.DERIVE)
    if hasattr(model, "calc_freqspec"):
        operations.append(ComputeOperation.SPECTRUM)
    if hasattr(model, "calc_respspec"):
        operations.append(ComputeOperation.RESPONSE)
    if hasattr(model, "eval_zvl"):
        operations.append(ComputeOperation.EVALUATE_ZVL)
    if hasattr(model, "eval_otovl"):
        operations.append(ComputeOperation.EVALUATE_OTOVL)
    if hasattr(model, "eval_fdmvl"):
        operations.append(ComputeOperation.EVALUATE_FDMVL)
    if hasattr(model, "eval_fpvdv"):
        operations.append(ComputeOperation.EVALUATE_FPVDV)
    if hasattr(model, "absmax"):
        operations.append(ComputeOperation.FEATURE)
    return tuple(dict.fromkeys(operations))


class _ModelProcessNamespace:
    """单模型处理分组。"""

    def __init__(self, model: "DataModelBase") -> None:
        self._model = model

    def flow(self) -> ComputeFlow:
        """以当前模型启动处理流。"""

        return ComputeFlow(_result=self._model)

    def pipeline(self, **kwargs: Any) -> "DataModelBase":
        """执行 one-shot 处理流程。"""

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
            raise TypeError("处理流未返回同类模型对象")
        return result


class _ModelDeriveNamespace:
    """单模型派生分组。"""

    def __init__(self, model: "DataModelBase") -> None:
        self._model = model

    def vel(self, **kwargs: Any) -> Any:
        """计算速度。"""

        return self._model.calc_vel(**kwargs)

    def disp(self, **kwargs: Any) -> Any:
        """计算位移。"""

        return self._model.calc_disp(**kwargs)

    def accel(self, **kwargs: Any) -> Any:
        """计算加速度。"""

        return self._model.calc_accel(**kwargs)


class _ModelSpectrumNamespace:
    """单模型频谱分组。"""

    def __init__(self, model: "DataModelBase") -> None:
        self._model = model

    def freqspec(self, **kwargs: Any) -> Any:
        """计算频谱。"""

        return self._model.calc_freqspec(**kwargs)


class _ModelResponseNamespace:
    """单模型响应谱分组。"""

    def __init__(self, model: "DataModelBase") -> None:
        self._model = model

    def respspec(self, **kwargs: Any) -> Any:
        """计算响应谱。"""

        return self._model.calc_respspec(**kwargs)


class _ModelEvaluateNamespace:
    """单模型评价分组。"""

    def __init__(self, model: "DataModelBase") -> None:
        self._model = model

    def zvl(self, **kwargs: Any) -> Any:
        return self._model.eval_zvl(**kwargs)

    def otovl(self, **kwargs: Any) -> Any:
        return self._model.eval_otovl(**kwargs)

    def fdmvl(self, **kwargs: Any) -> Any:
        return self._model.eval_fdmvl(**kwargs)

    def fpvdv(self, **kwargs: Any) -> Any:
        return self._model.eval_fpvdv(**kwargs)


class _ModelFeatureNamespace:
    """单模型特征分组。"""

    def __init__(self, model: "DataModelBase") -> None:
        self._model = model

    def absmax(self) -> float:
        """返回绝对峰值。"""

        value = getattr(self._model, "absmax", None)
        if value is None:
            raise TypeError(f"{type(self._model).__name__} 不支持 absmax 特征")
        return float(value)

    def rms(self) -> float:
        """返回均方根。"""

        return rms_feature(self._model.get_value())["rms"]

    def mean(self) -> float:
        """返回均值。"""

        return mean_feature(self._model.get_value())["mean"]

    def std(self) -> float:
        """返回标准差。"""

        return std_feature(self._model.get_value())["std"]

    def crest_factor(self) -> float:
        """返回峰值因子。"""

        return crest_factor_feature(self._model.get_value())["crest_factor"]

    def zero_crossings(self) -> int:
        """返回零交叉次数。"""

        return zero_crossings_feature(self._model.get_value())["zero_crossings"]

    def peak(self, **kwargs: Any) -> dict[str, float | int]:
        """返回主峰值信息。"""

        return peak_feature(self._model.get_value(), **kwargs)

    def peaks(self, **kwargs: Any) -> dict[str, Any]:
        """返回多峰检测结果。"""

        return peaks_feature(self._model.get_value(), **kwargs)

    def envelope(self) -> dict[str, Any]:
        """返回包络序列。"""

        return envelope_feature(self._model.get_value())

    def band_rms(self, *, fs: float, center_freq: float, octave: float = 1.0 / 3.0) -> float:
        """返回指定倍频带的均方根值。"""

        return band_rms_feature(
            self._model.get_value(),
            fs=fs,
            center_freq=center_freq,
            octave=octave,
        )["band_rms"]


class DataModelComputeNamespace:
    """DataModelBase 的统一计算入口。"""

    def __init__(self, model: "DataModelBase") -> None:
        self._model = model
        self.process = _ModelProcessNamespace(model)
        self.derive = _ModelDeriveNamespace(model)
        self.spectrum = _ModelSpectrumNamespace(model)
        self.response = _ModelResponseNamespace(model)
        self.evaluate = _ModelEvaluateNamespace(model)
        self.feature = _ModelFeatureNamespace(model)

    def available(self) -> tuple[ComputeOperation, ...]:
        """返回当前模型可执行的能力列表。"""

        return _model_available_operations(self._model)

    def supports(self, operation: ComputeOperation | str, *, source: ComputeSource | str | None = None) -> bool:
        """判断当前模型是否支持某项能力。"""

        del source
        try:
            normalized = ComputeOperation(str(operation))
        except ValueError:
            return False
        return normalized in self.available()

    def run(self, operation: ComputeOperation | str, **kwargs: Any) -> Any:
        """按统一枚举调度模型计算。"""

        normalized = ComputeOperation(str(operation))
        if normalized is ComputeOperation.PROCESS:
            return self.process.pipeline(**kwargs)
        if normalized is ComputeOperation.DERIVE:
            raise ValueError("derive 需要显式指定具体方法")
        if normalized is ComputeOperation.SPECTRUM:
            return self.spectrum.freqspec(**kwargs)
        if normalized is ComputeOperation.RESPONSE:
            return self.response.respspec(**kwargs)
        if normalized is ComputeOperation.EVALUATE_ZVL:
            return self.evaluate.zvl(**kwargs)
        if normalized is ComputeOperation.EVALUATE_OTOVL:
            return self.evaluate.otovl(**kwargs)
        if normalized is ComputeOperation.EVALUATE_FDMVL:
            return self.evaluate.fdmvl(**kwargs)
        if normalized is ComputeOperation.EVALUATE_FPVDV:
            return self.evaluate.fpvdv(**kwargs)
        if normalized is ComputeOperation.FEATURE:
            return self.feature.absmax()
        raise ValueError(f"不支持的计算操作: {normalized}")


class _SampleProcessNamespace:
    """单样本处理分组。"""

    def __init__(self, sample: "SampleBase") -> None:
        self._sample = sample

    def flow(self, *, source: ComputeSource | str | None = None) -> ComputeFlow:
        """以指定时序槽位启动处理流。"""

        resolved, model = _resolve_sample_timeseries(self._sample, source)

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
        """执行 one-shot 处理流程。"""

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
        except Exception as exc:
            return make_operation_result(
                action="preprocess",
                success=False,
                message=f"处理失败: {exc}",
                value=self._sample,
                error=exc,
            )


class _SampleSpectrumNamespace:
    """单样本频谱分组。"""

    def __init__(self, sample: "SampleBase") -> None:
        self._sample = sample

    def freqspec(self, **kwargs: Any) -> "OperationResult[SampleBase]":
        kwargs.pop("source", None)
        return self._sample.calc_freqspec(**kwargs)


class _SampleResponseNamespace:
    """单样本响应谱分组。"""

    def __init__(self, sample: "SampleBase") -> None:
        self._sample = sample

    def respspec(self, **kwargs: Any) -> "OperationResult[SampleBase]":
        kwargs.pop("source", None)
        return self._sample.calc_respspec(**kwargs)


class _SampleEvaluateNamespace:
    """单样本评价分组。"""

    def __init__(self, sample: "SampleBase") -> None:
        self._sample = sample

    def zvl(self, **kwargs: Any) -> "OperationResult[SampleBase]":
        return self._sample.eval_zvl(**kwargs)

    def otovl(self, **kwargs: Any) -> "OperationResult[SampleBase]":
        return self._sample.eval_otovl(**kwargs)

    def fdmvl(self, **kwargs: Any) -> "OperationResult[SampleBase]":
        return self._sample.eval_fdmvl(**kwargs)

    def fpvdv(self, **kwargs: Any) -> "OperationResult[SampleBase]":
        return self._sample.eval_fpvdv(**kwargs)


class _SampleFeatureNamespace:
    """单样本特征分组。"""

    def __init__(self, sample: "SampleBase") -> None:
        self._sample = sample

    def _legacy_pga(self) -> float:
        """返回加速度绝对峰值。"""

        accel = self._sample.get_data_var("accel")
        if accel is None:
            raise ValueError("当前样本没有 accel 槽位数据")
        value = getattr(accel, "absmax", None)
        if value is None:
            raise TypeError("accel 槽位不支持 pga 特征")
        return float(value)

    def _series(self, source: ComputeSource | str | None = None) -> Any:
        _, model = _resolve_sample_timeseries(self._sample, source)
        return model

    def absmax(self, *, source: ComputeSource | str | None = None) -> float:
        """返回时序槽位绝对最大值。"""

        return absmax_feature(self._series(source).get_value())["absmax"]

    def rms(self, *, source: ComputeSource | str | None = None) -> float:
        """返回时序槽位均方根。"""

        return rms_feature(self._series(source).get_value())["rms"]

    def mean(self, *, source: ComputeSource | str | None = None) -> float:
        """返回时序槽位均值。"""

        return mean_feature(self._series(source).get_value())["mean"]

    def std(self, *, source: ComputeSource | str | None = None) -> float:
        """返回时序槽位标准差。"""

        return std_feature(self._series(source).get_value())["std"]

    def crest_factor(self, *, source: ComputeSource | str | None = None) -> float:
        """返回时序槽位峰值因子。"""

        return crest_factor_feature(self._series(source).get_value())["crest_factor"]

    def zero_crossings(self, *, source: ComputeSource | str | None = None) -> int:
        """返回时序槽位零交叉次数。"""

        return zero_crossings_feature(self._series(source).get_value())["zero_crossings"]

    def peak(self, *, source: ComputeSource | str | None = None, **kwargs: Any) -> dict[str, float | int]:
        """返回时序槽位主峰值信息。"""

        return peak_feature(self._series(source).get_value(), **kwargs)

    def peaks(self, *, source: ComputeSource | str | None = None, **kwargs: Any) -> dict[str, Any]:
        """返回时序槽位多峰检测结果。"""

        return peaks_feature(self._series(source).get_value(), **kwargs)

    def envelope(self, *, source: ComputeSource | str | None = None) -> dict[str, Any]:
        """返回时序槽位包络序列。"""

        return envelope_feature(self._series(source).get_value())

    def band_rms(
        self,
        *,
        fs: float,
        center_freq: float,
        octave: float = 1.0 / 3.0,
        source: ComputeSource | str | None = None,
    ) -> float:
        """返回时序槽位指定倍频带的均方根值。"""

        return band_rms_feature(
            self._series(source).get_value(),
            fs=fs,
            center_freq=center_freq,
            octave=octave,
        )["band_rms"]


class _SamplePlanNamespace:
    """单样本计划分组。"""

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


class SampleComputeNamespace:
    """SampleBase 的统一计算入口。"""

    def __init__(self, sample: "SampleBase") -> None:
        self._sample = sample
        self.process = _SampleProcessNamespace(sample)
        self.spectrum = _SampleSpectrumNamespace(sample)
        self.response = _SampleResponseNamespace(sample)
        self.evaluate = _SampleEvaluateNamespace(sample)
        self.feature = _SampleFeatureNamespace(sample)
        self.plan = _SamplePlanNamespace()

    def available(self) -> tuple[ComputeOperation, ...]:
        """返回当前样本可执行的能力列表。"""

        operations: list[ComputeOperation] = []
        if any(self._sample.get_data_var(name) is not None for name in _time_series_slots(self._sample)):
            operations.extend(
                (
                    ComputeOperation.PROCESS,
                    ComputeOperation.SPECTRUM,
                    ComputeOperation.FEATURE,
                )
            )
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
        """判断当前样本是否支持某项能力。"""

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
            return _normalize_source(source) in {None, ComputeSource.ACCEL.value}
        if normalized is ComputeOperation.SPECTRUM:
            try:
                _resolve_sample_timeseries(self._sample, source)
            except Exception:
                return False
            return True
        return True

    def run(self, operation: ComputeOperation | str, **kwargs: Any) -> Any:
        """按统一枚举调度样本计算。"""

        normalized = ComputeOperation(str(operation))
        if normalized is ComputeOperation.PROCESS:
            return self.process.pipeline(**kwargs)
        if normalized is ComputeOperation.SPECTRUM:
            return self.spectrum.freqspec(**kwargs)
        if normalized is ComputeOperation.RESPONSE:
            return self.response.respspec(**kwargs)
        if normalized is ComputeOperation.EVALUATE_ZVL:
            return self.evaluate.zvl(**kwargs)
        if normalized is ComputeOperation.EVALUATE_OTOVL:
            return self.evaluate.otovl(**kwargs)
        if normalized is ComputeOperation.EVALUATE_FDMVL:
            return self.evaluate.fdmvl(**kwargs)
        if normalized is ComputeOperation.EVALUATE_FPVDV:
            return self.evaluate.fpvdv(**kwargs)
        if normalized is ComputeOperation.FEATURE:
            return self.feature.absmax()
        raise ValueError(f"不支持的计算操作: {normalized}")

    def flow(self, *, source: ComputeSource | str | None = None) -> ComputeFlow:
        """以当前样本启动处理流。"""

        return self.process.flow(source=source)

    def run_plan(
        self,
        plan: ComputePlan,
        *,
        overwrite: bool = False,
        strict: bool | None = None,
    ) -> "OperationResult[SampleBase]":
        """按顺序执行计算计划。"""

        from .samples.batch import make_operation_result

        try:
            for step in plan.steps:
                source = step.source or plan.default_source
                if step.group == "process":
                    self.process.pipeline(source=source, replace=True, strict=strict, **step.params)
                    continue
                if step.group == "spectrum":
                    self.spectrum.freqspec(source=source or "accel", overwrite=overwrite, **step.params)
                    continue
                if step.group == "response":
                    self.response.respspec(overwrite=overwrite, **step.params)
                    continue
                if step.group == "evaluate":
                    runner = getattr(self.evaluate, step.method)
                    runner(overwrite=overwrite, **step.params)
                    continue
                raise ValueError(f"不支持的计划步骤分组: {step.group}")
            return make_operation_result(
                action="run_plan",
                success=True,
                message=f"计划 '{plan.name}' 执行完成",
                value=self._sample,
            )
        except Exception as exc:
            return make_operation_result(
                action="run_plan",
                success=False,
                message=f"计划 '{plan.name}' 执行失败: {exc}",
                value=self._sample,
                error=exc,
            )


class _SampleSetProcessNamespace:
    """样本集处理分组。"""

    def __init__(self, sample_set: "SampleSetBase[Any]") -> None:
        self._sample_set = sample_set

    def flow(self) -> ComputeFlow:
        """以当前样本集启动批量处理流。"""

        return ComputeFlow(_result=self._sample_set)

    def pipeline(self, **kwargs: Any) -> "BatchOperationReport[Any]":
        return self._sample_set._batch_process_pipeline(**kwargs)


class _SampleSetSpectrumNamespace:
    def __init__(self, sample_set: "SampleSetBase[Any]") -> None:
        self._sample_set = sample_set

    def freqspec(self, **kwargs: Any) -> "BatchOperationReport[Any]":
        return self._sample_set.calc_freqspec(**kwargs)


class _SampleSetResponseNamespace:
    def __init__(self, sample_set: "SampleSetBase[Any]") -> None:
        self._sample_set = sample_set

    def respspec(self, **kwargs: Any) -> "BatchOperationReport[Any]":
        return self._sample_set.calc_respspec(**kwargs)


class _SampleSetEvaluateNamespace:
    def __init__(self, sample_set: "SampleSetBase[Any]") -> None:
        self._sample_set = sample_set

    def zvl(self, **kwargs: Any) -> "BatchOperationReport[Any]":
        return self._sample_set.eval_zvl(**kwargs)

    def otovl(self, **kwargs: Any) -> "BatchOperationReport[Any]":
        return self._sample_set.eval_otovl(**kwargs)

    def fdmvl(self, **kwargs: Any) -> "BatchOperationReport[Any]":
        return self._sample_set.eval_fdmvl(**kwargs)

    def fpvdv(self, **kwargs: Any) -> "BatchOperationReport[Any]":
        return self._sample_set.eval_fpvdv(**kwargs)


class _SampleSetPlanNamespace:
    def create(
        self,
        *,
        name: str,
        steps: Iterable[ComputeStep],
        default_source: ComputeSource | str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> ComputePlan:
        return ComputePlan(
            name=name,
            steps=tuple(steps),
            default_source=default_source,
            metadata=dict(metadata or {}),
        )


class SampleSetComputeNamespace:
    """SampleSetBase 的统一计算入口。"""

    def __init__(self, sample_set: "SampleSetBase[Any]") -> None:
        self._sample_set = sample_set
        self.process = _SampleSetProcessNamespace(sample_set)
        self.spectrum = _SampleSetSpectrumNamespace(sample_set)
        self.response = _SampleSetResponseNamespace(sample_set)
        self.evaluate = _SampleSetEvaluateNamespace(sample_set)
        self.plan = _SampleSetPlanNamespace()

    def available(self) -> tuple[ComputeOperation, ...]:
        """返回当前样本集中至少一个样本可执行的计算操作。"""

        operations: list[ComputeOperation] = []
        for sample in self._sample_set.values():
            operations.extend(sample.compute.available())
        return tuple(dict.fromkeys(operations))

    def supports(self, operation: ComputeOperation | str, *, source: ComputeSource | str | None = None) -> bool:
        """判断样本集中是否存在可执行指定操作的样本。"""

        try:
            normalized = ComputeOperation(str(operation))
        except ValueError:
            return False
        return any(sample.compute.supports(normalized, source=source) for sample in self._sample_set.values())

    def run(self, operation: ComputeOperation | str, **kwargs: Any) -> Any:
        """按统一调度入口执行批量计算操作。"""

        normalized = ComputeOperation(str(operation))
        if normalized is ComputeOperation.PROCESS:
            return self.process.pipeline(**kwargs)
        if normalized is ComputeOperation.SPECTRUM:
            return self.spectrum.freqspec(**kwargs)
        if normalized is ComputeOperation.RESPONSE:
            return self.response.respspec(**kwargs)
        if normalized is ComputeOperation.EVALUATE_ZVL:
            return self.evaluate.zvl(**kwargs)
        if normalized is ComputeOperation.EVALUATE_OTOVL:
            return self.evaluate.otovl(**kwargs)
        if normalized is ComputeOperation.EVALUATE_FDMVL:
            return self.evaluate.fdmvl(**kwargs)
        if normalized is ComputeOperation.EVALUATE_FPVDV:
            return self.evaluate.fpvdv(**kwargs)
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
    """按模型自己的命名协议导出序列表。"""

    frame = model.to_series_frame()
    if not isinstance(frame, pd.DataFrame):
        raise TypeError(f"{type(model).__name__} 的序列导出结果必须是 DataFrame")
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
