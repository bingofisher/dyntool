"""样本标准评价命令定义。"""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .batch import OperationResult
    from .base import SampleBaseModel


class VibEvalCommand(StrEnum):
    """振动评价标准命令。"""

    ZVL = "zvl"
    OTOVL = "otovl"
    FDMVL = "fdmvl"
    FPVDV = "fpvdv"

    @property
    def label(self) -> str:
        """返回大写标签。"""

        return self.value.upper()


def run_vib_eval(
    sample: "SampleBaseModel",
    command: VibEvalCommand,
    *,
    overwrite: bool,
    **options: Any,
) -> OperationResult[Any]:
    """执行显式评价命令。

    Args:
        sample: 待评价的样本对象。
        command: 显式评价命令枚举。
        overwrite: 是否允许覆盖已有评价结果。
        **options: 评价命令附加参数。常见键包括 `freq_range`、`weight_type`、
            `time_windows`、`nsup`、`calc_unit_system`、`output_unit_system`。

    Returns:
        单样本操作结果对象。
    """

    from .workflows import evaluate_sample

    return evaluate_sample(sample, command, overwrite=overwrite, **options)


__all__ = ["VibEvalCommand", "run_vib_eval"]
