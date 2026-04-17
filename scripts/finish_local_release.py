"""本地补丁版本收口与发布脚本。"""

import argparse
from dataclasses import dataclass
from datetime import date
import fnmatch
import os
from pathlib import Path
import re
import shutil
import subprocess


PROJECT_ROOT = Path(__file__).resolve().parent.parent
VERSION_FILE = PROJECT_ROOT / "src" / "dyntool" / "_version.py"
README_FILE = PROJECT_ROOT / "README.md"
DOCS_INDEX_FILE = PROJECT_ROOT / "docs" / "index.md"
CHANGELOG_FILE = PROJECT_ROOT / "CHANGELOG.md"
REMOTE_NAME = "origin"
LOCAL_MANAGEMENT_FILES = {"task_plan.md", "progress.md", "TODO.md", "findings.md"}
GENERATED_ARTIFACT_DIRS = (
    PROJECT_ROOT / ".ruff_cache",
    PROJECT_ROOT / ".pytest_cache",
    PROJECT_ROOT / "site",
    PROJECT_ROOT / "docs" / "_build",
)

GATE_COMMANDS: tuple[tuple[str, ...], ...] = (
    ("uv", "run", "python", "-B", "scripts/check_codex_assets.py"),
    ("uv", "run", "ruff", "check", "--no-cache", "src/dyntool", "tests", "examples"),
    ("uv", "run", "ruff", "format", "--check", "src/dyntool", "tests", "examples"),
    ("uv", "run", "python", "-B", "scripts/check_layer_imports.py"),
    ("uv", "run", "python", "-B", "scripts/check_text_quality.py"),
    ("uv", "run", "python", "-B", "scripts/check_docstring_coverage.py"),
    ("uv", "run", "python", "-B", "scripts/check_public_api_baseline.py"),
    ("uv", "run", "python", "-B", "scripts/check_resource_consistency.py"),
    ("uv", "run", "python", "-B", "scripts/check_mkdocs_site.py"),
    ("uv", "run", "python", "-B", "-m", "mkdocs", "build", "--strict", "--site-dir", ".pytest_tmp/mkdocs-site"),
    ("uv", "run", "pyright", "src/dyntool", "tests/typing_public_api.py"),
    (
        "uv",
        "run",
        "python",
        "-B",
        "-m",
        "pytest",
        "-q",
        "--basetemp",
        ".pytest_tmp/pytest",
        "-p",
        "no:cacheprovider",
    ),
)


@dataclass(frozen=True)
class CommitGroup:
    """固定提交分组。"""

    key: str
    message: str
    patterns: tuple[str, ...]


COMMIT_GROUPS: tuple[CommitGroup, ...] = (
    CommitGroup(
        key="core",
        message="feat: finalize sample storage and sqlite_h5 v2 flow",
        patterns=(
            "src/dyntool/__init__.py",
            "src/dyntool/_version.py",
            "src/dyntool/domain/samples/**",
            "src/dyntool/infrastructure/sample_*.py",
            "src/dyntool/infrastructure/storage_options.py",
            "src/dyntool/plotting/**",
            "src/dyntool/storage/**",
            "src/dyntool/resources/__init__.py",
            "src/dyntool/resource/__init__.py",
            "examples/_scenario_impls.py",
            "src/dyntool/resources/standards/**",
        ),
    ),
    CommitGroup(
        key="tests",
        message="test: align baselines, guards, and storage verification",
        patterns=(
            "tests/**",
            "scripts/check_*.py",
            "scripts/benchmark_set_sqlite_h5_io.py",
            "scripts/inspect_storage_repository.py",
            "docs/baselines/**",
        ),
    ),
    CommitGroup(
        key="docs",
        message="docs: synchronize storage, workflow, and public surface docs",
        patterns=(
            "AGENTS.md",
            "README.md",
            "CHANGELOG.md",
            "ARCHITECTURE.md",
            "docs/**",
        ),
    ),
    CommitGroup(
        key="chore",
        message="chore: add repository hygiene and local release helpers",
        patterns=(
            "pyproject.toml",
            "sitecustomize.py",
            "scripts/_repo_hygiene.py",
            "scripts/fix_text_hygiene.py",
            "scripts/clean_generated_artifacts.py",
            "scripts/finish_local_release.py",
        ),
    ),
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="执行本地补丁版本收口。")
    parser.add_argument("--target-version", default=None, help="目标版本号；默认自动提升补丁位。")
    parser.add_argument("--allow-main-release", action="store_true", help="允许在 main 上执行当前阶段收口。")
    parser.add_argument("--skip-push", action="store_true", help="只做本地 commit 与 tag，不推送远端。")
    parser.add_argument("--dry-run", action="store_true", help="只输出计划，不执行变更。")
    return parser


