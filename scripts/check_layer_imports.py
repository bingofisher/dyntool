"""检查实现层、公开模块、类型叶模块与可解析动态导入的依赖边界。"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src" / "dyntool"
LAYERS = {"application", "domain", "compute", "infrastructure"}
ALLOWED_NON_LAYER_TARGETS: dict[str, set[str]] = {
    "application": {"logging", "plotting", "storage", "config"},
    "domain": {"logging"},
    "compute": {"resources"},
    "infrastructure": {"storage", "logging", "plotting", "config"},
}
ALLOWED_TARGETS: dict[str, set[str]] = {
    "application": {"application", "domain", "compute"},
    "domain": {"domain", "compute"},
    "compute": {"compute"},
    "infrastructure": {"infrastructure", "domain"},
}
# 层外公开模块承担组装职责；这些例外必须与架构文档同步。
PUBLIC_MODULE_TARGETS = {
    "storage": {"storage", "domain", "infrastructure", "compute", "logging", "reporting"},
    "reporting": {"reporting", "domain", "compute", "plotting", "infrastructure"},
    "plotting": {"plotting", "domain", "config"},
    "logging": {"logging"},
    "config": {"config"},
}
LEAF_MODULE_TARGETS = {
    "dyntool.storage.types": {"domain", "storage"},
    "dyntool.plotting.types": {"domain", "plotting"},
}

BOM = bytes((0xEF, 0xBB, 0xBF))


def _iter_layer_files() -> list[Path]:
    return sorted(SOURCE_ROOT.rglob("*.py"))


def _resolve_import_name(*, current_module: str, imported_module: str | None, level: int) -> str | None:
    if level == 0:
        return imported_module
    parts = current_module.split(".")
    if level > len(parts):
        return None
    base = parts[:-level]
    if imported_module:
        base.extend(imported_module.split("."))
    return ".".join(base) if base else None


def _parse_module(path: Path) -> ast.AST:
    raw = path.read_bytes()
    if raw.startswith(BOM):
        rel = path.relative_to(PROJECT_ROOT)
        raise SyntaxError(f"{rel}: contains UTF-8 BOM; remove it before running layer checks")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        rel = path.relative_to(PROJECT_ROOT)
        raise SyntaxError(f"{rel}: not valid UTF-8 ({exc})") from exc
    try:
        return ast.parse(text, filename=str(path))
    except SyntaxError as exc:
        rel = path.relative_to(PROJECT_ROOT)
        raise SyntaxError(f"{rel}: failed to parse ({exc.msg} at line {exc.lineno})") from exc


def _iter_imported_modules(path: Path) -> list[tuple[int, str]]:
    module = ".".join(path.relative_to(PROJECT_ROOT / "src").with_suffix("").parts)
    tree = _parse_module(path)
    imports: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append((node.lineno, alias.name))
        elif isinstance(node, ast.ImportFrom):
            resolved = _resolve_import_name(current_module=module, imported_module=node.module, level=node.level)
            if resolved is not None:
                if resolved == "dyntool":
                    # 顶层重导出也必须按实际所属层检查，防止绕过 compute -> domain 限制。
                    for alias in node.names:
                        public_name = alias.name
                        target = (
                            public_name
                            if public_name in {*PUBLIC_MODULE_TARGETS, "resources"}
                            else "compute"
                            if public_name == "UnitSystem"
                            else "storage"
                            if public_name
                            in {
                                "StorageMode",
                                "StorageScheme",
                                "StorageConnectOptions",
                                "AttrDataFormat",
                                "ContainerFormat",
                            }
                            else "logging"
                            if public_name == "LoggingMode"
                            else "domain"
                        )
                        imports.append((node.lineno, f"dyntool.{target}"))
                else:
                    imports.append((node.lineno, resolved))
        elif _is_dynamic_import_call(node):
            imported_name = _extract_dynamic_import_name(node)
            if imported_name is not None:
                if imported_name.startswith("."):
                    package = next(
                        (
                            kw.value.value
                            for kw in node.keywords
                            if kw.arg == "package"
                            and isinstance(kw.value, ast.Constant)
                            and isinstance(kw.value.value, str)
                        ),
                        None,
                    )
                    if package is not None:
                        dots = len(imported_name) - len(imported_name.lstrip("."))
                        imported_name = _resolve_import_name(
                            current_module=f"{package}.__init__", imported_module=imported_name.lstrip("."), level=dots
                        )
                if imported_name is not None:
                    imports.append((node.lineno, imported_name))
    return imports


def _is_dynamic_import_call(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if isinstance(func, ast.Attribute):
        return func.attr == "import_module"
    return isinstance(func, ast.Name) and func.id in {"import_module", "__import__"}


def _extract_dynamic_import_name(node: ast.Call) -> str | None:
    if not node.args:
        return None
    first_arg = node.args[0]
    if not isinstance(first_arg, ast.Constant) or not isinstance(first_arg.value, str):
        return None
    return first_arg.value


def _layer_of_path(path: Path) -> str | None:
    top = path.relative_to(SOURCE_ROOT).parts[0]
    return top if top in LAYERS or top in PUBLIC_MODULE_TARGETS else None


def main() -> int:
    violations: list[str] = []
    edges: set[tuple[str, str]] = set()
    try:
        for pyfile in _iter_layer_files():
            layer = _layer_of_path(pyfile)
            if layer is None:
                continue
            current_module = ".".join(pyfile.relative_to(PROJECT_ROOT / "src").with_suffix("").parts)
            public_targets = PUBLIC_MODULE_TARGETS.get(layer)
            leaf_targets = LEAF_MODULE_TARGETS.get(current_module)
            for lineno, imported in _iter_imported_modules(pyfile):
                if not imported.startswith("dyntool."):
                    continue
                parts = imported.split(".")
                if len(parts) < 2:
                    continue
                target_layer = parts[1]
                if public_targets is not None:
                    allowed = leaf_targets or public_targets
                    if target_layer not in allowed:
                        violations.append(
                            f"{pyfile.relative_to(PROJECT_ROOT)}:{lineno}: forbidden public module dependency "
                            f"{layer} -> {target_layer} ({imported})"
                        )
                    continue
                if target_layer not in LAYERS:
                    if target_layer in ALLOWED_NON_LAYER_TARGETS[layer]:
                        continue
                    rel = pyfile.relative_to(PROJECT_ROOT)
                    violations.append(
                        f"{rel}:{lineno}: forbidden non-layer dependency {layer} -> {target_layer} ({imported})"
                    )
                    continue
                if target_layer != layer:
                    edges.add((layer, target_layer))
                if target_layer not in ALLOWED_TARGETS[layer]:
                    rel = pyfile.relative_to(PROJECT_ROOT)
                    violations.append(f"{rel}:{lineno}: forbidden dependency {layer} -> {target_layer} ({imported})")
    except SyntaxError as exc:
        print(f"Layer dependency check failed: {exc}")
        return 1

    if violations:
        print("Layer dependency check failed:")
        for item in violations:
            print(f"  - {item}")
        print("\nDetected layer edges:")
        for src, dst in sorted(edges):
            print(f"  - {src} -> {dst}")
        return 1

    print("Layer dependency check passed.")
    if edges:
        print("Detected layer edges:")
        for src, dst in sorted(edges):
            print(f"  - {src} -> {dst}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
