"""项目层 GUI 单路线治理回归测试。"""

from __future__ import annotations

from pathlib import Path
import tomllib


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _read(relative_path: str) -> str:
    return (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")


def test_readme_positions_gui_as_only_shell_and_records_web_retirement() -> None:
    """正式入口只保留 GUI，并明确告知 Web 退出。"""

    text = _read("README.md")

    assert "GUI 是当前唯一正式项目壳" in text
    assert "Web 路线已退出" in text
    assert "uv sync --group gui" in text
    assert "uv run python -B -m dyntool_gui.app" in text
    assert "uv sync --group web" not in text
    assert "dyntool_web.server" not in text


def test_web_is_absent_from_dependencies_source_and_distribution() -> None:
    """Web 退出同步源码、依赖组和打包范围。"""

    config = tomllib.loads(_read("pyproject.toml"))
    assert "web" not in config["project"]["optional-dependencies"]
    assert "web" not in config["dependency-groups"]
    assert config["tool"]["hatch"]["build"]["packages"] == ["src/dyntool", "src/dyntool_gui"]
    assert not (PROJECT_ROOT / "src/dyntool_web").exists()
    lock = tomllib.loads(_read("uv.lock"))
    assert not {"fastapi", "uvicorn", "websockets", "httpx"} & {package["name"] for package in lock["package"]}


def test_formal_docs_keep_gui_migration_and_remove_web_navigation() -> None:
    """正式导航与架构采用相同的 GUI 单路线合同。"""

    architecture = _read("ARCHITECTURE.md")
    migration = _read("docs/developer/gui_single_route_migration.md")
    index_doc = _read("docs/developer/index.md")
    mkdocs_nav = _read("mkdocs.yml")

    assert "GUI 是当前唯一正式项目壳" in architecture
    assert "Web 路线已退出" in architecture
    assert "gui_single_route_migration.md" in architecture
    assert "GUI 单路线迁移与可靠性" in index_doc
    assert "developer/gui_single_route_migration.md" in mkdocs_nav
    assert "dyntool_web_workbench.md" not in mkdocs_nav
    assert "不保存模型数组" in migration
    assert "未执行" in migration


def test_ci_static_checks_include_gui_and_keep_quality_job() -> None:
    """唯一 GUI 路线纳入静态门禁并保留主 CI 身份。"""

    workflow = _read(".github/workflows/ci.yml")
    assert "name: CI" in workflow
    assert "  quality:" in workflow
    assert "ruff check --no-cache src/dyntool src/dyntool_gui tests examples scripts" in workflow
    assert "ruff format --check --no-cache src/dyntool src/dyntool_gui tests examples scripts" in workflow
    assert "--group gui" in workflow
