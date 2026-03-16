"""规范样本和样本集工作流辅助函数。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

from .commands import VibEvalCommand

if TYPE_CHECKING:
    from .sets import SampleSetBase


def evaluate_sample(
    sample: object,
    command: VibEvalCommand,
    **kwargs: Any,
) -> tuple[bool, str]:
    """对单个样本执行规范评价。"""

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
    uid: str | None = None,
    uids: list[str] | None = None,
    filter: Callable[[Any], bool] | None = None,
    **kwargs: object,
) -> dict[str, tuple[bool, str]] | tuple[bool, str]:
    """对样本集执行规范评价。"""

    return sample_set._batch_vibeval(  # type: ignore[attr-defined]
        command,
        overwrite=overwrite,
        uid=uid,
        uids=uids,
        filter=filter,
        **kwargs,
    )


def evaluate_sample_set_all(
    sample_set: "SampleSetBase[Any]",
    *,
    overwrite: bool = False,
    uid: str | None = None,
    uids: list[str] | None = None,
    filter: Callable[[Any], bool] | None = None,
    **kwargs: Any,
) -> None:
    """对样本集执行全部规范评价。"""

    evaluate_sample_set(
        sample_set,
        VibEvalCommand.ZVL,
        overwrite=overwrite,
        uid=uid,
        uids=uids,
        filter=filter,
        **kwargs,
    )
    evaluate_sample_set(
        sample_set,
        VibEvalCommand.OTOVL,
        overwrite=overwrite,
        uid=uid,
        uids=uids,
        filter=filter,
        **kwargs,
    )
    evaluate_sample_set(
        sample_set,
        VibEvalCommand.FDMVL,
        overwrite=overwrite,
        uid=uid,
        uids=uids,
        filter=filter,
        **kwargs,
    )
    evaluate_sample_set(
        sample_set,
        VibEvalCommand.FPVDV,
        overwrite=overwrite,
        uid=uid,
        uids=uids,
        filter=filter,
        **kwargs,
    )


def preprocess_sample(sample: object, **kwargs: Any) -> tuple[bool, str]:
    """对单个样本执行规范预处理。"""

    accel = getattr(sample, "accel", None)
    if accel is None:
        return False, "无加速度数据"
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
            processed = processed.baseline_correct(
                method=baseline,
                order=baseline_order,
            )
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
        setattr(sample, "accel", processed)
        return True, "处理完成"
    except Exception as exc:
        return False, f"预处理失败: {exc}"


def preprocess_sample_set(
    sample_set: "SampleSetBase[Any]",
    *,
    uid: str | None = None,
    uids: list[str] | None = None,
    filter: Callable[[Any], bool] | None = None,
    **kwargs: Any,
) -> dict[str, tuple[bool, str]] | tuple[bool, str]:
    """对样本集执行规范预处理。"""

    results: dict[str, tuple[bool, str]] = {}
    for item_uid, sample in sample_set._select_samples(  # type: ignore[attr-defined]
        uid=uid,
        uids=uids,
        filter=filter,
    ):
        results[item_uid] = preprocess_sample(sample, **kwargs)
    if uid is not None:
        return results[uid]
    return results


def _evaluate_zvl(sample: object, **kwargs: Any) -> tuple[bool, str]:
    return _run_sample_eval(sample, attr_name="zvl", runner_name="eval_zvl", **kwargs)


def _evaluate_otovl(sample: object, **kwargs: Any) -> tuple[bool, str]:
    return _run_sample_eval(
        sample,
        attr_name="otovl",
        runner_name="eval_otovl",
        **kwargs,
    )


def _evaluate_fdmvl(sample: object, **kwargs: Any) -> tuple[bool, str]:
    return _run_sample_eval(
        sample,
        attr_name="fdmvl",
        runner_name="eval_fdmvl",
        **kwargs,
    )


def _evaluate_fpvdv(sample: object, **kwargs: Any) -> tuple[bool, str]:
    return _run_sample_eval(
        sample,
        attr_name="fpvdv",
        runner_name="eval_fpvdv",
        **kwargs,
    )


def _run_sample_eval(
    sample: object,
    *,
    attr_name: str,
    runner_name: str,
    force: bool = False,
    overwrite: bool | None = None,
    **kwargs: Any,
) -> tuple[bool, str]:
    accel = getattr(sample, "accel", None)
    run_action = getattr(sample, "_run_accel_action", None)
    resolve_overwrite = getattr(sample, "_resolve_overwrite", None)
    if accel is None:
        return False, "无加速度数据"
    if run_action is None or resolve_overwrite is None:
        raise TypeError(f"{type(sample).__name__} 不支持规范振动评价")
    runner = getattr(accel, runner_name)
    return run_action(
        attr_name=attr_name,
        overwrite=resolve_overwrite(force=force, overwrite=overwrite),
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