def _run(command: tuple[str, ...], *, capture_output: bool = False) -> subprocess.CompletedProcess[str]:
    effective_command = list(command)
    if effective_command and effective_command[0] == "git":
        effective_command[1:1] = ["-c", "core.quotePath=false"]
    env = os.environ.copy()
    if tuple(command[:6]) == ("uv", "run", "python", "-B", "-m", "mkdocs"):
        env.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    return subprocess.run(
        effective_command,
        cwd=PROJECT_ROOT,
        check=True,
        text=True,
        capture_output=capture_output,
        encoding="utf-8",
        env=env,
    )


def _git_output(*args: str) -> str:
    return _run(("git", *args), capture_output=True).stdout.strip()


def _read_current_version(version_file: Path = VERSION_FILE) -> str:
    text = version_file.read_text(encoding="utf-8")
    match = re.search(r'__version__\s*=\s*"(?P<version>\d+\.\d+\.\d+)"', text)
    if match is None:
        raise RuntimeError(f"未在 {version_file} 中找到版本号。")
    return match.group("version")


def _bump_patch_version(version: str) -> str:
    major, minor, patch = version.split(".")
    return f"{major}.{minor}.{int(patch) + 1}"


def _replace_required(text: str, old: str, new: str, *, path: Path) -> str:
    if old not in text:
        raise RuntimeError(f"未在 {path} 中找到 {old!r}。")
    return text.replace(old, new)


def _update_version_strings(old_version: str, new_version: str) -> None:
    version_text = VERSION_FILE.read_text(encoding="utf-8")
    VERSION_FILE.write_text(
        _replace_required(version_text, old_version, new_version, path=VERSION_FILE), encoding="utf-8"
    )

    readme_text = README_FILE.read_text(encoding="utf-8")
    README_FILE.write_text(
        _replace_required(
            readme_text, f"当前发布版本：`v{old_version}`", f"当前发布版本：`v{new_version}`", path=README_FILE
        ),
        encoding="utf-8",
    )

    docs_text = DOCS_INDEX_FILE.read_text(encoding="utf-8")
    DOCS_INDEX_FILE.write_text(
        _replace_required(
            docs_text, f"当前发布版本：`v{old_version}`", f"当前发布版本：`v{new_version}`", path=DOCS_INDEX_FILE
        ),
        encoding="utf-8",
    )


def _build_changelog_entry(new_version: str, today: date | None = None) -> str:
    release_date = (today or date.today()).isoformat()
    return (
        f"## v{new_version} - {release_date}\n\n"
        "### 当前阶段收口\n\n"
        "- 完成 `SET_SQLITE_H5` v2 正式化、样本/样本集主链联动、自动识别、完整性校验与摘要对比相关收口。\n"
        "- 同步测试、baseline、性能基线与仓库门禁，确保当前主目录中的单一集成主题具备可回归性。\n"
        "- 收敛正式文档、开发者工作流与仓库卫生脚本，并建立本地补丁版本收口入口。\n\n"
    )


def _prepend_changelog(new_version: str) -> None:
    original = CHANGELOG_FILE.read_text(encoding="utf-8")
    marker = "## v"
    marker_index = original.find(marker)
    if marker_index == -1:
        raise RuntimeError("CHANGELOG.md 中未找到版本段落。")
    entry = _build_changelog_entry(new_version)
    CHANGELOG_FILE.write_text(original[:marker_index] + entry + original[marker_index:], encoding="utf-8")


def _current_branch() -> str:
    return _git_output("branch", "--show-current")


def _status_paths() -> set[str]:
    changed = {path for path in _git_output("diff", "--name-only").splitlines() if path}
    changed.update(path for path in _git_output("diff", "--cached", "--name-only").splitlines() if path)
    changed.update(path for path in _git_output("ls-files", "--others", "--exclude-standard").splitlines() if path)
    return changed


