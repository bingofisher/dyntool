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
    ".codex/**/*.md",
    ".codex/agents/*.toml",
    ".agents/skills/**/*.md",
    ".agents/skills/**/*.toml",
    ".agents/skills/**/scripts/**/*.py",
    "task_plan.md",
    "progress.md",
    "findings.md",
    ".editorconfig",
    ".gitattributes",
    "docs/**/*.md",
    "docs/**/*.toml",
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
    "docs/**/*.md",
    "examples/**/*.md",
]
PYTHON_TEXT_IO_GLOBS = [
    ".agents/skills/**/scripts/**/*.py",
    "examples/**/*.py",
    "scripts/**/*.py",
    "src/dyntool/**/*.py",
    "tests/**/*.py",
]
PUBLIC_RUNTIME_KWARG_GLOBS = [
    "src/dyntool/domain/runtime/core.py",
    "src/dyntool/domain/samples/base.py",
    "src/dyntool/domain/samples/sets.py",
    "src/dyntool/domain/samples/namespaces.py",
    "src/dyntool/domain/samples/workflows.py",
    "src/dyntool/storage/runtime.py",
    "src/dyntool/application/runtime_binding.py",
    "src/dyntool/domain/models/base.py",
    "src/dyntool/domain/models/time_series.py",
    "src/dyntool/domain/models/frequency_spectrum.py",
    "src/dyntool/domain/models/response_spectrum.py",
    "src/dyntool/domain/models/transfer_function.py",
    "src/dyntool/domain/samples/batch.py",
    "src/dyntool/domain/samples/commands.py",
]
STRICT_TYPE_GLOBS = [
    "src/dyntool/application/facade.py",
    "src/dyntool/application/runtime_binding.py",
    "src/dyntool/domain/runtime/core.py",
    "src/dyntool/domain/models/base.py",
    "src/dyntool/domain/models/transfer_function.py",
    "src/dyntool/domain/models/time_series.py",
    "src/dyntool/domain/models/frequency_spectrum.py",
    "src/dyntool/domain/models/response_spectrum.py",
    "src/dyntool/domain/samples/namespaces.py",
    "src/dyntool/domain/samples/workflows.py",
    "src/dyntool/domain/samples/base.py",
    "src/dyntool/domain/samples/sets.py",
    "src/dyntool/domain/samples/commands.py",
    "src/dyntool/domain/samples/batch.py",
    "src/dyntool/compute/signals.py",
    "src/dyntool/compute/solvers.py",
    "src/dyntool/compute/pipelines.py",
    "src/dyntool/plotting/dataset.py",
    "src/dyntool/plotting/types.py",
    "src/dyntool/plotting/plotters.py",
    "src/dyntool/storage/__init__.py",
    "src/dyntool/storage/runtime.py",
    "src/dyntool/application/options.py",
    "src/dyntool/logging/__init__.py",
    "src/dyntool/logging/provider.py",
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
    "闁哄倸娲﹂妴",
    "闁稿浚鍓欑槐",
    "闁哄秹鏀卞﹢",
    "闁告梻濮惧ù",
    "濞ｅ洦绻傞悺",
    "闂傚牄鍨归幃",
    "婵☆垪鈧磭鈧",
    "閻犲洤鐡ㄥΣ",
    "鏍囬",
    "鏋舵瀯",
    "绀轰緥闄勫綍",
    "鍏ラ棬涓庝娇鐢",
    "杩欎竴椤",
    "鏈€鐭彲杩愯鐢ㄦ硶",
    "鍏抽敭浠ｇ爜鐗囨",
    "鐩稿叧 API",
    "闂傚爼鍋",
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
SELF_PATTERN_EXEMPT_FILES = {"check_text_quality.py", "test_cleanup_guards.py"}
VAGUE_PARAM_FRAGMENTS = ("透传给底层", "附加参数", "额外参数")
KWARG_SUPPORT_MARKERS = (
    "支持键",
    "csv_read_options",
    "provider_options",
    "extras",
    "skiprows",
    "delimiter",
    "header",
    "names",
    "index_col",
    "encoding",
    "comment",
    "decimal",
    "storage_scheme",
    "set_filename",
    "workers",
    "chunk_size",
    "load_mode",
    "categories",
    "initial",
    "dtype",
    "kind",
    "fill_value",
    "bounds_error",
    "assume_sorted",
    "freq_range",
    "baseline_order",
    "truncate_range",
    "存储模式",
    "存储方案",
    "命名解析器",
    "严格模式",
    "并发数",
    "分类过滤",
    "保存参数",
    "加载参数",
    "连接参数",
    "格式控制项",
    "单位映射",
    "CSV 读取参数",
    "批量保存参数",
    "批量加载参数",
)
VIBRATION_METADATA_DESCRIPTION_KEYWORDS = (
    "工况编号",
    "测点编号",
    "仪器编号",
    "方向编号",
    "记录编号",
    "时间戳",
    "附加业务信息",
)


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


def _iter_public_runtime_kwarg_files() -> list[Path]:
    return _iter_files(PUBLIC_RUNTIME_KWARG_GLOBS)


def _iter_strict_type_files() -> list[Path]:
    return _iter_files(STRICT_TYPE_GLOBS)


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
        if keyword.arg != "encoding":
            continue
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
    try:
        source = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return []

    tree = ast.parse(source, filename=str(path))
    violations: list[str] = []
    rel = path.relative_to(PROJECT_ROOT)

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
        if mode is not None and "b" in mode:
            continue
        if mode is None:
            continue
        if _encoding_is_utf8(node):
            continue

        call_name = "Path.open" if is_method_open else "open"
        violations.append(f'{rel}:{node.lineno}: {call_name}() must explicitly use encoding="utf-8"')

    return violations


def _public_runtime_kwarg_doc_violations(path: Path) -> list[str]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    violations: list[str] = []
    rel = path.relative_to(PROJECT_ROOT)

    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        if node.name.startswith("_"):
            continue
        if node.args.kwarg is None:
            continue
        docstring = ast.get_docstring(node) or ""
        if not docstring.strip():
            continue
        if any(fragment in docstring for fragment in VAGUE_PARAM_FRAGMENTS) and not any(
            marker in docstring for marker in KWARG_SUPPORT_MARKERS
        ):
            violations.append(f"{rel}:{node.lineno}: public/runtime boundary var-kwargs docstring is vague")
            continue
        if node.args.kwarg.arg in docstring and not any(marker in docstring for marker in KWARG_SUPPORT_MARKERS):
            violations.append(f"{rel}:{node.lineno}: public/runtime boundary var-kwargs docstring must list keys")

    return violations


def _annotation_mentions_object(node: ast.AST | None) -> bool:
    if node is None:
        return False
    return "object" in ast.unparse(node)


def _strict_object_annotation_violations(path: Path) -> list[str]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    rel = path.relative_to(PROJECT_ROOT)
    violations: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.AnnAssign):
            if _annotation_mentions_object(node.annotation):
                target = ast.unparse(node.target)
                violations.append(f"{rel}:{node.lineno}: strict typed module must not annotate {target} with object")
            continue
        if isinstance(node, ast.arg):
            if _annotation_mentions_object(node.annotation):
                violations.append(f"{rel}:{node.lineno}: strict typed module must not annotate {node.arg} with object")
            continue
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            if node.name == "__eq__":
                continue
            if _annotation_mentions_object(node.returns):
                violations.append(
                    f"{rel}:{node.lineno}: strict typed module must not annotate return type of {node.name} with object"
                )
            continue

    return violations


def _vibration_metadata_description_violations() -> list[str]:
    path = PROJECT_ROOT / "src" / "dyntool" / "domain" / "metadata" / "types.py"
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    rel = path.relative_to(PROJECT_ROOT)
    return [
        f"{rel}: missing detailed metadata description keyword {keyword!r}"
        for keyword in VIBRATION_METADATA_DESCRIPTION_KEYWORDS
        if keyword not in text
    ]


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

    for path in _iter_public_runtime_kwarg_files():
        violations.extend(_public_runtime_kwarg_doc_violations(path))

    for path in _iter_strict_type_files():
        violations.extend(_strict_object_annotation_violations(path))

    violations.extend(_vibration_metadata_description_violations())

    if violations:
        print("Text quality check failed:")
        for violation in violations:
            print(f"  - {violation}")
        return 1

    print("Text quality check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
