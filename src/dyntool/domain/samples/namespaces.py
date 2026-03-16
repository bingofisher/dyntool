"""Namespace wrappers for sample and sample-set workflows."""

from __future__ import annotations

from typing import Any

from ...compute.flow import ComputeFlow
from .commands import VibEvalCommand
from .workflows import (
    evaluate_sample,
    evaluate_sample_set,
    evaluate_sample_set_all,
    preprocess_sample,
    preprocess_sample_set,
)


class SampleProcessingNamespace:
    """Canonical processing namespace for a single sample."""

    def __init__(self, sample: object) -> None:
        self._sample = sample

    def preprocess_accel(self, **kwargs: Any) -> tuple[bool, str]:
        """对当前样本执行加速度预处理工作流。"""
        return preprocess_sample(self._sample, **kwargs)

    def flow(self) -> ComputeFlow:
        """返回以当前样本为起点的计算流对象。"""
        method = getattr(self._sample, "flow", None)
        if method is None:
            raise TypeError(f"{type(self._sample).__name__} 不支持 flow()")
        return method()


class SampleEvaluationNamespace:
    """Canonical evaluation namespace for a single sample."""

    def __init__(self, sample: object) -> None:
        self._sample = sample

    def zvl(self, **kwargs: Any) -> tuple[bool, str]:
        """执行 Z 振级评价命令。"""
        return evaluate_sample(self._sample, VibEvalCommand.ZVL, **kwargs)

    def otovl(self, **kwargs: Any) -> tuple[bool, str]:
        """执行 1/3 倍频程振级评价命令。"""
        return evaluate_sample(self._sample, VibEvalCommand.OTOVL, **kwargs)

    def fdmvl(self, **kwargs: Any) -> tuple[bool, str]:
        """执行分频最大振级评价命令。"""
        return evaluate_sample(self._sample, VibEvalCommand.FDMVL, **kwargs)

    def fpvdv(self, **kwargs: Any) -> tuple[bool, str]:
        """执行四次方振动剂量值评价命令。"""
        return evaluate_sample(self._sample, VibEvalCommand.FPVDV, **kwargs)

    def flow(self) -> ComputeFlow:
        """返回以当前样本为起点的计算流对象。"""
        method = getattr(self._sample, "flow", None)
        if method is None:
            raise TypeError(f"{type(self._sample).__name__} 不支持 flow()")
        return method()


class SampleSetProcessingNamespace:
    """Canonical processing namespace for a sample set."""

    def __init__(self, sample_set: object) -> None:
        self._sample_set = sample_set

    def preprocess_accel(self, **kwargs: Any) -> Any:
        """对样本集批量执行加速度预处理工作流。"""
        return preprocess_sample_set(self._sample_set, **kwargs)

    def batch(self, operation: Any, **kwargs: Any) -> dict[str, Any]:
        """对样本集执行批处理操作并返回逐样本结果。"""
        return self._sample_set.batch(operation, **kwargs)

    def flow(self) -> ComputeFlow:
        """返回以当前样本集为起点的计算流对象。"""
        method = getattr(self._sample_set, "flow", None)
        if method is None:
            raise TypeError(f"{type(self._sample_set).__name__} 不支持 flow()")
        return method()


class SampleSetEvaluationNamespace:
    """Canonical evaluation namespace for a sample set."""

    def __init__(self, sample_set: object) -> None:
        self._sample_set = sample_set

    def zvl(self, **kwargs: Any) -> Any:
        """对样本集批量执行 Z 振级评价。"""
        return evaluate_sample_set(self._sample_set, VibEvalCommand.ZVL, **kwargs)

    def otovl(self, **kwargs: Any) -> Any:
        """对样本集批量执行 1/3 倍频程振级评价。"""
        return evaluate_sample_set(self._sample_set, VibEvalCommand.OTOVL, **kwargs)

    def fdmvl(self, **kwargs: Any) -> Any:
        """对样本集批量执行分频最大振级评价。"""
        return evaluate_sample_set(self._sample_set, VibEvalCommand.FDMVL, **kwargs)

    def fpvdv(self, **kwargs: Any) -> Any:
        """对样本集批量执行四次方振动剂量值评价。"""
        return evaluate_sample_set(self._sample_set, VibEvalCommand.FPVDV, **kwargs)

    def all(self, **kwargs: Any) -> Any:
        """对样本集一次性执行全部内置振动评价命令。"""
        return evaluate_sample_set_all(self._sample_set, **kwargs)

    def flow(self) -> ComputeFlow:
        """返回以当前样本集为起点的计算流对象。"""
        method = getattr(self._sample_set, "flow", None)
        if method is None:
            raise TypeError(f"{type(self._sample_set).__name__} 不支持 flow()")
        return method()


__all__ = [
    "SampleProcessingNamespace",
    "SampleEvaluationNamespace",
    "SampleSetProcessingNamespace",
    "SampleSetEvaluationNamespace",
]
