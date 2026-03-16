"""基础设施持久化协议与注册中心。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Protocol, runtime_checkable

from ..domain.constants import DataCategory
from ..domain.runtime.errors import RecoverableIOError
from ..logging import get_logger

logger = get_logger("infrastructure.persistence")


class PersistenceError(Exception):
    """持久化基础异常。"""


class BackendError(PersistenceError):
    """底层后端异常。"""


class SchemaError(PersistenceError):
    """序列化/反序列化结构异常。"""


@runtime_checkable
class DataBackend(Protocol):
    """持久化后端协议。"""

    def save(self, path: Path, model: Any, **options: Any) -> None:
        """保存模型或结构化载荷到目标路径。"""
        ...

    def load(self, path: Path, category: DataCategory | None = None, **options: Any) -> Any:
        """从目标路径加载模型或结构化载荷。"""
        ...

    def inspect_units(self, path: Path, category: DataCategory | None = None, **options: Any) -> dict[str, str]:
        """仅检查持久化对象中的单位映射而不构造完整模型。"""
        ...


@dataclass(slots=True)
class HookContext:
    """before-save/after-load 钩子上下文。"""

    stage: str
    path: Path
    fmt: str
    category: DataCategory | None
    payload: Any
    options: dict[str, Any]


Hook = Callable[[HookContext], Any]

_BACKEND_REGISTRY: dict[str, type[DataBackend]] = {}
_BEFORE_SAVE_HOOKS: list[Hook] = []
_AFTER_LOAD_HOOKS: list[Hook] = []


def register_backend(fmt: str, backend_cls: type[DataBackend]) -> None:
    """注册后端类型。"""

    _BACKEND_REGISTRY[fmt] = backend_cls
    logger.debug("register backend: fmt=%s, backend=%s", fmt, backend_cls.__name__)


def get_backend(fmt: str) -> DataBackend:
    """实例化已注册后端。"""

    if fmt not in _BACKEND_REGISTRY:
        available = ", ".join(sorted(_BACKEND_REGISTRY))
        raise ValueError(f"Unsupported format: {fmt}. Available: {available}")
    return _BACKEND_REGISTRY[fmt]()


def register_before_save(hook: Hook) -> None:
    """注册保存前钩子。"""

    _BEFORE_SAVE_HOOKS.append(hook)


def register_after_load(hook: Hook) -> None:
    """注册加载后钩子。"""

    _AFTER_LOAD_HOOKS.append(hook)


def _run_before_save(path: Path, fmt: str, model: Any, **options: Any) -> Any:
    payload = model
    for hook in _BEFORE_SAVE_HOOKS:
        ctx = HookContext(
            stage="before_save",
            path=path,
            fmt=fmt,
            category=None,
            payload=payload,
            options=options,
        )
        out = hook(ctx)
        if out is not None:
            payload = out
    return payload


def _run_after_load(path: Path, fmt: str, category: DataCategory | None, raw: Any, **options: Any) -> Any:
    payload = raw
    for hook in _AFTER_LOAD_HOOKS:
        ctx = HookContext(
            stage="after_load",
            path=path,
            fmt=fmt,
            category=category,
            payload=payload,
            options=options,
        )
        out = hook(ctx)
        if out is not None:
            payload = out
    return payload


def save(path: Path | str, model: Any, *, fmt: str = "h5", **options: Any) -> None:
    """通过已注册后端保存模型。"""

    path = Path(path)
    payload = _run_before_save(path, fmt, model, **options)
    backend = get_backend(fmt)
    try:
        backend.save(path, payload, **options)
    except Exception as exc:  # noqa: BLE001
        raise BackendError(f"save failed: fmt={fmt}, path={path}") from exc
    logger.info("save done: fmt=%s, path=%s", fmt, path)


def load(
    path: Path | str,
    *,
    fmt: str = "h5",
    category: DataCategory | None = None,
    **options: Any,
) -> Any:
    """通过已注册后端加载模型。"""

    path = Path(path)
    backend = get_backend(fmt)
    try:
        raw = backend.load(path, category=category, **options)
    except Exception as exc:  # noqa: BLE001
        raise BackendError(f"load failed: fmt={fmt}, path={path}, category={category}") from exc
    loaded = _run_after_load(path, fmt, category, raw, **options)
    logger.info("load done: fmt=%s, path=%s, category=%s", fmt, path, category)
    return loaded


def inspect(
    path: Path | str,
    *,
    fmt: str = "h5",
    category: DataCategory | None = None,
    **options: Any,
) -> dict[str, str]:
    """通过已注册后端检查存储单位。"""

    path = Path(path)
    backend = get_backend(fmt)
    try:
        units = backend.inspect_units(path, category=category, **options)
    except Exception as exc:  # noqa: BLE001
        raise BackendError(f"inspect failed: fmt={fmt}, path={path}, category={category}") from exc
    logger.info("inspect done: fmt=%s, path=%s, category=%s", fmt, path, category)
    return units


def _register_defaults() -> None:
    from .persistence_backends import CSVBackend, H5Backend

    register_backend("h5", H5Backend)
    register_backend("csv", CSVBackend)


_register_defaults()


__all__ = [
    "DataBackend",
    "PersistenceError",
    "BackendError",
    "SchemaError",
    "RecoverableIOError",
    "HookContext",
    "register_backend",
    "get_backend",
    "register_before_save",
    "register_after_load",
    "save",
    "load",
    "inspect",
]
