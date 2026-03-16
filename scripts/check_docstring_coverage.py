"""检查 ``src/dyntool`` 下源码模块的 docstring 覆盖率与重点结构质量。"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src" / "dyntool"

FOCUSED_SECTION_REQUIREMENTS: dict[str, dict[str, tuple[str, ...]]] = {
    "src/dyntool/domain/models/base.py": {
        "DataModelBase": ("Attributes:",),
        "DataModelBase.from_file": ("Args:", "Returns:", "Raises:", "Notes:"),
        "DataModelBase.inspect_units": ("Args:", "Returns:", "Notes:"),
        "DataModelBase.from_csv": ("Args:", "Returns:", "Notes:"),
    },
    "src/dyntool/domain/runtime/core.py": {
        "ModelRuntimePort": ("Notes:",),
        "ModelRuntimePort.save_model": ("Args:", "Raises:", "Notes:"),
        "ModelRuntimePort.load_model": ("Args:", "Returns:", "Raises:", "Notes:"),
        "ModelRuntimePort.inspect_model_units": ("Args:", "Returns:", "Raises:", "Notes:"),
        "SampleRuntimePort": ("Notes:",),
        "SampleRuntimePort.connect_sample_storage": ("Args:", "Returns:", "Notes:"),
        "SampleRuntimePort.save_sample": ("Args:", "Returns:", "Notes:"),
        "SampleRuntimePort.load_sample": ("Args:", "Returns:", "Notes:"),
        "SampleSetRuntimePort": ("Notes:",),
        "SampleSetRuntimePort.connect_sample_set_storage": ("Args:", "Returns:", "Notes:"),
        "SampleSetRuntimePort.save_sample_set": ("Args:", "Returns:", "Notes:"),
        "SampleSetRuntimePort.load_sample_set": ("Args:", "Returns:", "Notes:"),
        "SampleSetRuntimePort.save_all_samples": ("Args:", "Returns:", "Notes:"),
        "SampleSetRuntimePort.load_all_samples": ("Args:", "Returns:", "Notes:"),
    },
    "src/dyntool/infrastructure/sample_storage_context.py": {
        "StorageContext": ("Attributes:",),
        "StorageContext.__init__": ("Args:",),
        "StorageContext.resolve_storage_categories": ("Args:", "Returns:", "Raises:", "Notes:"),
        "StorageContext.attr_data_format": ("Returns:", "Raises:", "Notes:"),
        "StorageContext.resolve_name": ("Args:", "Returns:", "Raises:", "Notes:"),
        "StorageContext.sample_data_dict": ("Args:", "Returns:", "Raises:", "Notes:"),
        "StorageContext.apply_precision_payload": ("Args:", "Returns:", "Notes:"),
        "StorageContext.resolve_field_type": ("Args:", "Returns:", "Raises:", "Notes:"),
    },
    "src/dyntool/infrastructure/sample_set_storage.py": {
        "SampleSetStorage": ("Attributes:",),
        "SampleSetStorage.connect": ("Args:", "Returns:", "Raises:", "Notes:"),
        "SampleSetStorage.save_all": ("Args:", "Returns:", "Raises:", "Notes:"),
        "SampleSetStorage.load_all": ("Args:", "Returns:", "Raises:", "Notes:"),
    },
    "src/dyntool/storage/runtime.py": {
        "StorageRuntime": ("Attributes:",),
        "StorageRuntime.load": ("Args:", "Returns:", "Raises:", "Notes:"),
        "StorageRuntime.connect_sample_set_runtime": ("Args:", "Returns:", "Raises:", "Notes:"),
        "StorageRuntime.save_sample_set_runtime": ("Args:", "Returns:", "Raises:", "Notes:"),
        "StorageRuntime.load_sample_set_runtime": ("Args:", "Returns:", "Raises:", "Notes:"),
        "StorageRuntime.save_all_samples_runtime": ("Args:", "Returns:", "Raises:", "Notes:"),
        "StorageRuntime.load_all_samples_runtime": ("Args:", "Returns:", "Raises:", "Notes:"),
    },
    "src/dyntool/storage/types.py": {
        "StorageMode": ("枚举值:", "影响:"),
        "StorageScheme": ("枚举值:", "影响:"),
        "AttrDataFormat": ("枚举值:", "影响:"),
        "StorageConnectOptions": ("Attributes:",),
        "ResolvedStorageConnectOptions": ("Attributes:",),
        "resolve_connect_options": ("Args:", "Returns:", "Notes:"),
    },
}


def _iter_target_files() -> list[Path]:
    """返回需要执行 docstring 检查的源码文件列表。"""

    return sorted(path for path in SOURCE_ROOT.rglob("*.py") if path.is_file() and "__pycache__" not in path.parts)


def _is_public_name(name: str) -> bool:
    """判断名称是否属于公开符号。"""

    return not name.startswith("_")


def _is_setter(func: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """判断方法是否为属性 setter。"""

    for decorator in func.decorator_list:
        if isinstance(decorator, ast.Attribute) and decorator.attr == "setter":
            return True
    return False


def _is_overload(func: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """判断函数是否为 ``typing.overload`` 存根。"""

    for decorator in func.decorator_list:
        if isinstance(decorator, ast.Name) and decorator.id == "overload":
            return True
    return False


def _iter_missing_docstrings(path: Path) -> list[str]:
    """收集单个源码文件中的缺失 docstring 项。"""

    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    missing: list[str] = []
    rel = path.relative_to(PROJECT_ROOT)

    if ast.get_docstring(tree) is None:
        missing.append(f"{rel}: missing module docstring")

    for node in tree.body:
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and _is_overload(node):
                continue
            if _is_public_name(node.name) and ast.get_docstring(node) is None:
                missing.append(f"{rel}: missing docstring for {node.name}")
        if isinstance(node, ast.ClassDef):
            if not _is_public_name(node.name):
                continue
            for child in node.body:
                if not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                if not _is_public_name(child.name):
                    continue
                if _is_setter(child):
                    continue
                if _is_overload(child):
                    continue
                if ast.get_docstring(child) is None:
                    missing.append(f"{rel}: missing docstring for {node.name}.{child.name}")
    return missing


def _collect_docstrings(path: Path) -> dict[str, str]:
    """收集单个文件中公开模块、类和方法的 docstring。"""

    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    docs: dict[str, str] = {}
    module_doc = ast.get_docstring(tree)
    if module_doc is not None:
        docs["<module>"] = module_doc

    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            if not _is_public_name(node.name):
                continue
            class_doc = ast.get_docstring(node)
            if class_doc is not None:
                docs[node.name] = class_doc
            for child in node.body:
                if not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                if not _is_public_name(child.name) and child.name != "__init__":
                    continue
                if _is_setter(child) or _is_overload(child):
                    continue
                child_doc = ast.get_docstring(child)
                if child_doc is not None:
                    docs[f"{node.name}.{child.name}"] = child_doc
            continue

        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if _is_overload(node):
                continue
            if _is_public_name(node.name):
                func_doc = ast.get_docstring(node)
                if func_doc is not None:
                    docs[node.name] = func_doc

    return docs


def _iter_structure_violations(path: Path) -> list[str]:
    """检查重点模块中公开符号的 docstring 结构是否满足要求。"""

    rel = path.relative_to(PROJECT_ROOT).as_posix()
    requirements = FOCUSED_SECTION_REQUIREMENTS.get(rel)
    if requirements is None:
        return []

    docs = _collect_docstrings(path)
    violations: list[str] = []
    for symbol, sections in requirements.items():
        doc = docs.get(symbol)
        if doc is None:
            violations.append(f"{rel}: missing docstring for required symbol {symbol}")
            continue
        for section in sections:
            if section not in doc:
                violations.append(f"{rel}: {symbol} missing section {section}")
    return violations


def main() -> int:
    """执行 docstring 覆盖率与结构质量检查。"""

    violations: list[str] = []
    for path in _iter_target_files():
        violations.extend(_iter_missing_docstrings(path))
        violations.extend(_iter_structure_violations(path))

    if violations:
        print("Docstring coverage check failed:")
        for violation in violations:
            print(f"  - {violation}")
        return 1

    print("Docstring coverage check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
