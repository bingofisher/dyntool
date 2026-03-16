"""日志模块正式公开函数。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .config import LoggingConfig
from .provider import (
    _warn_default_provider_fallback_once,
    available_providers,
    get_active_provider_name,
    get_log_provider,
    get_logger,
    register_log_provider,
    use_log_provider,
)
from .types import LogContext, LoggingMode


def build_log_context(
    *,
    module: str | None = None,
    action: str | None = None,
    sample_id: str | None = None,
    sample_set_id: str | None = None,
) -> LogContext:
    """构造日志上下文。"""

    return LogContext(
        module=module,
        action=action,
        sample_id=sample_id,
        sample_set_id=sample_set_id,
    )


def configure_logging(
    config: LoggingConfig | None = None,
    *,
    provider: str | None = None,
    provider_options: dict[str, Any] | None = None,
    mode: LoggingMode | None = None,
    log_file: str | Path | None = None,
    log_dir: str | Path | None = None,
    level: str | None = None,
    mirror_to_console: bool | None = None,
    max_bytes: int | None = None,
    backup_count: int | None = None,
    fmt: str | None = None,
    datefmt: str | None = None,
) -> LoggingConfig:
    """应用日志配置并返回生效配置。"""

    effective = config or LoggingConfig()
    if provider is not None:
        effective.provider = provider
    if provider_options is not None:
        effective.provider_options = dict(provider_options)
    if mode is not None:
        effective.mode = mode
    if log_file is not None:
        effective.log_file = Path(log_file)
    if log_dir is not None:
        effective.log_dir = Path(log_dir)
    if level is not None:
        effective.level = level
    if mirror_to_console is not None:
        effective.mirror_to_console = mirror_to_console
    if max_bytes is not None:
        effective.max_bytes = max_bytes
    if backup_count is not None:
        effective.backup_count = backup_count
    if fmt is not None:
        effective.fmt = fmt
    if datefmt is not None:
        effective.datefmt = datefmt
    effective.normalize()
    if provider is None and effective.provider == "loguru" and "loguru" not in available_providers():
        _warn_default_provider_fallback_once()
        effective.provider = "stdlib"
    if effective.provider != get_active_provider_name():
        return use_log_provider(effective.provider, config=effective).config
    active_provider = get_log_provider()
    active_provider.configure(effective)
    return active_provider.config


__all__ = [
    "available_providers",
    "build_log_context",
    "configure_logging",
    "get_active_provider_name",
    "get_log_provider",
    "get_logger",
    "register_log_provider",
    "use_log_provider",
]
