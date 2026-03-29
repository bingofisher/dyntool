"""检查仓库文本质量、编码规范和常见乱码片段。"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEXT_GLOBS = [
    "AGENTS.md",
    "README.md",
    "ARCHITECTURE.md",
    "mkdocs.yml",
    "task_plan.md",
    "progress.md",
    "findings.md",
    ".editorconfig",
    ".gitattributes",
    ".codex/**/*.md",
    ".codex/**/*.toml",
    ".agents/skills/**/*.md",
    ".agents/skills/**/*.toml",
    "docs/index.md",
    "docs/user_guide.md",
    "docs/workflow_guide.md",
    "docs/examples_overview.md",
    "docs/api/**/*.md",
    "docs/developer/custom_extension.md",
    "docs/baselines/public_api_baseline.toml",
    "examples/**/*.md",
    "examples/**/*.py",
    "scripts/**/*.py",
    "src/dyntool/**/*.py",
    "tests/**/*.py",
]
STRICT_CHINESE_DOC_GLOBS = [
    "AGENTS.md",
    "README.md",
    "ARCHITECTURE.md",
    ".codex/**/*.md",
    ".agents/skills/**/*.md",
    "docs/index.md",
    "docs/user_guide.md",
    "docs/workflow_guide.md",
    "docs/examples_overview.md",
    "docs/api/**/*.md",
    "docs/developer/custom_extension.md",
    "examples/**/*.md",
]
PYTHON_TEXT_IO_GLOBS = [
    "examples/**/*.py",
    "scripts/**/*.py",
    "src/dyntool/**/*.py",
    "tests/**/*.py",
]
EDITORCONFIG_REQUIRED = ("root = true", "charset = utf-8", "end_of_line = lf")
GITATTRIBUTES_REQUIRED = (
    "* text=auto eol=lf",
    "*.py text eol=lf",
    "*.md text eol=lf",
)
EXCLUDED_PARTS = {"_build", ".git", "__pycache__", "site"}
HEADER_PATTERNS = (
    "@Author",
    "@Date",
    "@LastEditors",
    "@LastEditTime",
    "@FilePath",
    "@Description",
)
COMMON_MOJIBAKE_FRAGMENTS = (
    "鍏紑",
    "绋冲畾鎬",
    "鏂囨。",
    "鍙傝€",
    "鏍锋",
    "鍐呴儴",
    "妫€",
    "鐢ㄦ埛",
    "闂佸",
    "閺",
)
BOM = bytes((0xEF, 0xBB, 0xBF))
C1_CONTROL_RE = re.compile(r"[\u0080-\u009f]")
SELF_PATTERN_EXEMPT_FILES = {"check_text_quality.py", "test_cleanup_guards.py"}


def _iter_files(patterns: list[str]) -> list[Path]:
    files: set[Path] = set()
    for pattern in patterns:
        files.update(PROJECT_ROOT.glob(pattern))
    result: list[Path] = []
    for path in files:
        if not path.is_file():
            continue
        relative_parts = set(path.relative_to(PROJECT_ROOT).parts)
        if relative_parts & EXCLUDED_PARTS:
            continue
        result.append(path)
    return sorted(result)


def _iter_text_files() -> list[Path]:
    return _iter_files(TEXT_GLOBS)


def _iter_python_text_io_files() -> list[Path]:
    return _iter_files(PYTHON_TEXT_IO_GLOBS)


def _iter_strict_doc_files() -> set[Path]:
    return set(_iter_files(STRICT_CHINESE_DOC_GLOBS))


def _contains_cjk(text: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in text)


def _check_control_files(violations: list[str]) -> None:
    editorconfig = PROJECT_ROOT / ".editorconfig"
    gitattributes = PROJECT_ROOT / ".gitattributes"

    if not editorconfig.exists():
        violations.append(".editorconfig: missing")
    else:
        text = editorconfig.read_text(encoding="utf-8")
        for token in EDITORCONFIG_REQUIRED:
            if token not in text:
                violations.append(f".editorconfig: missing required token {token!r}")

    if not gitattributes.exists():
        violations.append(".gitattributes: missing")
    else:
        text = gitattributes.read_text(encoding="utf-8")
        for token in GITATTRIBUTES_REQUIRED:
            if token not in text:
                violations.append(f".gitattributes: missing required token {token!r}")


def _string_literal(node: ast.AST | None) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _encoding_is_utf8(call: ast.Call) -> bool:
    for keyword in call.keywords:
        if keyword.arg == "encoding":
            return _string_literal(keyword.value) == "utf-8"
    return False


def _call_mode(call: ast.Call, *, is_method_open: bool) -> str | None:
    for keyword in call.keywords:
        if keyword.arg == "mode":
            return _string_literal(keyword.value)

    mode_index = 0 if is_method_open else 1
    if len(call.args) <= mode_index:
        return "r"
    return _string_literal(call.args[mode_index])


def _text_io_encoding_violations(path: Path) -> list[str]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    rel = path.relative_to(PROJECT_ROOT)
    violations: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        func = node.func
        if isinstance(func, ast.Attribute) and func.attr in {"read_text", "write_text"}:
            if not _encoding_is_utf8(node):
                violations.append(f'{rel}:{node.lineno}: Path.{func.attr}() must explicitly use encoding="utf-8"')
            continue

        is_builtin_open = isinstance(func, ast.Name) and func.id == "open"
        is_method_open = isinstance(func, ast.Attribute) and func.attr == "open"
        if not (is_builtin_open or is_method_open):
            continue

        mode = _call_mode(node, is_method_open=is_method_open)
        if mode is None or "b" in mode:
            continue
        if _encoding_is_utf8(node):
            continue

        call_name = "Path.open" if is_method_open else "open"
        violations.append(f'{rel}:{node.lineno}: {call_name}() must explicitly use encoding="utf-8"')

    return violations


def main() -> int:
    violations: list[str] = []
    strict_doc_files = _iter_strict_doc_files()

    _check_control_files(violations)

    for path in _iter_text_files():
        rel = path.relative_to(PROJECT_ROOT)
        raw = path.read_bytes()
        if raw.startswith(BOM):
            violations.append(f"{rel}: contains UTF-8 BOM")

        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            violations.append(f"{rel}: not valid UTF-8 ({exc})")
            continue

        if C1_CONTROL_RE.search(text):
            violations.append(f"{rel}: contains C1 control characters")
        if path.name not in SELF_PATTERN_EXEMPT_FILES and any(pattern in text for pattern in HEADER_PATTERNS):
            violations.append(f"{rel}: contains forbidden historical header template")
        if path.name not in SELF_PATTERN_EXEMPT_FILES and any(
            fragment in text for fragment in COMMON_MOJIBAKE_FRAGMENTS
        ):
            violations.append(f"{rel}: contains common mojibake fragments")
        if path in strict_doc_files and not _contains_cjk(text):
            violations.append(f"{rel}: should contain Chinese documentation")

    for path in _iter_python_text_io_files():
        violations.extend(_text_io_encoding_violations(path))

    if violations:
        print("Text quality check failed:")
        for violation in violations:
            print(f"  - {violation}")
        return 1

    print("Text quality check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
