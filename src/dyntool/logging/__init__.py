"""AdvDynTool 正式日志模块。"""

from __future__ import annotations

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


def configure_logging(*args: object, **kwargs: object) -> LoggingConfig:
    """应用日志配置。"""

    return _api.configure_logging(*args, **kwargs)


def get_logger(*args: object, **kwargs: object):
    """获取 logger。"""

    return _api.get_logger(*args, **kwargs)


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
