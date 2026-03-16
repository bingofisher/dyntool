"""检查阶段执行审查与最终校核记录是否完整。"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TASK_PLAN_PATH = PROJECT_ROOT / "task_plan.md"
PROGRESS_PATH = PROJECT_ROOT / "progress.md"
DOC_PATH = PROJECT_ROOT / "docs" / "plans" / "execution_review_plan.md"

TASK_PLAN_REQUIRED_SECTIONS = (
    "## 持续执行与审查规则",
    "## 阶段计划",
    "## 最终审查",
)
PROGRESS_REQUIRED_SECTIONS = (
    "## 执行程度标尺",
    "## 持续执行规则",
    "## 阶段状态总览",
    "## 阶段审查记录",
    "## 最终审查记录",
)
DOC_REQUIRED_SECTIONS = (
    "## 目标",
    "## 阶段审查流程",
    "## 最终审查流程",
    "## 持续执行节奏",
    "## 命令清单",
)
PHASE_RE = re.compile(r"^### (Phase \d+)", re.MULTILINE)
TASK_PLAN_PHASE_SUBSECTIONS = (
    "#### 实施任务",
    "#### 阶段审查任务",
    "#### 持续执行动作",
    "#### 完成判据",
)
STATUS_ROW_RE = re.compile(r"^\|\s*(Phase \d+)\s*\|", re.MULTILINE)
FINAL_CHECKBOX_RE = re.compile(r"^- \[(?P<mark>[ xX])\] ", re.MULTILINE)


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _require_sections(*, text: str, path: Path, sections: tuple[str, ...]) -> list[str]:
    violations: list[str] = []
    rel = path.relative_to(PROJECT_ROOT)
    for section in sections:
        if section not in text:
            violations.append(f"{rel}: missing required section {section!r}")
    return violations


def _extract_phase_blocks(text: str) -> dict[str, str]:
    matches = list(PHASE_RE.finditer(text))
    blocks: dict[str, str] = {}
    for index, match in enumerate(matches):
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        blocks[match.group(1)] = text[start:end]
    return blocks


def _check_task_plan_phases(task_plan_text: str) -> tuple[list[str], list[str]]:
    violations: list[str] = []
    phase_blocks = _extract_phase_blocks(task_plan_text)
    for phase_name, block in phase_blocks.items():
        for subsection in TASK_PLAN_PHASE_SUBSECTIONS:
            if subsection not in block:
                violations.append(f"task_plan.md: {phase_name} missing required subsection {subsection!r}")
    return violations, list(phase_blocks)


def _check_progress_phase_coverage(progress_text: str, phase_names: list[str]) -> list[str]:
    violations: list[str] = []
    status_rows = set(STATUS_ROW_RE.findall(progress_text))
    progress_phase_blocks = set(_extract_phase_blocks(progress_text))
    for phase_name in phase_names:
        if phase_name not in status_rows:
            violations.append(f"progress.md: missing phase status row for {phase_name}")
        if phase_name not in progress_phase_blocks:
            violations.append(f"progress.md: missing phase review record for {phase_name}")
    return violations


def _check_strict(progress_text: str) -> list[str]:
    violations: list[str] = []
    status_lines = [line.strip() for line in progress_text.splitlines() if line.startswith("| Phase ")]
    for line in status_lines:
        columns = [part.strip() for part in line.strip("|").split("|")]
        if len(columns) < 4:
            violations.append(f"progress.md: malformed phase status row {line!r}")
            continue
        phase_name, status, implementation, review = columns[:4]
        if status != "审查通过":
            violations.append(f"progress.md: {phase_name} is not ready for strict final audit ({status})")
        if implementation != "100%":
            violations.append(f"progress.md: {phase_name} implementation progress is not 100% ({implementation})")
        if review != "100%":
            violations.append(f"progress.md: {phase_name} review progress is not 100% ({review})")
    final_section = progress_text.split("## 最终审查记录", maxsplit=1)
    if len(final_section) != 2:
        violations.append("progress.md: missing final review section for strict mode")
        return violations
    unchecked = [
        match.group(0).strip() for match in FINAL_CHECKBOX_RE.finditer(final_section[1]) if match.group("mark") != "x"
    ]
    if unchecked:
        violations.append("progress.md: final review checklist still contains unchecked items")
    return violations


def main() -> int:
    parser = argparse.ArgumentParser(description="Check staged execution review artifacts.")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Require all phase rows and final review items to be fully completed.",
    )
    args = parser.parse_args()

    violations: list[str] = []
    task_plan_text = _read_text(TASK_PLAN_PATH)
    progress_text = _read_text(PROGRESS_PATH)
    doc_text = _read_text(DOC_PATH)

    violations.extend(
        _require_sections(
            text=task_plan_text,
            path=TASK_PLAN_PATH,
            sections=TASK_PLAN_REQUIRED_SECTIONS,
        )
    )
    violations.extend(
        _require_sections(
            text=progress_text,
            path=PROGRESS_PATH,
            sections=PROGRESS_REQUIRED_SECTIONS,
        )
    )
    violations.extend(
        _require_sections(
            text=doc_text,
            path=DOC_PATH,
            sections=DOC_REQUIRED_SECTIONS,
        )
    )

    task_plan_violations, phase_names = _check_task_plan_phases(task_plan_text)
    violations.extend(task_plan_violations)
    violations.extend(_check_progress_phase_coverage(progress_text, phase_names))

    if args.strict:
        violations.extend(_check_strict(progress_text))

    if violations:
        print("Execution review check failed:")
        for violation in violations:
            print(f"  - {violation}")
        return 1

    mode = "strict" if args.strict else "standard"
    print(f"Execution review check passed ({mode}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
