"""检查仓库级 Codex agents 与 skills 资产是否完整且与当前口径一致。"""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path
import re

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
REQUIRED_AGENT_KEYS = (
    "name",
    "description",
    "model",
    "model_reasoning_effort",
    "sandbox_mode",
    "developer_instructions",
)
REQUIRED_CODEX_FILES = (
    ".codex/project-context.md",
    ".codex/library-contract.md",
    ".codex/prompts/task-template.md",
)
AGENTS_REQUIRED_TOKENS = (
    ".codex/agents/",
    ".agents/skills/",
    "check_codex_assets.py",
    "必须先问用户的事项",
    "Codex 工作方式与子代理策略",
)
FORBIDDEN_PUBLIC_SURFACE_TOKENS = (
    "DynTool",
    "tool.models",
    "tool.model",
    "tool.sample",
    "tool.sampleset",
    "tool.processing",
    "tool.evaluation",
    "tool.plotting",
    "tool.logger",
    "tool.storage",
    "tool.constant",
    "tool.resource",
)
FORBIDDEN_PUBLIC_SURFACE_PATTERNS = {
    token: re.compile(rf"(?<![A-Za-z0-9_]){re.escape(token)}(?![A-Za-z0-9_])")
    for token in FORBIDDEN_PUBLIC_SURFACE_TOKENS
}
ROLE_MATRIX_PATH = Path(".agents/skills/advdyntool-task-routing/references/role-matrix.toml")
DOC_WORKFLOW_PATH = Path("docs/developer/development_workflow.md")
BOM = bytes((0xEF, 0xBB, 0xBF))


def _repo_path(relative: str | Path) -> Path:
    return PROJECT_ROOT / relative


def _read_text(path: Path) -> str:
    raw = path.read_bytes()
    if raw.startswith(BOM):
        raise ValueError(f"{path.relative_to(PROJECT_ROOT)}: contains UTF-8 BOM")
    return raw.decode("utf-8")


def _parse_toml(path: Path) -> dict[str, object]:
    try:
        return tomllib.loads(_read_text(path))
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"{path.relative_to(PROJECT_ROOT)}: invalid TOML ({exc})") from exc


def _check_required_files(violations: list[str]) -> None:
    for relative in REQUIRED_CODEX_FILES:
        path = _repo_path(relative)
        if not path.exists():
            violations.append(f"{relative}: missing required Codex asset")

    agents_dir = _repo_path(".codex/agents")
    if not agents_dir.exists():
        violations.append(".codex/agents: missing")
    for filename in REQUIRED_AGENT_FILES:
        path = agents_dir / filename
        if not path.exists():
            violations.append(f".codex/agents/{filename}: missing required agent")

    skills_dir = _repo_path(".agents/skills")
    if not skills_dir.exists():
        violations.append(".agents/skills: missing")
    for skill_name in REQUIRED_SKILLS:
        skill_dir = skills_dir / skill_name
        if not skill_dir.exists():
            violations.append(f".agents/skills/{skill_name}: missing required skill directory")
            continue
        if not (skill_dir / "SKILL.md").exists():
            violations.append(f".agents/skills/{skill_name}/SKILL.md: missing")

    if not _repo_path(DOC_WORKFLOW_PATH).exists():
        violations.append(f"{DOC_WORKFLOW_PATH.as_posix()}: missing")


def _check_agents(violations: list[str]) -> None:
    agents_dir = _repo_path(".codex/agents")
    if not agents_dir.exists():
        return
    for filename in REQUIRED_AGENT_FILES:
        path = agents_dir / filename
        if not path.exists():
            continue
        try:
            payload = _parse_toml(path)
        except ValueError as exc:
            violations.append(str(exc))
            continue
        for key in REQUIRED_AGENT_KEYS:
            if key not in payload:
                violations.append(f"{path.relative_to(PROJECT_ROOT)}: missing required key {key!r}")


def _check_role_matrix(violations: list[str]) -> None:
    path = _repo_path(ROLE_MATRIX_PATH)
    if not path.exists():
        violations.append(f"{ROLE_MATRIX_PATH.as_posix()}: missing")
        return
    try:
        payload = _parse_toml(path)
    except ValueError as exc:
        violations.append(str(exc))
        return

    required_agents = payload.get("required_agents")
    required_skills = payload.get("required_skills")
    if required_agents != list(REQUIRED_AGENT_FILES):
        violations.append(f"{ROLE_MATRIX_PATH.as_posix()}: required_agents does not match required agent roster")
    if required_skills != list(REQUIRED_SKILLS):
        violations.append(f"{ROLE_MATRIX_PATH.as_posix()}: required_skills does not match required skill roster")


def _check_gitignore(violations: list[str]) -> None:
    path = _repo_path(".gitignore")
    if not path.exists():
        violations.append(".gitignore: missing")
        return
    text = _read_text(path)
    blocked_entries = {".codex/", "/.codex/"}
    active_entries = {line.strip() for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#")}
    if blocked_entries & active_entries:
        violations.append(".gitignore: must not ignore the repository-scoped .codex/ directory")


def _check_agents_md(violations: list[str]) -> None:
    path = _repo_path("AGENTS.md")
    if not path.exists():
        violations.append("AGENTS.md: missing")
        return
    text = _read_text(path)
    for token in AGENTS_REQUIRED_TOKENS:
        if token not in text:
            violations.append(f"AGENTS.md: missing required token {token!r}")


def _iter_asset_files() -> list[Path]:
    patterns = (
        ".codex/**/*.md",
        ".codex/agents/*.toml",
        ".agents/skills/**/*.md",
        ".agents/skills/**/*.toml",
    )
    files: set[Path] = set()
    for pattern in patterns:
        files.update(_repo_path(".").glob(pattern))
    return sorted(path for path in files if path.is_file())


def _check_legacy_tokens(violations: list[str]) -> None:
    for path in _iter_asset_files():
        text = _read_text(path)
        for token, pattern in FORBIDDEN_PUBLIC_SURFACE_PATTERNS.items():
            if pattern.search(text):
                violations.append(
                    f"{path.relative_to(PROJECT_ROOT)}: contains removed or legacy public-surface token {token!r}"
                )


def main() -> int:
    violations: list[str] = []
    _check_required_files(violations)
    _check_agents(violations)
    _check_role_matrix(violations)
    _check_gitignore(violations)
    _check_agents_md(violations)
    _check_legacy_tokens(violations)

    if violations:
        print("Codex asset check failed:")
        for violation in violations:
            print(f"  - {violation}")
        return 1

    print("Codex asset check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
