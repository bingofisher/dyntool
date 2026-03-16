"""检查仓库文本质量、编码规范和常见乱码片段。"""

from __future__ import annotations

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
    "docs/**/*.md",
    "docs/**/*.toml",
    "examples/**/*.md",
    "examples/**/*.py",
    "src/dyntool/**/*.py",
    "tests/**/*.py",
]
STRICT_CHINESE_DOC_GLOBS = [
    "AGENTS.md",
    "README.md",
    "ARCHITECTURE.md",
    "docs/**/*.md",
    "examples/**/*.md",
]
HEADER_PATTERNS = (
    "@Author",
    "@Date",
    "@LastEditors",
    "@LastEditTime",
    "@FilePath",
    "@Description",
)
COMMON_MOJIBAKE_FRAGMENTS = (
    "鏂囨。",
    "鍏紑",
    "鏍锋湰",
    "鍔犺浇",
    "淇濆瓨",
    "闈㈠悜",
    "妯″瀷",
    "璇存槑",
)
BOM = bytes((0xEF, 0xBB, 0xBF))
EDITORCONFIG_REQUIRED = ("root = true", "charset = utf-8", "end_of_line = lf")
GITATTRIBUTES_REQUIRED = (
    "* text=auto eol=lf",
    "*.py text eol=lf",
    "*.md text eol=lf",
)
EXCLUDED_PARTS = {"_build", ".git", "__pycache__", "site"}
C1_CONTROL_RE = re.compile(r"[\u0080-\u009f]")


def _iter_text_files() -> list[Path]:
    files: set[Path] = set()
    for pattern in TEXT_GLOBS:
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


def _iter_strict_doc_files() -> set[Path]:
    files: set[Path] = set()
    for pattern in STRICT_CHINESE_DOC_GLOBS:
        files.update(PROJECT_ROOT.glob(pattern))
    return {
        path for path in files if path.is_file() and not (set(path.relative_to(PROJECT_ROOT).parts) & EXCLUDED_PARTS)
    }


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
        if any(pattern in text for pattern in HEADER_PATTERNS):
            violations.append(f"{rel}: contains forbidden historical header template")
        if any(fragment in text for fragment in COMMON_MOJIBAKE_FRAGMENTS):
            violations.append(f"{rel}: contains common mojibake fragments")
        if path in strict_doc_files and not _contains_cjk(text):
            violations.append(f"{rel}: should contain Chinese documentation")

    if violations:
        print("Text quality check failed:")
        for violation in violations:
            print(f"  - {violation}")
        return 1

    print("Text quality check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
