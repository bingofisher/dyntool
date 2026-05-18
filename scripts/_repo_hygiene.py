"""仓库文本卫生与生成物清理的共享逻辑。"""

from __future__ import annotations

import ast
import os
from dataclasses import dataclass
from pathlib import Path
import re


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
    "docs/developer/**/*.md",
    "docs/reference/**/*.md",
    "docs/usage/**/*.md",
    "docs/workflows/**/*.md",
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
    "docs/developer/**/*.md",
    "docs/reference/**/*.md",
    "docs/usage/**/*.md",
    "docs/workflows/**/*.md",
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
PROTECTED_ARTIFACT_ROOTS = {".git", ".venv", ".uv-cache", ".worktrees"}
GENERATED_ARTIFACT_NAMES = {
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".pytest_tmp",
    ".pytest_tmp_root",
    ".tmp",
    "tmp",
    "site",
    "_build",
    ".tmp_plot_verify",
}
GENERATED_ARTIFACT_PATHS = {Path("docs") / "_build"}
HEADER_PATTERNS = (
    "@Author",
    "@Date",
    "@LastEditors",
    "@LastEditTime",
    "@FilePath",
    "@Description",
)
KNOWN_MOJIBAKE_REPLACEMENTS = {
    "\u93cd\u56ec\ue57d": "标题",
    "\u6d93\ue15f\u6783\u7487\u5b58\u69d1": "中文说明",
}
COMMON_MOJIBAKE_FRAGMENTS = (
    *KNOWN_MOJIBAKE_REPLACEMENTS.keys(),
    "\u95c2\u5099\u7901",
    "\u95b8\u5ff3\u5259\u7df1",
    "\u7f01\u5b34\u557f\u9423",
    "\u95ba\u509d\u6d26",
    "\u95b8\u6b0f\u503d",
    "\u95ba\u5d76\u6531",
    "\u95b8\u612c\u61d8\u934e",
    "\u6fe1\ue0a2\u5a89",
    "\u95bb\ue78c\u5291\u9369",
    "楠岃瘉澶辫触",
    "鏍锋湰",
    "鏍囧噯鍖",
    "浠庡簳灞",
    "绛栫暐",
    "杩斿洖",
)
BOM = bytes((0xEF, 0xBB, 0xBF))
C1_CONTROL_RE = re.compile(r"[\u0080-\u009f]")
SELF_PATTERN_EXEMPT_FILES = {
    "check_text_quality.py",
    "fix_text_hygiene.py",
    "_repo_hygiene.py",
    "test_cleanup_guards.py",
    "test_repo_hygiene_scripts.py",
}


@dataclass(slots=True)
class TextIssue:
    """单个文本卫生问题。"""

    path: Path
    kind: str
    detail: str
    fixable: bool = False
    line: int | None = None
    snippet: str | None = None

    def format(self, project_root: Path) -> str:
        """格式化为稳定输出。"""

        location = self.path.relative_to(project_root).as_posix()
        if self.line is not None:
            location = f"{location}:{self.line}"
        if self.snippet:
            return f"{location}: {self.detail} -> {self.snippet}"
        return f"{location}: {self.detail}"


@dataclass(slots=True)
class ArtifactIssue:
    """单个生成物命中项。"""

    path: Path

    def format(self, project_root: Path) -> str:
        return self.path.relative_to(project_root).as_posix()


@dataclass(slots=True)
class HygieneReport:
    """统一维护脚本输出。"""

    scanned_files: int
    issues_found: int
    fixable_issues: int
    changed_or_removed: list[Path]
    manual_review: list[str]


def _iter_files(project_root: Path, patterns: list[str]) -> list[Path]:
    files: set[Path] = set()
    for pattern in patterns:
        files.update(project_root.glob(pattern))

    result: list[Path] = []
    for path in files:
        if not path.is_file():
            continue
        relative_parts = set(path.relative_to(project_root).parts)
        if relative_parts & EXCLUDED_PARTS:
            continue
        result.append(path)
    return sorted(result)


def iter_text_files(project_root: Path) -> list[Path]:
    """返回需要扫描的文本文件。"""

    return _iter_files(project_root, TEXT_GLOBS)


def iter_python_text_io_files(project_root: Path) -> list[Path]:
    """返回需要扫描显式编码的 Python 文件。"""

    return _iter_files(project_root, PYTHON_TEXT_IO_GLOBS)


def iter_strict_doc_files(project_root: Path) -> set[Path]:
    """返回必须包含中文说明的正式文档集合。"""

    return set(_iter_files(project_root, STRICT_CHINESE_DOC_GLOBS))


def contains_cjk(text: str) -> bool:
    """判断文本是否包含中文字符。"""

    return any("\u4e00" <= char <= "\u9fff" for char in text)


def check_control_files(project_root: Path) -> list[str]:
    """检查控制文件是否满足强规则。"""

    violations: list[str] = []
    editorconfig = project_root / ".editorconfig"
    gitattributes = project_root / ".gitattributes"

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

    return violations


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


def text_io_encoding_violations(path: Path, project_root: Path) -> list[str]:
    """检查文本 I/O 是否显式声明 UTF-8。"""

    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    rel = path.relative_to(project_root)
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


def _iter_fragment_occurrences(text: str, fragment: str) -> list[tuple[int, str]]:
    hits: list[tuple[int, str]] = []
    for index, line in enumerate(text.splitlines(), start=1):
        if fragment in line:
            hits.append((index, line.strip()))
    return hits


