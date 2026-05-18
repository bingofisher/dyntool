"""项目层 GUI / Web 主线治理回归测试。"""

from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _read(relative_path: str) -> str:
    return (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")


def test_readme_positions_gui_as_formal_shell_and_web_as_frozen_experiment() -> None:
    text = _read("README.md")

    assert "GUI 是当前唯一正式项目壳" in text
    assert "Web 工作台实验线（冻结）" in text
    assert "不再作为当前推荐工作台入口" in text
    assert "uv sync --group web" in text
    assert "uv run python -B -m dyntool_web.server" in text


def test_architecture_marks_web_as_experimental_line() -> None:
    text = _read("ARCHITECTURE.md")

    assert "GUI 是当前唯一正式项目壳" in text
    assert "Web 工作台实验线" in text
    assert "不再继续扩张" in text
    assert "主迭代节奏以 GUI 为准" in text


def test_developer_docs_keep_web_but_downgrade_it_from_parallel_mainline() -> None:
    web_doc = _read("docs/developer/dyntool_web_workbench.md")
    index_doc = _read("docs/developer/index.md")
    mkdocs_nav = _read("mkdocs.yml")

    assert "# Web 工作台实验线（冻结）" in web_doc
    assert "GUI 是唯一正式项目壳" in web_doc
    assert "不再与 GUI 对称推进" in web_doc
    assert "Web 工作台实验线（冻结）" in index_doc
    assert "Web 工作台实验线（冻结）: developer/dyntool_web_workbench.md" in mkdocs_nav
