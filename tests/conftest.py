"""测试公共配置。"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src"
PACKAGE_ROOT = SOURCE_ROOT / "dyntool"

os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
sys.dont_write_bytecode = True


def _cleanup_generated_artifacts() -> None:
    """清理前序门禁命令遗留的构建产物。"""

    for target in (PROJECT_ROOT / "site", PROJECT_ROOT / "docs" / "_build"):
        if target.exists():
            shutil.rmtree(target, ignore_errors=True)

    for path in PROJECT_ROOT.rglob("__pycache__"):
        relative = path.relative_to(PROJECT_ROOT)
        if relative.parts[:1] == ("tests",):
            continue
        shutil.rmtree(path, ignore_errors=True)


def _reset_dyntool_modules() -> None:
    """移除已经加载的旧 dyntool 模块。"""

    for name in list(sys.modules):
        if name == "dyntool" or name.startswith("dyntool."):
            sys.modules.pop(name, None)


def _ensure_current_source_first() -> None:
    """确保当前仓库源码位于导入路径首位。"""

    resolved_source = SOURCE_ROOT.resolve()
    sys.path[:] = [entry for entry in sys.path if Path(entry or ".").resolve() != resolved_source]
    sys.path.insert(0, str(resolved_source))
    _reset_dyntool_modules()


def _assert_current_worktree_package() -> None:
    """断言测试导入的是当前工作树源码。"""

    _ensure_current_source_first()
    import dyntool

    package_file = Path(dyntool.__file__).resolve()
    if PACKAGE_ROOT.resolve() not in package_file.parents:
        raise RuntimeError(f"pytest 没有导入当前工作树源码: {package_file}")


def pytest_sessionstart(session: pytest.Session) -> None:
    """在测试会话开始时校验导入链。"""

    _cleanup_generated_artifacts()
    _assert_current_worktree_package()


@pytest.fixture(autouse=True)
def _close_all_matplotlib_figures() -> None:
    """每个测试结束后关闭全部 matplotlib 图。"""

    yield
    plt.close("all")
