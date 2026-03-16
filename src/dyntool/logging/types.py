"""日志模块公开类型定义。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class LoggingMode(StrEnum):
    """日志输出模式。"""

    CONSOLE_ONLY = "console_only"
    SINGLE_FILE = "single_file"
    DIRECTORY = "directory"


@dataclass(slots=True, frozen=True)
class LogContext:
    """日志上下文。"""

    module: str | None = None
    action: str | None = None
    sample_id: str | None = None
    sample_set_id: str | None = None

    def to_extra(self) -> dict[str, str]:
        """转换为 logging extra 字段。"""

        return {
            key: value
            for key, value in {
                "ctx_module": self.module,
                "ctx_action": self.action,
                "ctx_sample_id": self.sample_id,
                "ctx_sample_set_id": self.sample_set_id,
            }.items()
            if value is not None
        }


__all__ = ["LogContext", "LoggingMode"]