def detect_text_issues(path: Path, project_root: Path, *, strict_doc: bool) -> list[TextIssue]:
    """检测单文件文本卫生问题。"""

    issues: list[TextIssue] = []
    raw = path.read_bytes()
    if raw.startswith(BOM):
        issues.append(TextIssue(path, "bom", "contains UTF-8 BOM", fixable=True))

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        issues.append(TextIssue(path, "invalid_utf8", f"not valid UTF-8 ({exc})"))
        return issues

    if "\r" in text:
        issues.append(TextIssue(path, "line_endings", "contains CRLF or CR line endings", fixable=True))

    if C1_CONTROL_RE.search(text):
        issues.append(TextIssue(path, "c1_control", "contains C1 control characters"))

    if path.name not in SELF_PATTERN_EXEMPT_FILES and any(pattern in text for pattern in HEADER_PATTERNS):
        issues.append(TextIssue(path, "historical_header", "contains forbidden historical header template"))

    if strict_doc and not contains_cjk(text):
        issues.append(TextIssue(path, "missing_cjk", "should contain Chinese documentation"))

    if path.name not in SELF_PATTERN_EXEMPT_FILES:
        remaining_text = text
        for fragment, replacement in KNOWN_MOJIBAKE_REPLACEMENTS.items():
            if fragment not in remaining_text:
                continue
            for line, snippet in _iter_fragment_occurrences(remaining_text, fragment):
                issues.append(
                    TextIssue(
                        path,
                        "known_mojibake",
                        f"contains known mojibake fragment; suggested replacement {replacement!r}",
                        fixable=True,
                        line=line,
                        snippet=snippet,
                    )
                )
            remaining_text = remaining_text.replace(fragment, replacement)

        for fragment in COMMON_MOJIBAKE_FRAGMENTS:
            if fragment in KNOWN_MOJIBAKE_REPLACEMENTS:
                continue
            for line, snippet in _iter_fragment_occurrences(remaining_text, fragment):
                issues.append(
                    TextIssue(
                        path,
                        "unknown_mojibake",
                        "contains suspicious mojibake fragment",
                        line=line,
                        snippet=snippet,
                    )
                )

    return issues


def apply_low_risk_text_fixes(path: Path) -> bool:
    """对单文件执行低风险文本修复。"""

    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return False

    updated = text.replace("\r\n", "\n").replace("\r", "\n")
    for source, target in KNOWN_MOJIBAKE_REPLACEMENTS.items():
        updated = updated.replace(source, target)

    if updated == text and not raw.startswith(BOM):
        return False

    path.write_text(updated, encoding="utf-8", newline="\n")
    return True


def scan_text_hygiene(project_root: Path) -> tuple[list[TextIssue], list[str], int]:
    """扫描仓库文本卫生问题。"""

    issues: list[TextIssue] = []
    strict_doc_files = iter_strict_doc_files(project_root)
    text_files = iter_text_files(project_root)

    for violation in check_control_files(project_root):
        issues.append(TextIssue(project_root / violation.split(":", maxsplit=1)[0], "control_file", violation))

    for path in text_files:
        issues.extend(detect_text_issues(path, project_root, strict_doc=path in strict_doc_files))

    encoding_violations: list[str] = []
    for path in iter_python_text_io_files(project_root):
        encoding_violations.extend(text_io_encoding_violations(path, project_root))

    return issues, encoding_violations, len(text_files)


def scan_generated_artifacts(project_root: Path) -> list[ArtifactIssue]:
    """扫描仓库内高置信生成物。"""

    issues: list[ArtifactIssue] = []
    for current_root, dirnames, filenames in os.walk(project_root, topdown=True):
        current_path = Path(current_root)
        dirnames[:] = [name for name in dirnames if name not in PROTECTED_ARTIFACT_ROOTS]

        removable_dirs = [name for name in dirnames if name in GENERATED_ARTIFACT_NAMES]
        for name in removable_dirs:
            candidate = current_path / name
            relative = candidate.relative_to(project_root)
            if relative in GENERATED_ARTIFACT_PATHS or name in GENERATED_ARTIFACT_NAMES:
                issues.append(ArtifactIssue(candidate))

        dirnames[:] = [name for name in dirnames if name not in GENERATED_ARTIFACT_NAMES]

        for filename in filenames:
            candidate = current_path / filename
            relative = candidate.relative_to(project_root)
            if relative in GENERATED_ARTIFACT_PATHS:
                issues.append(ArtifactIssue(candidate))

    deduped = {issue.path.resolve(): issue for issue in issues}
    return [deduped[key] for key in sorted(deduped, key=lambda item: str(item))]


def remove_generated_artifact(path: Path) -> None:
    """删除高置信生成物路径。"""

    if path.is_dir():
        for child in sorted(path.iterdir(), key=lambda item: (item.is_file(), str(item)), reverse=True):
            if child.is_dir():
                remove_generated_artifact(child)
            else:
                child.unlink()
        path.rmdir()
        return

    path.unlink()


def format_report(
    *,
    mode: str,
    scanned_files: int,
    issues_found: int,
    fixable_issues: int,
    changed_or_removed: list[str],
    manual_review: list[str],
) -> str:
    """构造统一脚本输出。"""

    lines = [
        "summary",
        f"  mode: {mode}",
        f"  scanned_files: {scanned_files}",
        f"  issues_found: {issues_found}",
        f"  auto_fixable: {fixable_issues}",
        f"  manual_review: {len(manual_review)}",
        "changed/removed",
    ]
    if changed_or_removed:
        lines.extend(f"  - {item}" for item in changed_or_removed)
    else:
        lines.append("  - none")

    lines.append("manual_review")
    if manual_review:
        lines.extend(f"  - {item}" for item in manual_review)
    else:
        lines.append("  - none")

    return "\n".join(lines)


def print_text(text: str) -> None:
    """以 UTF-8 友好的方式输出文本。"""

    if hasattr(os.sys.stdout, "reconfigure"):
        os.sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    print(text)
