"""Validate the canonical public API baseline and forbid removed entrypoints."""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
BASELINE_PATH = PROJECT_ROOT / "docs" / "baselines" / "public_api_baseline.toml"
SCAN_ROOTS = [
    PROJECT_ROOT / "src",
    PROJECT_ROOT / "examples",
    PROJECT_ROOT / "docs",
    PROJECT_ROOT / "README.md",
    PROJECT_ROOT / "ARCHITECTURE.md",
]
EXCLUDED_SCAN_FILES = {
    BASELINE_PATH.resolve(),
}
EXCLUDED_SCAN_PREFIXES = {
    (PROJECT_ROOT / "docs" / "plans").resolve(),
    (PROJECT_ROOT / "docs" / "archive").resolve(),
}


def _load_baseline() -> dict[str, object]:
    with BASELINE_PATH.open("rb") as fh:
        return tomllib.load(fh)


def _iter_scan_files() -> list[Path]:
    files: list[Path] = []
    for root in SCAN_ROOTS:
        if root.is_file():
            files.append(root)
            continue
        files.extend(sorted(root.rglob("*.py")))
        files.extend(sorted(root.rglob("*.md")))
        files.extend(sorted(root.rglob("*.toml")))
    unique: dict[Path, None] = {}
    for path in files:
        resolved = path.resolve()
        if resolved in EXCLUDED_SCAN_FILES:
            continue
        if any(str(resolved).startswith(str(prefix)) for prefix in EXCLUDED_SCAN_PREFIXES):
            continue
        if resolved not in EXCLUDED_SCAN_FILES:
            unique[resolved] = None
    return list(unique)


def _scan_forbidden_tokens(forbidden_tokens: list[str]) -> list[str]:
    violations: list[str] = []
    for path in _iter_scan_files():
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            rel = path.relative_to(PROJECT_ROOT)
            violations.append(f"{rel}: not valid UTF-8 ({exc})")
            continue
        rel = path.relative_to(PROJECT_ROOT)
        for token in forbidden_tokens:
            if token in text:
                violations.append(f"{rel}: contains forbidden token {token!r}")
    return violations


def _check_package_exports(allowed: list[str], removed: list[str]) -> list[str]:
    import dyntool

    exported = list(getattr(dyntool, "__all__", []))
    violations: list[str] = []
    if sorted(exported) != sorted(allowed):
        violations.append("src/dyntool/__init__.py: __all__ does not match top_level_exports_allowed")
    for name in removed:
        if hasattr(dyntool, name):
            violations.append(f"src/dyntool/__init__.py: removed export still exists: {name}")
    return violations


def _check_dyntool_members(allowed: list[str], removed: list[str]) -> list[str]:
    from dyntool import DynTool

    tool = DynTool()
    public_members = sorted(name for name in vars(tool) if not name.startswith("_"))
    violations: list[str] = []
    if sorted(allowed) != public_members:
        violations.append("src/dyntool/application/facade.py: DynTool public members drifted from baseline")
    for name in removed:
        if hasattr(tool, name):
            violations.append(f"src/dyntool/application/facade.py: removed DynTool member still exists: {name}")
    return violations


def main() -> int:
    baseline = _load_baseline()
    forbidden_tokens = list(baseline["forbidden_tokens"])
    top_level_exports_allowed = list(baseline["top_level_exports_allowed"])
    top_level_exports_removed = list(baseline["top_level_exports_removed"])
    dyntool_members_allowed = list(baseline["dyntool_members_allowed"])
    dyntool_members_removed = list(baseline["dyntool_members_removed"])

    violations = _scan_forbidden_tokens(forbidden_tokens)
    violations.extend(_check_package_exports(top_level_exports_allowed, top_level_exports_removed))
    violations.extend(_check_dyntool_members(dyntool_members_allowed, dyntool_members_removed))

    if violations:
        print("Public API baseline check failed:")
        for item in violations:
            print(f"  - {item}")
        return 1

    print("Public API baseline check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
