"""修复仓库内可安全自动处理的文本卫生问题。"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


SCRIPT_ROOT = Path(__file__).resolve().parent
sys.dont_write_bytecode = True
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from _repo_hygiene import (  # noqa: E402
    apply_low_risk_text_fixes,
    detect_text_issues,
    format_report,
    iter_python_text_io_files,
    iter_strict_doc_files,
    iter_text_files,
    print_text,
    text_io_encoding_violations,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="检查或修复仓库文本卫生问题。")
    parser.add_argument("--check", action="store_true", help="显式执行检查模式。")
    parser.add_argument("--apply", action="store_true", help="执行低风险自动修复。默认只检查。")
    return parser


def main(argv: list[str] | None = None, *, project_root: Path | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.check and args.apply:
        raise SystemExit("`--check` 与 `--apply` 不能同时使用。")
    root = (project_root or SCRIPT_ROOT.parent).resolve()
    strict_doc_files = iter_strict_doc_files(root)
    text_files = iter_text_files(root)

    changed: list[str] = []
    manual_review: list[str] = []
    issues_found = 0
    fixable_issues = 0

    for path in text_files:
        if args.apply and apply_low_risk_text_fixes(path):
            changed.append(path.relative_to(root).as_posix())

        issues = detect_text_issues(path, root, strict_doc=path in strict_doc_files)
        issues_found += len(issues)
        fixable_issues += sum(1 for issue in issues if issue.fixable)
        manual_review.extend(issue.format(root) for issue in issues if not issue.fixable)

    for path in iter_python_text_io_files(root):
        violations = text_io_encoding_violations(path, root)
        issues_found += len(violations)
        manual_review.extend(violations)

    print_text(
        format_report(
            mode="apply" if args.apply else "check",
            scanned_files=len(text_files),
            issues_found=issues_found,
            fixable_issues=fixable_issues,
            changed_or_removed=changed,
            manual_review=manual_review,
        )
    )
    return 0 if issues_found == 0 and not manual_review else 1


if __name__ == "__main__":
    raise SystemExit(main())
