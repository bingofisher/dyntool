"""日志模块内部配置。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .types import LoggingMode


@dataclass(slots=True)
class LoggingConfig:
    """日志配置对象。"""

    provider: str = "loguru"
    provider_options: dict[str, Any] = field(default_factory=dict)
    mode: LoggingMode = LoggingMode.CONSOLE_ONLY
    level: str = "INFO"
    log_file: Path | None = None
    log_dir: Path | None = None
    mirror_to_console: bool = True
    fmt: str = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    datefmt: str = "%Y-%m-%d %H:%M:%S"
    max_bytes: int = 0
    backup_count: int = 0

    def normalize(self) -> "LoggingConfig":
        """补齐默认路径并返回自身。"""

        self.provider = str(self.provider).strip().lower() or "loguru"
        self.provider_options = dict(self.provider_options)
        if self.mode is LoggingMode.SINGLE_FILE and self.log_file is None:
            self.log_file = Path("logs") / "dyntool.log"
        if self.mode is LoggingMode.DIRECTORY and self.log_dir is None:
            self.log_dir = Path("logs")
        return self


__all__ = ["LoggingConfig"]
