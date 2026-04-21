"""第二轮真实接入预留的 facade 协议。"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol


class ImportFacade(Protocol):
    """导入 facade 协议占位。"""

    def available_actions(self) -> tuple[str, ...]:
        """返回导入 facade 支持的动作名。"""


class ProcessingFacade(Protocol):
    """处理 facade 协议占位。"""

    def available_actions(self) -> tuple[str, ...]:
        """返回处理 facade 支持的动作名。"""


class PlottingFacade(Protocol):
    """绘图 facade 协议占位。"""

    def available_actions(self) -> tuple[str, ...]:
        """返回绘图 facade 支持的动作名。"""


class ExportFacade(Protocol):
    """工程导出 facade 协议占位。"""

    def available_actions(self) -> tuple[str, ...]:
        """返回导出 facade 支持的动作名。"""

    def default_output_dir(self) -> Path:
        """返回默认导出目录。"""
