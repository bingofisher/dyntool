"""Codex 仓库资产校验测试。"""

from __future__ import annotations

import importlib.util
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

REQUIRED_AGENT_FILES = (
    "impact-analysis.toml",
    "implement-domain-compute.toml",
    "implement-application.toml",
    "implement-storage-infrastructure.toml",
    "implement-resource-config.toml",
    "implement-plotting-logging.toml",
    "public-surface-guardian.toml",
    "test-specialist.toml",
    "docs-sync.toml",
    "verification-runner.toml",
    "spec-reviewer.toml",
    "code-quality-reviewer.toml",
)

REQUIRED_SKILLS = (
    "advdyntool-task-routing",
    "advdyntool-impact-analysis",
    "advdyntool-doc-sync",
    "advdyntool-quality-gates",
)


def _load_script_module(name: str, path: Path) -> object:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _seed_minimal_codex_assets(root: Path) -> None:
    _write_text(
        root / "AGENTS.md",
        "\n".join(
            (
                "# AdvDynTool Codex Rules",
                "",
                "## 8) 必须先问用户的事项",
                "- 公开 API 变化。",
                "",
                "## 11) Codex 工作方式与子代理策略",
                "- 使用 `.codex/agents/` 定义仓库级子代理。",
                "- 使用 `.agents/skills/` 定义仓库级技能。",
                "",
                "## 9) 质量门禁",
                "- `python scripts/check_codex_assets.py`",
            )
        )
        + "\n",
    )
    _write_text(root / ".gitignore", ".venv/\n")
    _write_text(root / ".editorconfig", "root = true\n[*]\ncharset = utf-8\nend_of_line = lf\n")
    _write_text(root / ".gitattributes", "* text=auto eol=lf\n*.py text eol=lf\n*.md text eol=lf\n")
    _write_text(root / ".codex" / "project-context.md", "# 项目上下文\n当前公开入口是 `dyntool`。\n")
    _write_text(root / ".codex" / "library-contract.md", "# 库约定\n主入口是 `from dyntool import DefaultSample`。\n")
    _write_text(root / ".codex" / "prompts" / "task-template.md", "# 任务模板\n请先检查 `AGENTS.md`。\n")
    _write_text(root / "docs" / "developer" / "development_workflow.md", "# 开发工作流\n")
    _write_text(
        root / ".agents" / "skills" / "advdyntool-task-routing" / "references" / "role-matrix.toml",
        "required_agents = [\n"
        + ",\n".join(f'    "{name}"' for name in REQUIRED_AGENT_FILES)
        + "\n]\nrequired_skills = [\n"
        + ",\n".join(f'    "{name}"' for name in REQUIRED_SKILLS)
        + "\n]\n",
    )

    agent_template = "\n".join(
        (
            'name = "demo"',
            'description = "仓库级子代理"',
            'model = "gpt-5.4-mini"',
            'model_reasoning_effort = "medium"',
            'sandbox_mode = "read-only"',
            'developer_instructions = """职责范围：测试。\n可写目录：只读。\n禁止触碰边界：公开 API。\n升级条件：涉及公开 API、单位或存储。\n先问用户：需要启用子代理时。"""',
        )
    )
    for filename in REQUIRED_AGENT_FILES:
        _write_text(root / ".codex" / "agents" / filename, agent_template + "\n")

    for skill_name in REQUIRED_SKILLS:
        _write_text(root / ".agents" / "skills" / skill_name / "SKILL.md", f"# {skill_name}\n中文说明。\n")
        _write_text(
            root / ".agents" / "skills" / skill_name / "references" / "README.md",
            "# 参考\n角色矩阵与触发条件。\n",
        )


def test_check_codex_assets_passes_for_minimal_well_formed_tree(tmp_path: Path) -> None:
    script = _load_script_module("check_codex_assets_script", PROJECT_ROOT / "scripts" / "check_codex_assets.py")
    _seed_minimal_codex_assets(tmp_path)

    script.PROJECT_ROOT = tmp_path

    assert script.main() == 0


def test_check_codex_assets_detects_missing_required_agent(tmp_path: Path) -> None:
    script = _load_script_module(
        "check_codex_assets_missing_agent_script", PROJECT_ROOT / "scripts" / "check_codex_assets.py"
    )
    _seed_minimal_codex_assets(tmp_path)
    (tmp_path / ".codex" / "agents" / "docs-sync.toml").unlink()

    script.PROJECT_ROOT = tmp_path

    assert script.main() == 1


def test_check_codex_assets_detects_legacy_public_surface_tokens(tmp_path: Path) -> None:
    script = _load_script_module(
        "check_codex_assets_legacy_surface_script", PROJECT_ROOT / "scripts" / "check_codex_assets.py"
    )
    _seed_minimal_codex_assets(tmp_path)
    _write_text(tmp_path / ".codex" / "library-contract.md", "# 库约定\n主入口仍是 `DynTool`。\n")

    script.PROJECT_ROOT = tmp_path

    assert script.main() == 1


def test_check_codex_assets_detects_gitignore_blocking_codex(tmp_path: Path) -> None:
    script = _load_script_module(
        "check_codex_assets_gitignore_script", PROJECT_ROOT / "scripts" / "check_codex_assets.py"
    )
    _seed_minimal_codex_assets(tmp_path)
    _write_text(tmp_path / ".gitignore", ".codex/\n")

    script.PROJECT_ROOT = tmp_path

    assert script.main() == 1


def test_check_text_quality_covers_codex_and_skill_docs(tmp_path: Path) -> None:
    script = _load_script_module("check_text_quality_codex_script", PROJECT_ROOT / "scripts" / "check_text_quality.py")
    _write_text(tmp_path / ".editorconfig", "root = true\n[*]\ncharset = utf-8\nend_of_line = lf\n")
    _write_text(tmp_path / ".gitattributes", "* text=auto eol=lf\n*.py text eol=lf\n*.md text eol=lf\n")
    _write_text(tmp_path / ".codex" / "project-context.md", "# 坏片段\n")
    _write_text(tmp_path / ".agents" / "skills" / "advdyntool-task-routing" / "SKILL.md", "# 中文说明\n")

    script.PROJECT_ROOT = tmp_path
    script.COMMON_MOJIBAKE_FRAGMENTS = ("坏片段",)

    text_files = {path.relative_to(tmp_path).as_posix() for path in script._iter_text_files()}
    assert ".codex/project-context.md" in text_files
    assert ".agents/skills/advdyntool-task-routing/SKILL.md" in text_files

    assert script.main() == 1