def _is_local_management_path(path: str) -> bool:
    return Path(path).name in LOCAL_MANAGEMENT_FILES


def _matches_any(path: str, patterns: tuple[str, ...]) -> bool:
    return any(fnmatch.fnmatch(path, pattern) for pattern in patterns)


def classify_paths(paths: set[str]) -> tuple[dict[str, list[str]], list[str]]:
    grouped: dict[str, list[str]] = {group.key: [] for group in COMMIT_GROUPS}
    uncovered: list[str] = []
    for path in sorted(paths):
        if _is_local_management_path(path):
            continue
        matched = False
        for group in COMMIT_GROUPS:
            if _matches_any(path, group.patterns):
                grouped[group.key].append(path)
                matched = True
                break
        if not matched:
            uncovered.append(path)
    return grouped, uncovered


def _ensure_safe_state(*, allow_main_release: bool) -> None:
    branch = _current_branch()
    if branch == "main" and not allow_main_release:
        raise RuntimeError("当前位于 main；若要执行当前阶段收口，请显式传入 --allow-main-release。")
    if _git_output("remote") == "":
        raise RuntimeError("未检测到远端仓库，无法执行发布收口。")
    if _git_output("diff", "--name-only", "--diff-filter=U"):
        raise RuntimeError("当前存在未解决冲突，无法继续。")


def _run_quality_gates() -> None:
    _clean_generated_artifacts()
    for command in GATE_COMMANDS:
        if "pytest" in command:
            _clean_generated_artifacts()
        print(f"[gate] {' '.join(command)}")
        _run(command)


def _clean_generated_artifacts() -> None:
    for path in GENERATED_ARTIFACT_DIRS:
        if path.exists():
            shutil.rmtree(path)
    for path in PROJECT_ROOT.rglob("__pycache__"):
        if path.is_dir():
            shutil.rmtree(path)


def _stage_paths(paths: list[str]) -> None:
    if not paths:
        return
    _run(("git", "add", "-A", "--", *paths))


def _commit(message: str) -> bool:
    if _git_output("diff", "--cached", "--name-only") == "":
        return False
    _run(("git", "commit", "-m", message))
    return True


def _create_annotated_tag(tag_name: str) -> None:
    _run(("git", "tag", "-a", tag_name, "-m", tag_name))


def _push_current_branch_and_tag(tag_name: str) -> None:
    branch = _current_branch()
    _run(("git", "push", REMOTE_NAME, branch))
    _run(("git", "push", REMOTE_NAME, tag_name))


def _print_group_plan(grouped: dict[str, list[str]], target_version: str) -> None:
    print(f"[plan] 目标版本: v{target_version}")
    for group in COMMIT_GROUPS:
        paths = grouped[group.key]
        print(f"[plan] {group.message}: {len(paths)} files")
        for path in paths:
            print(f"  - {path}")


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    _ensure_safe_state(allow_main_release=args.allow_main_release)

    current_version = _read_current_version()
    target_version = args.target_version or _bump_patch_version(current_version)
    changed_paths = _status_paths()
    grouped, uncovered = classify_paths(changed_paths)
    if uncovered:
        raise RuntimeError(f"存在未纳入固定提交分组的路径：{uncovered}")

    if args.dry_run:
        _print_group_plan(grouped, target_version)
        return 0

    _run_quality_gates()

    for group in COMMIT_GROUPS:
        _stage_paths(grouped[group.key])
        created = _commit(group.message)
        if created:
            print(f"[commit] {group.message}")

    _update_version_strings(current_version, target_version)
    _prepend_changelog(target_version)
    _stage_paths(
        [
            str(VERSION_FILE.relative_to(PROJECT_ROOT)).replace("\\", "/"),
            str(README_FILE.relative_to(PROJECT_ROOT)).replace("\\", "/"),
            str(DOCS_INDEX_FILE.relative_to(PROJECT_ROOT)).replace("\\", "/"),
            str(CHANGELOG_FILE.relative_to(PROJECT_ROOT)).replace("\\", "/"),
        ]
    )
    _commit(f"release: v{target_version}")
    tag_name = f"v{target_version}"
    _create_annotated_tag(tag_name)

    if not args.skip_push:
        _push_current_branch_and_tag(tag_name)

    print(f"[done] 已完成 v{target_version} 本地收口。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
