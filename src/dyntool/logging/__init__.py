"""AdvDynTool 正式日志模块。"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from .config import LoggingConfig
from .provider import LogProvider
from .types import LogContext, LoggingMode
from . import api as _api


def build_log_context(
    *,
    module: str | None = None,
    action: str | None = None,
    sample_id: str | None = None,
    sample_set_id: str | None = None,
) -> LogContext:
    """构造日志上下文。"""

    return _api.build_log_context(
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
    """应用日志配置。"""

    return _api.configure_logging(
        config=config,
        provider=provider,
        provider_options=provider_options,
        mode=mode,
        log_file=log_file,
        log_dir=log_dir,
        level=level,
        mirror_to_console=mirror_to_console,
        max_bytes=max_bytes,
        backup_count=backup_count,
        fmt=fmt,
        datefmt=datefmt,
    )


def get_logger(
    name: str | None = None,
    *,
    context: LogContext | None = None,
) -> logging.Logger | logging.LoggerAdapter[logging.Logger]:
    """获取 logger。"""

    return _api.get_logger(name, context=context)


def available_providers() -> tuple[str, ...]:
    """返回可用 provider 名称。"""

    return _api.available_providers()


def get_active_provider_name() -> str:
    """返回当前 provider 名称。"""

    return _api.get_active_provider_name()


def get_log_provider() -> LogProvider:
    """返回当前日志 provider。"""

    return _api.get_log_provider()


def register_log_provider(name: str, factory) -> None:
    """注册 provider。"""

    _api.register_log_provider(name, factory)


def use_log_provider(name: str, *, config: LoggingConfig | None = None) -> LogProvider:
    """切换 provider。"""

    return _api.use_log_provider(name, config=config)


__all__ = [
    "LogContext",
    "LogProvider",
    "LoggingConfig",
    "LoggingMode",
    "available_providers",
    "build_log_context",
    "configure_logging",
    "get_active_provider_name",
    "get_log_provider",
    "get_logger",
    "register_log_provider",
    "use_log_provider",
]

globals().pop("provider", None)
