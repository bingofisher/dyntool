"""清理仓库内高置信生成物。"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


SCRIPT_ROOT = Path(__file__).resolve().parent
sys.dont_write_bytecode = True
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from _repo_hygiene import format_report, print_text, remove_generated_artifact, scan_generated_artifacts  # noqa: E402


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="检查或清理仓库内高置信生成物。")
    parser.add_argument("--check", action="store_true", help="显式执行检查模式。")
    parser.add_argument("--apply", action="store_true", help="执行删除。默认只检查。")
    return parser


def main(argv: list[str] | None = None, *, project_root: Path | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.check and args.apply:
        raise SystemExit("`--check` 与 `--apply` 不能同时使用。")
    root = (project_root or SCRIPT_ROOT.parent).resolve()
    issues = scan_generated_artifacts(root)
    removed: list[str] = []
    manual_review: list[str] = []

    if args.apply:
        for issue in issues:
            try:
                remove_generated_artifact(issue.path)
                removed.append(issue.format(root))
            except OSError as exc:
                manual_review.append(f"{issue.format(root)}: {exc}")

    print_text(
        format_report(
            mode="apply" if args.apply else "check",
            scanned_files=len(issues),
            issues_found=len(issues),
            fixable_issues=len(issues),
            changed_or_removed=removed,
            manual_review=manual_review,
        )
    )

    if args.apply:
        remaining = scan_generated_artifacts(root)
        return 0 if not remaining and not manual_review else 1
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
