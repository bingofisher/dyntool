"""检查仓库内部是否出现明显散乱的顶层 helper 反模式。"""

from __future__ import annotations

import ast
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src" / "dyntool"
MONITORED_PREFIXES = ("_normalize_", "_coerce_", "_apply_", "_resolve_")
AGGREGATION_CLASS_HINTS = ("Parser", "Runtime", "Adapter", "Resolver", "Builder", "Registry")
BOM = bytes((0xEF, 0xBB, 0xBF))


def _read_text(path: Path, *, project_root: Path) -> str:
    raw = path.read_bytes()
    if raw.startswith(BOM):
        raise SyntaxError(f"{path.relative_to(project_root)}: contains UTF-8 BOM")
    return raw.decode("utf-8")


def _iter_source_files(project_root: Path) -> list[Path]:
    source_root = project_root / "src" / "dyntool"
    if not source_root.exists():
        return []
    return sorted(source_root.rglob("*.py"))


def _private_helper_group(tree: ast.Module) -> dict[str, list[ast.FunctionDef | ast.AsyncFunctionDef]]:
    groups: dict[str, list[ast.FunctionDef | ast.AsyncFunctionDef]] = {prefix: [] for prefix in MONITORED_PREFIXES}
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        for prefix in MONITORED_PREFIXES:
            if node.name.startswith(prefix):
                groups[prefix].append(node)
                break
    return groups


def _has_aggregation_class(tree: ast.Module) -> bool:
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        if not node.name.startswith("_"):
            continue
        if any(hint in node.name for hint in AGGREGATION_CLASS_HINTS):
            return True
    return False


def _detect_scattered_helpers(path: Path, *, project_root: Path) -> str | None:
    tree = ast.parse(_read_text(path, project_root=project_root), filename=str(path))
    groups = _private_helper_group(tree)
    if _has_aggregation_class(tree):
        return None
    for prefix, nodes in groups.items():
        if len(nodes) < 4:
            continue
        names = ", ".join(node.name for node in nodes)
        return (
            f"{path.relative_to(project_root)}: contains scattered top-level helper cluster {prefix}* "
            f"without private parser/runtime aggregation ({names})"
        )
    return None


def main(*, project_root: Path | None = None) -> int:
    root = (project_root or PROJECT_ROOT).resolve()
    violations: list[str] = []
    for path in _iter_source_files(root):
        violation = _detect_scattered_helpers(path, project_root=root)
        if violation is not None:
            violations.append(violation)
    if violations:
        print("Helper structure check failed:")
        for violation in violations:
            print(f"  - {violation}")
        return 1
    print("Helper structure check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
