"""规范样本与样本集工作流辅助函数。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

from .batch import BatchOperationReport, OperationResult, _recoverable_io_error, make_operation_result
from .commands import VibEvalCommand

if TYPE_CHECKING:
    from .base import SampleBaseModel
    from .sets import SampleSetBase


def _reject_removed_force_argument(kwargs: dict[str, Any]) -> None:
    """拒绝历史 `force` 参数。"""

    if "force" in kwargs:
        raise TypeError("force 参数已移除，请使用 overwrite")


def evaluate_sample(
    sample: "SampleBaseModel",
    command: VibEvalCommand,
    **kwargs: Any,
) -> OperationResult[Any]:
    """对单个样本执行规范评价。

    Args:
        sample: 待评价的样本对象。
        command: 评价命令枚举。
        **kwargs: 支持键包括 `overwrite`、`freq_range`、`weight_type`、
            `time_windows`、`nsup`、`calc_unit_system` 与
            `output_unit_system`。

    Returns:
        单样本操作结果对象。

    Raises:
        ValueError: 评价命令不受支持。
    """

    _reject_removed_force_argument(kwargs)
    if command is VibEvalCommand.ZVL:
        return _evaluate_zvl(sample, **kwargs)
    if command is VibEvalCommand.OTOVL:
        return _evaluate_otovl(sample, **kwargs)
    if command is VibEvalCommand.FDMVL:
        return _evaluate_fdmvl(sample, **kwargs)
    if command is VibEvalCommand.FPVDV:
        return _evaluate_fpvdv(sample, **kwargs)
    raise ValueError(f"不支持的评价命令: {command}")


def evaluate_sample_set(
    sample_set: "SampleSetBase[Any]",
    command: VibEvalCommand,
    *,
    overwrite: bool = False,
    strict: bool | None = None,
    uid: str | None = None,
    uids: list[str] | None = None,
    filter: Callable[[Any], bool] | None = None,
    **kwargs: Any,
) -> BatchOperationReport[Any]:
    """对样本集执行规范评价。

    Args:
        sample_set: 待评价的样本集对象。
        command: 评价命令枚举。
        overwrite: 是否覆盖已有结果。
        strict: 是否覆盖样本集严格模式。
        uid: 仅处理单个样本 UID。
        uids: 处理多个样本 UID。
        filter: 样本过滤函数。
        **kwargs: 支持键包括 `freq_range`、`weight_type`、`time_windows`、
            `nsup`、`calc_unit_system` 与 `output_unit_system`。

    Returns:
        样本集批量操作报告对象。
    """

    _reject_removed_force_argument(dict(kwargs))
    return sample_set._batch_vibeval(
        command,
        overwrite=overwrite,
        strict=strict,
        uid=uid,
        uids=uids,
        filter=filter,
        **kwargs,
    )


def evaluate_sample_set_all(
    sample_set: "SampleSetBase[Any]",
    *,
    overwrite: bool = False,
    strict: bool | None = None,
    uid: str | None = None,
    uids: list[str] | None = None,
    filter: Callable[[Any], bool] | None = None,
    **kwargs: Any,
) -> None:
    """对样本集执行全部内置评价。

    Args:
        sample_set: 待评价的样本集对象。
        overwrite: 是否覆盖已有结果。
        strict: 是否覆盖样本集严格模式。
        uid: 仅处理单个样本 UID。
        uids: 处理多个样本 UID。
        filter: 样本过滤函数。
        **kwargs: 支持键包括 `freq_range`、`weight_type`、`time_windows`、
            `nsup`、`calc_unit_system` 与 `output_unit_system`。
    """

    _reject_removed_force_argument(kwargs)
    evaluate_sample_set(
        sample_set,
        VibEvalCommand.ZVL,
        overwrite=overwrite,
        strict=strict,
        uid=uid,
        uids=uids,
        filter=filter,
        **kwargs,
    )
    evaluate_sample_set(
        sample_set,
        VibEvalCommand.OTOVL,
        overwrite=overwrite,
        strict=strict,
        uid=uid,
        uids=uids,
        filter=filter,
        **kwargs,
    )
    evaluate_sample_set(
        sample_set,
        VibEvalCommand.FDMVL,
        overwrite=overwrite,
        strict=strict,
        uid=uid,
        uids=uids,
        filter=filter,
        **kwargs,
    )
    evaluate_sample_set(
        sample_set,
        VibEvalCommand.FPVDV,
        overwrite=overwrite,
        strict=strict,
        uid=uid,
        uids=uids,
        filter=filter,
        **kwargs,
    )


def preprocess_sample(sample: "SampleBaseModel", **kwargs: Any) -> OperationResult[Any]:
    """对单个样本执行规范预处理。

    Args:
        sample: 待处理的样本对象。
        **kwargs: 支持键包括 `truncate_range`、`baseline`、`baseline_order`、
            `highpass`、`lowpass`、`bandpass` 与 `filter_order`。

    Returns:
        单样本操作结果对象。
    """

    action = "preprocess"
    accel = getattr(sample, "accel", None)
    if accel is None:
        return make_operation_result(action=action, success=False, message="无加速度数据", value=sample)
    try:
        processed = accel
        truncate_range = kwargs.get("truncate_range")
        baseline = kwargs.get("baseline")
        baseline_order = kwargs.get("baseline_order", 1)
        highpass = kwargs.get("highpass")
        lowpass = kwargs.get("lowpass")
        bandpass = kwargs.get("bandpass")
        filter_order = kwargs.get("filter_order", 4)
        if truncate_range is not None:
            processed = processed.truncate(*truncate_range)
        if baseline is not None:
            processed = processed.baseline_correct(method=baseline, order=baseline_order)
        if highpass is not None:
            processed = processed.filter_highpass(highpass, order=filter_order)
        if lowpass is not None:
            processed = processed.filter_lowpass(lowpass, order=filter_order)
        if bandpass is not None:
            processed = processed.filter_bandpass(
                bandpass[0],
                f_high=bandpass[1],
                order=filter_order,
            )
        sample.update_data(accel=processed)
        return make_operation_result(action=action, success=True, message="处理完成", value=sample)
    except Exception as exc:
        return make_operation_result(
            action=action,
            success=False,
            message=f"预处理失败: {exc}",
            value=sample,
            error=exc,
        )


def preprocess_sample_set(
    sample_set: "SampleSetBase[Any]",
    *,
    strict: bool | None = None,
    uid: str | None = None,
    uids: list[str] | None = None,
    filter: Callable[[Any], bool] | None = None,
    **kwargs: Any,
) -> BatchOperationReport[Any]:
    """对样本集执行规范预处理。

    Args:
        sample_set: 待处理的样本集对象。
        strict: 是否覆盖样本集严格模式。
        uid: 仅处理单个样本 UID。
        uids: 处理多个样本 UID。
        filter: 样本过滤函数。
        **kwargs: 支持键包括 `truncate_range`、`baseline`、`baseline_order`、
            `highpass`、`lowpass`、`bandpass` 与 `filter_order`。

    Returns:
        样本集批量操作报告对象。

    Raises:
        OSError: 严格模式下任一样本处理失败时由可恢复 I/O 错误包装抛出。
    """

    report = BatchOperationReport[Any](
        action="preprocess",
        strict=sample_set.strict if strict is None else strict,
    )
    items = sample_set._select_samples(uid=uid, uids=uids, filter=filter)
    report.stats.valid_samples = sum(1 for _, sample in items if getattr(sample, "accel", None) is not None)
    recoverable_io_error = _recoverable_io_error()
    for item_uid, sample in items:
        result = preprocess_sample(sample, **kwargs)
        report.add(item_uid, result)
        if report.strict and result.status == "failed":
            sample_set._last_operation_report = report
            raise recoverable_io_error(f"批处理失败: {item_uid}") from result.error
    sample_set._last_operation_report = report
    return report


def _evaluate_zvl(sample: "SampleBaseModel", **kwargs: Any) -> OperationResult[Any]:
    """执行 Z 振级评价。"""

    return _run_sample_eval(sample, attr_name="zvl", runner_name="eval_zvl", **kwargs)


def _evaluate_otovl(sample: "SampleBaseModel", **kwargs: Any) -> OperationResult[Any]:
    """执行 1/3 倍频程振级评价。"""

    return _run_sample_eval(sample, attr_name="otovl", runner_name="eval_otovl", **kwargs)


def _evaluate_fdmvl(sample: "SampleBaseModel", **kwargs: Any) -> OperationResult[Any]:
    """执行分频最大振级评价。"""

    return _run_sample_eval(sample, attr_name="fdmvl", runner_name="eval_fdmvl", **kwargs)


def _evaluate_fpvdv(sample: "SampleBaseModel", **kwargs: Any) -> OperationResult[Any]:
    """执行四次方振动剂量值评价。"""

    return _run_sample_eval(sample, attr_name="fpvdv", runner_name="eval_fpvdv", **kwargs)


def _run_sample_eval(
    sample: "SampleBaseModel",
    *,
    attr_name: str,
    runner_name: str,
    overwrite: bool = False,
    **kwargs: Any,
) -> OperationResult[Any]:
    """执行单个评价动作。

    Args:
        sample: 待评价的样本对象。
        attr_name: 评价结果属性名，例如 `otovl`。
        runner_name: 加速度数据模型上的执行方法名。
        overwrite: 是否覆盖已有结果。
        **kwargs: 透传给具体评价方法的命名参数。

    Returns:
        单样本操作结果对象。
    """

    action = attr_name
    accel = getattr(sample, "accel", None)
    run_action = getattr(sample, "_run_accel_action", None)
    if accel is None:
        return make_operation_result(action=action, success=False, message="无加速度数据", value=sample)
    if run_action is None:
        raise TypeError(f"{type(sample).__name__} 不支持规范振动评价")
    runner = getattr(accel, runner_name)
    return run_action(
        attr_name=attr_name,
        overwrite=overwrite,
        runner=lambda: runner(**kwargs),
        use_eval_formatter=True,
    )


__all__ = [
    "evaluate_sample",
    "evaluate_sample_set",
    "evaluate_sample_set_all",
    "preprocess_sample",
    "preprocess_sample_set",
]
