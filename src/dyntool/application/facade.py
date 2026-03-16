"""顶层轻量工具入口。"""

from __future__ import annotations

from .. import logging as logging_api
from . import options as option_types
from .resource_service import ResourceService


class DynTool:
    """仅保留资源与配置入口的轻量门面。"""

    def __init__(
        self,
        *,
        log_provider: object | None = None,
        logging_config: object | None = None,
    ) -> None:
        self.resource = ResourceService()
        self.options = option_types
        if logging_config is not None:
            logging_api.configure_logging(config=logging_config)
        elif log_provider is not None:
            logging_api.get_log_provider().configure(log_provider.config)


__all__ = ["DynTool"]
