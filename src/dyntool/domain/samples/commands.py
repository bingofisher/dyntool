"""样本标准评价命令定义。"""

from __future__ import annotations

from enum import StrEnum
from typing import Any


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
    sample: object,
    command: VibEvalCommand,
    *,
    force: bool,
    **kwargs: Any,
) -> tuple[bool, str]:
    """执行显式评价命令。"""

    from .workflows import evaluate_sample

    return evaluate_sample(sample, command, force=force, **kwargs)


__all__ = ["VibEvalCommand", "run_vib_eval"]
