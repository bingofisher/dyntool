"""样本与样本集工作流命名空间。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

from ...compute.flow import ComputeFlow
from .batch import BatchOperationReport, OperationResult
from .commands import VibEvalCommand
from .workflows import (
    evaluate_sample,
    evaluate_sample_set,
    evaluate_sample_set_all,
    preprocess_sample,
    preprocess_sample_set,
)

if TYPE_CHECKING:
    from .base import SampleBaseModel
    from .sets import SampleSetBase


class SampleProcessingNamespace:
    """单样本处理命名空间。"""

    def __init__(self, sample: "SampleBaseModel") -> None:
        self._sample = sample

    def preprocess_accel(self, **kwargs: Any) -> OperationResult[Any]:
        """对当前样本执行加速度预处理工作流。

        Args:
            **kwargs: 支持键包括 `truncate_range`、`baseline`、`baseline_order`、
                `highpass`、`lowpass`、`bandpass` 与 `filter_order`。

        Returns:
            预处理操作结果对象。成功时 `value` 为当前样本，失败时 `error` 保留异常。
        """

        return preprocess_sample(self._sample, **kwargs)

    def flow(self) -> ComputeFlow:
        """返回以当前样本为起点的计算流对象。"""

        method = getattr(self._sample, "flow", None)
        if method is None:
            raise TypeError(f"{type(self._sample).__name__} 不支持 flow()")
        return method()


class SampleEvaluationNamespace:
    """单样本评价命名空间。"""

    def __init__(self, sample: "SampleBaseModel") -> None:
        self._sample = sample

    def zvl(self, *, overwrite: bool = False, **kwargs: Any) -> OperationResult[Any]:
        """执行 Z 振级评价命令。

        Args:
            overwrite: 是否覆盖已有结果。
            **kwargs: 支持键包括 `freq_range`、`weight_type`、`time_windows`、
                `calc_unit_system` 与 `output_unit_system`。

        Returns:
            单样本评价结果对象。
        """

        return evaluate_sample(self._sample, VibEvalCommand.ZVL, overwrite=overwrite, **kwargs)

    def otovl(self, *, overwrite: bool = False, **kwargs: Any) -> OperationResult[Any]:
        """执行 1/3 倍频程振级评价命令。

        Args:
            overwrite: 是否覆盖已有结果。
            **kwargs: 支持键包括 `freq_range`、`time_windows`、
                `calc_unit_system` 与 `output_unit_system`。

        Returns:
            单样本评价结果对象。
        """

        return evaluate_sample(self._sample, VibEvalCommand.OTOVL, overwrite=overwrite, **kwargs)

    def fdmvl(self, *, overwrite: bool = False, **kwargs: Any) -> OperationResult[Any]:
        """执行分频最大振级评价命令。

        Args:
            overwrite: 是否覆盖已有结果。
            **kwargs: 支持键包括 `freq_range`、`calc_unit_system` 与
                `output_unit_system`。

        Returns:
            单样本评价结果对象。
        """

        return evaluate_sample(self._sample, VibEvalCommand.FDMVL, overwrite=overwrite, **kwargs)

    def fpvdv(self, *, overwrite: bool = False, **kwargs: Any) -> OperationResult[Any]:
        """执行四次方振动剂量值评价命令。

        Args:
            overwrite: 是否覆盖已有结果。
            **kwargs: 支持键包括 `freq_range`、`nsup`、`calc_unit_system` 与
                `output_unit_system`。

        Returns:
            单样本评价结果对象。
        """

        return evaluate_sample(self._sample, VibEvalCommand.FPVDV, overwrite=overwrite, **kwargs)

    def flow(self) -> ComputeFlow:
        """返回以当前样本为起点的计算流对象。"""

        method = getattr(self._sample, "flow", None)
        if method is None:
            raise TypeError(f"{type(self._sample).__name__} 不支持 flow()")
        return method()


class SampleSetProcessingNamespace:
    """样本集处理命名空间。"""

    def __init__(self, sample_set: "SampleSetBase[Any]") -> None:
        self._sample_set = sample_set

    def preprocess_accel(self, **kwargs: Any) -> BatchOperationReport[Any]:
        """对样本集批量执行加速度预处理。

        Args:
            **kwargs: 支持键包括 `strict`、`uid`、`uids`、`filter`、
                `truncate_range`、`baseline`、`baseline_order`、`highpass`、
                `lowpass`、`bandpass` 与 `filter_order`。

        Returns:
            批量操作报告对象。
        """

        return preprocess_sample_set(self._sample_set, **kwargs)

    def batch(self, operation: Callable[[Any], Any], **kwargs: Any) -> dict[str, Any]:
        """对样本集执行通用批处理操作。

        Args:
            operation: 逐样本执行的可调用对象。
            **kwargs: 会按原样传给 `SampleSet.batch()`；该入口当前主要用于内部
                批处理或受控 `extras` 场景，不建议用户依赖未文档化键名。

        Returns:
            以样本 UID 为键、批处理结果为值的映射。
        """

        return self._sample_set.batch(operation, **kwargs)

    def calc_freqspec(self, *, overwrite: bool = False, **kwargs: Any) -> BatchOperationReport[Any]:
        """批量计算频谱结果。

        Args:
            overwrite: 是否覆盖已有 `freqspec`。
            **kwargs: 支持键包括 `uid`、`uids`、`filter`、`strict` 以及底层
                `calc_freqspec()` 支持的计算参数。

        Returns:
            批量操作报告对象。
        """

        return self._sample_set.calc_freqspec(overwrite=overwrite, **kwargs)

    def calc_respspec(self, *, overwrite: bool = False, **kwargs: Any) -> BatchOperationReport[Any]:
        """批量计算反应谱结果。

        Args:
            overwrite: 是否覆盖已有 `respspec`。
            **kwargs: 支持键包括 `uid`、`uids`、`filter`、`strict` 以及底层
                `calc_respspec()` 支持的计算参数。

        Returns:
            批量操作报告对象。
        """

        return self._sample_set.calc_respspec(overwrite=overwrite, **kwargs)

    def flow(self) -> ComputeFlow:
        """返回以当前样本集为起点的计算流对象。"""

        method = getattr(self._sample_set, "flow", None)
        if method is None:
            raise TypeError(f"{type(self._sample_set).__name__} 不支持 flow()")
        return method()


class SampleSetEvaluationNamespace:
    """样本集评价命名空间。"""

    def __init__(self, sample_set: "SampleSetBase[Any]") -> None:
        self._sample_set = sample_set

    def zvl(self, *, overwrite: bool = False, **kwargs: Any) -> BatchOperationReport[Any]:
        """对样本集批量执行 Z 振级评价。

        Args:
            overwrite: 是否覆盖已有结果。
            **kwargs: 支持键包括 `strict`、`uid`、`uids`、`filter`、
                `freq_range`、`weight_type`、`time_windows`、
                `calc_unit_system` 与 `output_unit_system`。

        Returns:
            批量操作报告对象。
        """

        return evaluate_sample_set(self._sample_set, VibEvalCommand.ZVL, overwrite=overwrite, **kwargs)

    def otovl(self, *, overwrite: bool = False, **kwargs: Any) -> BatchOperationReport[Any]:
        """对样本集批量执行 1/3 倍频程振级评价。

        Args:
            overwrite: 是否覆盖已有结果。
            **kwargs: 支持键包括 `strict`、`uid`、`uids`、`filter`、
                `freq_range`、`time_windows`、`calc_unit_system` 与
                `output_unit_system`。

        Returns:
            批量操作报告对象。
        """

        return evaluate_sample_set(self._sample_set, VibEvalCommand.OTOVL, overwrite=overwrite, **kwargs)

    def fdmvl(self, *, overwrite: bool = False, **kwargs: Any) -> BatchOperationReport[Any]:
        """对样本集批量执行分频最大振级评价。

        Args:
            overwrite: 是否覆盖已有结果。
            **kwargs: 支持键包括 `strict`、`uid`、`uids`、`filter`、
                `freq_range`、`calc_unit_system` 与 `output_unit_system`。

        Returns:
            批量操作报告对象。
        """

        return evaluate_sample_set(self._sample_set, VibEvalCommand.FDMVL, overwrite=overwrite, **kwargs)

    def fpvdv(self, *, overwrite: bool = False, **kwargs: Any) -> BatchOperationReport[Any]:
        """对样本集批量执行四次方振动剂量值评价。

        Args:
            overwrite: 是否覆盖已有结果。
            **kwargs: 支持键包括 `strict`、`uid`、`uids`、`filter`、
                `freq_range`、`nsup`、`calc_unit_system` 与
                `output_unit_system`。

        Returns:
            批量操作报告对象。
        """

        return evaluate_sample_set(self._sample_set, VibEvalCommand.FPVDV, overwrite=overwrite, **kwargs)

    def all(self, *, overwrite: bool = False, **kwargs: Any) -> None:
        """对样本集一次性执行全部内置评价命令。

        Args:
            overwrite: 是否覆盖已有结果。
            **kwargs: 支持键包括 `strict`、`uid`、`uids`、`filter` 以及各评价
                命令共用的 `freq_range`、`calc_unit_system` 与
                `output_unit_system`。
        """

        return evaluate_sample_set_all(self._sample_set, overwrite=overwrite, **kwargs)

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
