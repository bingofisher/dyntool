"""Validate the canonical public API baseline and forbid removed entrypoints."""

from __future__ import annotations

import ast
import sys
import tomllib
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
BASELINE_PATH = PROJECT_ROOT / "docs" / "baselines" / "public_api_baseline.toml"
EXAMPLES_MANIFEST_PATH = PROJECT_ROOT / "docs" / "examples_manifest.toml"
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


def _internal_example_paths() -> set[Path]:
    manifest = tomllib.loads(EXAMPLES_MANIFEST_PATH.read_text(encoding="utf-8"))
    internal: set[Path] = set()
    for entry in manifest.get("example", []):
        if entry.get("kind") != "internal":
            continue
        script = entry.get("script")
        readme = entry.get("readme")
        if isinstance(script, str):
            internal.add((PROJECT_ROOT / script).resolve())
        if isinstance(readme, str):
            internal.add((PROJECT_ROOT / readme).resolve())
    return internal


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
        if resolved in _internal_example_paths():
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


def _extract_module_all(path: Path) -> list[str]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))

    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == "__all__":
                value = ast.literal_eval(node.value)
                if not isinstance(value, list | tuple):
                    raise TypeError(f"{path}: __all__ must be a list or tuple literal")
                return [str(item) for item in value]

    raise ValueError(f"{path}: missing __all__ assignment")


def _check_package_exports(allowed: list[str], removed: list[str]) -> list[str]:
    exported = _extract_module_all(PROJECT_ROOT / "src" / "dyntool" / "__init__.py")
    violations: list[str] = []
    if sorted(exported) != sorted(allowed):
        violations.append("src/dyntool/__init__.py: __all__ does not match top_level_exports_allowed")
    for name in removed:
        if name in exported:
            violations.append(f"src/dyntool/__init__.py: removed export still exists: {name}")
    return violations


def _check_storage_module_exports(allowed: list[str]) -> list[str]:
    exported = _extract_module_all(PROJECT_ROOT / "src" / "dyntool" / "storage" / "__init__.py")
    if sorted(exported) == sorted(allowed):
        return []
    return ["src/dyntool/storage/__init__.py: __all__ does not match storage_module_exports_allowed"]


def _check_plotting_module_exports(allowed: list[str], removed: list[str]) -> list[str]:
    exported = _extract_module_all(PROJECT_ROOT / "src" / "dyntool" / "plotting" / "__init__.py")
    violations: list[str] = []
    if sorted(exported) != sorted(allowed):
        violations.append("src/dyntool/plotting/__init__.py: __all__ does not match plotting_module_exports_allowed")
    for name in removed:
        if name in exported:
            violations.append(f"src/dyntool/plotting/__init__.py: removed export still exists: {name}")
    return violations


def _check_plotting_plotters_module_exports(allowed: list[str]) -> list[str]:
    exported = _extract_module_all(PROJECT_ROOT / "src" / "dyntool" / "plotting" / "plotters.py")
    if sorted(exported) == sorted(allowed):
        return []
    return ["src/dyntool/plotting/plotters.py: __all__ does not match plotting_plotters_module_exports_allowed"]


def _check_reporting_module_exports(allowed: list[str]) -> list[str]:
    exported = _extract_module_all(PROJECT_ROOT / "src" / "dyntool" / "reporting" / "__init__.py")
    if sorted(exported) == sorted(allowed):
        return []
    return ["src/dyntool/reporting/__init__.py: __all__ does not match reporting_module_exports_allowed"]


def _check_public_api_docs(
    storage_module_exports_allowed: list[str],
    plotting_module_exports_allowed: list[str],
    reporting_module_exports_allowed: list[str],
) -> list[str]:
    path = PROJECT_ROOT / "docs" / "api" / "public_api.md"
    text = path.read_text(encoding="utf-8")
    required_tokens = (
        "dyntool.storage",
        "dyntool.plotting",
        "dyntool.reporting",
        "dyntool.logging",
        "dyntool.config",
        "dyntool.resources",
    )
    violations: list[str] = []
    for token in required_tokens:
        if token not in text:
            violations.append(f"docs/api/public_api.md: missing public API token {token!r}")

    storage_contract_tokens = [token for token in storage_module_exports_allowed if token[:1].isupper()]
    for token in storage_contract_tokens:
        if token not in text:
            violations.append(f"docs/api/public_api.md: missing storage contract token {token!r}")
    plotting_contract_tokens = [token for token in plotting_module_exports_allowed if token[:1].isupper()]
    for token in plotting_contract_tokens:
        if token not in text:
            violations.append(f"docs/api/public_api.md: missing plotting contract token {token!r}")
    for token in reporting_module_exports_allowed:
        if token not in text:
            violations.append(f"docs/api/public_api.md: missing reporting contract token {token!r}")
    return violations


def main() -> int:
    baseline = _load_baseline()
    forbidden_tokens = list(baseline["forbidden_tokens"])
    top_level_exports_allowed = list(baseline["top_level_exports_allowed"])
    top_level_exports_removed = list(baseline["top_level_exports_removed"])
    storage_module_exports_allowed = list(baseline.get("storage_module_exports_allowed", []))
    plotting_module_exports_allowed = list(baseline.get("plotting_module_exports_allowed", []))
    plotting_plotters_module_exports_allowed = list(baseline.get("plotting_plotters_module_exports_allowed", []))
    plotting_module_exports_removed = list(baseline.get("plotting_module_exports_removed", []))
    reporting_module_exports_allowed = list(baseline.get("reporting_module_exports_allowed", []))

    violations = _scan_forbidden_tokens(forbidden_tokens)
    violations.extend(_check_package_exports(top_level_exports_allowed, top_level_exports_removed))
    if storage_module_exports_allowed:
        violations.extend(_check_storage_module_exports(storage_module_exports_allowed))
    if plotting_module_exports_allowed or plotting_module_exports_removed:
        violations.extend(
            _check_plotting_module_exports(plotting_module_exports_allowed, plotting_module_exports_removed)
        )
    if plotting_plotters_module_exports_allowed:
        violations.extend(_check_plotting_plotters_module_exports(plotting_plotters_module_exports_allowed))
    if reporting_module_exports_allowed:
        violations.extend(_check_reporting_module_exports(reporting_module_exports_allowed))
    violations.extend(
        _check_public_api_docs(
            storage_module_exports_allowed,
            plotting_module_exports_allowed,
            reporting_module_exports_allowed,
        )
    )

    if violations:
        print("Public API baseline check failed:")
        for item in violations:
            print(f"  - {item}")
        return 1

    print("Public API baseline check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
