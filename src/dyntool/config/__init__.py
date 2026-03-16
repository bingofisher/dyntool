"""正式配置模块。"""

from __future__ import annotations

from .core import (
    Config,
    DictFlattener,
    PathLike,
    VariableReplacer,
    deep_update,
    load_config,
    read_config_file,
)

__all__ = [
    "Config",
    "DictFlattener",
    "PathLike",
    "VariableReplacer",
    "deep_update",
    "load_config",
    "read_config_file",
]
