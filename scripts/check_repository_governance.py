"""检查仓库治理规则、质量命令口径与 plotting 正式 schema 口径。"""

from __future__ import annotations

import re
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CANONICAL_QUALITY_GATE_COMMANDS = (
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
    "$env:PYTHONDONTWRITEBYTECODE='1'; uv run python -B -m mkdocs build --strict --site-dir .pytest_tmp/mkdocs-site",
    "uv run pyright src/dyntool tests/typing_public_api.py",
    "$env:PYTHONDONTWRITEBYTECODE='1'; uv run python -B -m pytest -q --basetemp .pytest_tmp/pytest -p no:cacheprovider",
)
EXACT_COMMAND_DOCS = (
    Path("AGENTS.md"),
    Path("docs/developer/release_checklist.md"),
)
SUBSET_COMMAND_DOCS = (
    Path("README.md"),
    Path("docs/developer/doc_conventions.md"),
)
FORMAL_PLOTTING_SCAN_ROOTS = (
    Path("README.md"),
    Path("ARCHITECTURE.md"),
    Path("docs/api"),
    Path("docs/usage"),
    Path("docs/developer"),
    Path("examples"),
    Path("src/dyntool/plotting/assets"),
    Path("tests/test_public_api.py"),
    Path("tests/typing_public_api.py"),
)
PLOTTING_SCHEMA_EXEMPT_PATHS = {
    Path("docs/developer/migration_1_2_0.md"),
    Path("tests/test_plotting.py"),
}
FORBIDDEN_COMMAND_PATTERNS = (
    re.compile(r"(?<!uv run )python -B scripts/check_[a-z0-9_]+\.py"),
    re.compile(r"(?<!uv run )ruff check"),
    re.compile(r"(?<!uv run )ruff format"),
    re.compile(r"(?<!uv run )pyright(?:\s|$)"),
)
FORBIDDEN_PLOTTING_SCHEMA_PATTERNS = (
    re.compile(r"(?m)^\[axis_config(?:[.\]])"),
    re.compile(r"(?m)^\[axis_labels(?:[.\]])"),
    re.compile(r"\bspine_top\b"),
    re.compile(r"\bspine_bottom\b"),
    re.compile(r"\bspine_left\b"),
    re.compile(r"\bspine_right\b"),
    re.compile(r"\bspine_linewidth\b"),
    re.compile(r"\btick_direction\b"),
    re.compile(r"\btick_length\b"),
    re.compile(r"\btick_width\b"),
    re.compile(r"\bminor_tick_length\b"),
    re.compile(r"\bminor_tick_width\b"),
    re.compile(r"\bgrid_linewidth\b"),
)
BOM = bytes((0xEF, 0xBB, 0xBF))


def _read_text(path: Path) -> str:
    raw = path.read_bytes()
    if raw.startswith(BOM):
        raise ValueError(f"{path.relative_to(PROJECT_ROOT)}: contains UTF-8 BOM")
    return raw.decode("utf-8")


def _iter_markdown_and_assets(project_root: Path) -> list[Path]:
    files: set[Path] = set()
    for root in FORMAL_PLOTTING_SCAN_ROOTS:
        target = project_root / root
        if not target.exists():
            continue
        if target.is_file():
            files.add(target)
            continue
        files.update(target.rglob("*.md"))
        files.update(target.rglob("*.toml"))
        files.update(target.rglob("*.py"))
    return sorted(path for path in files if path.is_file())


def _check_exact_command_docs(project_root: Path, violations: list[str]) -> None:
    for relative in EXACT_COMMAND_DOCS:
        path = project_root / relative
        if not path.exists():
            violations.append(f"{relative.as_posix()}: missing")
            continue
        text = _read_text(path)
        for command in CANONICAL_QUALITY_GATE_COMMANDS:
            if command not in text:
                violations.append(f"{relative.as_posix()}: missing canonical quality command {command!r}")
        for pattern in FORBIDDEN_COMMAND_PATTERNS:
            match = pattern.search(text)
            if match:
                violations.append(
                    f"{relative.as_posix()}: contains non-canonical quality command fragment {match.group(0)!r}"
                )


def _check_subset_command_docs(project_root: Path, violations: list[str]) -> None:
    for relative in SUBSET_COMMAND_DOCS:
        path = project_root / relative
        if not path.exists():
            violations.append(f"{relative.as_posix()}: missing")
            continue
        text = _read_text(path)
        for pattern in FORBIDDEN_COMMAND_PATTERNS:
            match = pattern.search(text)
            if match:
                violations.append(
                    f"{relative.as_posix()}: contains non-canonical quality command fragment {match.group(0)!r}"
                )


def _check_plotting_schema_tokens(project_root: Path, violations: list[str]) -> None:
    for path in _iter_markdown_and_assets(project_root):
        relative = path.relative_to(project_root)
        if relative in PLOTTING_SCHEMA_EXEMPT_PATHS:
            continue
        text = _read_text(path)
        for pattern in FORBIDDEN_PLOTTING_SCHEMA_PATTERNS:
            match = pattern.search(text)
            if match:
                violations.append(f"{relative.as_posix()}: contains removed plotting schema token {match.group(0)!r}")


def main(*, project_root: Path | None = None) -> int:
    root = (project_root or PROJECT_ROOT).resolve()
    violations: list[str] = []
    _check_exact_command_docs(root, violations)
    _check_subset_command_docs(root, violations)
    _check_plotting_schema_tokens(root, violations)
    if violations:
        print("Repository governance check failed:")
        for violation in violations:
            print(f"  - {violation}")
        return 1
    print("Repository governance check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
