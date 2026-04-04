"""检查仓库文本质量、编码规范和常见乱码片段。"""

from __future__ import annotations

from pathlib import Path
import sys


SCRIPT_ROOT = Path(__file__).resolve().parent
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

import _repo_hygiene as repo_hygiene  # noqa: E402


print_text = repo_hygiene.print_text
PROJECT_ROOT = repo_hygiene.PROJECT_ROOT
TEXT_GLOBS = list(repo_hygiene.TEXT_GLOBS)
STRICT_CHINESE_DOC_GLOBS = list(repo_hygiene.STRICT_CHINESE_DOC_GLOBS)
COMMON_MOJIBAKE_FRAGMENTS = tuple(repo_hygiene.COMMON_MOJIBAKE_FRAGMENTS)


def _iter_text_files() -> list[Path]:
    """返回当前脚本配置下的文本文件列表。"""

    return repo_hygiene._iter_files(PROJECT_ROOT, TEXT_GLOBS)


def main(*, project_root: Path | None = None) -> int:
    """执行文本质量检查并返回进程退出码。"""

    root = (project_root or PROJECT_ROOT or SCRIPT_ROOT.parent).resolve()
    original_project_root = repo_hygiene.PROJECT_ROOT
    original_text_globs = repo_hygiene.TEXT_GLOBS
    original_strict_doc_globs = repo_hygiene.STRICT_CHINESE_DOC_GLOBS
    original_fragments = repo_hygiene.COMMON_MOJIBAKE_FRAGMENTS

    try:
        repo_hygiene.PROJECT_ROOT = root
        repo_hygiene.TEXT_GLOBS = list(TEXT_GLOBS)
        repo_hygiene.STRICT_CHINESE_DOC_GLOBS = list(STRICT_CHINESE_DOC_GLOBS)
        repo_hygiene.COMMON_MOJIBAKE_FRAGMENTS = tuple(COMMON_MOJIBAKE_FRAGMENTS)

        issues, encoding_violations, _ = repo_hygiene.scan_text_hygiene(root)
        violations = [issue.format(root) for issue in issues]
        violations.extend(encoding_violations)

        if violations:
            print_text("Text quality check failed:")
            for violation in violations:
                print_text(f"  - {violation}")
            return 1

        print_text("Text quality check passed.")
        return 0
    finally:
        repo_hygiene.PROJECT_ROOT = original_project_root
        repo_hygiene.TEXT_GLOBS = original_text_globs
        repo_hygiene.STRICT_CHINESE_DOC_GLOBS = original_strict_doc_globs
        repo_hygiene.COMMON_MOJIBAKE_FRAGMENTS = original_fragments


if __name__ == "__main__":
    raise SystemExit(main())
