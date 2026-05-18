"""GitHub Rulesets 与 CI 治理回归测试。"""

from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_ci_workflow_exists_and_uses_quality_job() -> None:
    """正式 CI workflow 应已恢复，并固定使用 quality job。"""

    workflow_path = PROJECT_ROOT / ".github" / "workflows" / "ci.yml"
    assert workflow_path.exists()

    text = workflow_path.read_text(encoding="utf-8")
    assert "name: CI" in text
    assert "quality:" in text
    assert "runs-on: windows-latest" in text
    assert "uv sync --group dev --group docs" in text
    assert "PYTHONDONTWRITEBYTECODE: \"1\"" in text


def test_ci_workflow_covers_current_repository_quality_gates() -> None:
    """正式 CI workflow 应覆盖当前仓库的核心质量门禁。"""

    text = (PROJECT_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    expected_commands = (
        "uv run python -B scripts/check_codex_assets.py",
        "uv run ruff check --no-cache src/dyntool tests examples",
        "uv run ruff format --check src/dyntool tests examples",
        "uv run python -B scripts/check_layer_imports.py",
        "uv run python -B scripts/check_text_quality.py",
        "uv run python -B scripts/check_docstring_coverage.py",
        "uv run python -B scripts/check_public_api_baseline.py",
        "uv run python -B scripts/check_resource_consistency.py",
        "uv run python -B scripts/check_mkdocs_site.py",
        "uv run python -B scripts/check_repository_governance.py",
        "uv run python -B scripts/check_helper_structure.py",
        "uv run pyright src/dyntool tests/typing_public_api.py",
        "uv run python -B -m mkdocs build --strict --site-dir .pytest_tmp/mkdocs-site",
        "uv run python -B -m pytest -q --basetemp .pytest_tmp/pytest -p no:cacheprovider",
    )
    for command in expected_commands:
        assert command in text


def test_developer_docs_pin_ruleset_names_and_branch_tag_targets() -> None:
    """开发者文档应固定 Ruleset 名称、分支目标和 tag 目标。"""

    ruleset_doc = PROJECT_ROOT / "docs" / "developer" / "github_rulesets.md"
    assert ruleset_doc.exists()
    text = ruleset_doc.read_text(encoding="utf-8")

    assert "Protect main" in text
    assert "Protect release tags" in text
    assert "refs/heads/main" in text
    assert "refs/tags/v*" in text
    assert "quality" in text


def test_governance_docs_position_main_and_v_tags_as_single_sources_of_truth() -> None:
    """治理文档应统一 main 主线与 v* 发布事实源口径。"""

    version_lines = (PROJECT_ROOT / "docs" / "developer" / "version_lines.md").read_text(encoding="utf-8")
    release_checklist = (PROJECT_ROOT / "docs" / "developer" / "release_checklist.md").read_text(encoding="utf-8")
    agents = (PROJECT_ROOT / "AGENTS.md").read_text(encoding="utf-8")

    assert "`main`：当前正式稳定主线" in version_lines
    assert "`v1.2.2` 已作为当前稳定基线正式发布" in version_lines
    assert "Protect main" in release_checklist
    assert "Protect release tags" in release_checklist
    assert "`main` 是唯一正式主线" in agents
    assert "`v*` tag 是唯一正式发布事实源" in agents
