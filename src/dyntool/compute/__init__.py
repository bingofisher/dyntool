"""Compute layer: reusable signal processing and evaluation algorithms."""

from __future__ import annotations

import importlib
from typing import Any

from .context import ComputeContext
from .flow import ComputeFlow

__all__ = [
    "signals",
    "solvers",
    "metrics",
    "pipelines",
    "results",
    "units",
    "ComputeContext",
    "ComputeFlow",
]


def __getattr__(name: str) -> Any:
    if name in {"signals", "solvers", "metrics", "pipelines", "results", "units"}:
        module = importlib.import_module(f".{name}", __name__)
        globals()[name] = module
        return module
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
