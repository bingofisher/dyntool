"""持久化注册中心与 hook 回归测试。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from dyntool.domain.constants import DataCategory
from dyntool.infrastructure.persistence import (
    BackendError,
    HookContext,
    register_after_load,
    register_backend,
    register_before_save,
)
from dyntool import infrastructure as persistence_registry_pkg

persistence_registry = persistence_registry_pkg.persistence


class _DummyBackend:
    _db: dict[str, Any] = {}

    def save(self, path: Path, model: Any, **options: Any) -> None:
        self._db[str(path)] = model

    def load(self, path: Path, category: DataCategory | None = None, **options: Any) -> Any:
        return self._db[str(path)]


def test_registry_hooks_work_with_unified_context(tmp_path: Path) -> None:
    fmt = "dummy_ctx"
    before_backup = list(persistence_registry._BEFORE_SAVE_HOOKS)
    after_backup = list(persistence_registry._AFTER_LOAD_HOOKS)
    backend_backup = dict(persistence_registry._BACKEND_REGISTRY)
    register_backend(fmt, _DummyBackend)

    def before_hook(ctx: HookContext) -> Any:
        assert ctx.stage == "before_save"
        return {"wrapped": ctx.payload}

    def after_hook(ctx: HookContext) -> Any:
        assert ctx.stage == "after_load"
        return ctx.payload["wrapped"]

    try:
        register_before_save(before_hook)
        register_after_load(after_hook)
        p = tmp_path / "x.bin"
        persistence_registry.save(p, {"k": 1}, fmt=fmt)
        loaded = persistence_registry.load(p, fmt=fmt, category=DataCategory.UNDEFINED)
        assert loaded == {"k": 1}
    finally:
        persistence_registry._BEFORE_SAVE_HOOKS[:] = before_backup
        persistence_registry._AFTER_LOAD_HOOKS[:] = after_backup
        persistence_registry._BACKEND_REGISTRY.clear()
        persistence_registry._BACKEND_REGISTRY.update(backend_backup)


def test_registry_wraps_backend_error(tmp_path: Path) -> None:
    class _BadBackend:
        def save(self, path: Path, model: Any, **options: Any) -> None:
            raise RuntimeError("boom")

        def load(self, path: Path, category: DataCategory | None = None, **options: Any) -> Any:
            raise RuntimeError("boom")

    fmt = "bad_backend"
    backend_backup = dict(persistence_registry._BACKEND_REGISTRY)
    register_backend(fmt, _BadBackend)
    try:
        with pytest.raises(BackendError):
            persistence_registry.save(tmp_path / "x.bin", {"k": 1}, fmt=fmt)
    finally:
        persistence_registry._BACKEND_REGISTRY.clear()
        persistence_registry._BACKEND_REGISTRY.update(backend_backup)
