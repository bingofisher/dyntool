"""检查 MkDocs 文档站配置、示例结构和示例映射。"""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path
import re

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MKDOCS_CONFIG = PROJECT_ROOT / "mkdocs.yml"
SITE_ROOT = PROJECT_ROOT / "site"
EXAMPLES_MANIFEST = PROJECT_ROOT / "docs" / "examples_manifest.toml"
REQUIRED_DOC_FILES = (
    "docs/index.md",
    "docs/user_guide.md",
    "docs/workflow_guide.md",
    "docs/examples_overview.md",
    "docs/examples_manifest.toml",
    "docs/usage/index.md",
    "docs/usage/01_input_and_types.md",
    "docs/usage/02_samples_and_sets.md",
    "docs/usage/03_processing_and_results.md",
    "docs/usage/04_storage_rules.md",
    "docs/usage/05_plotting_logging_resources.md",
    "docs/api/index.md",
    "docs/api/public_api.md",
    "docs/api/internal_api.md",
    "docs/gen_snippets.py",
    "docs/gen_reference_pages.py",
    "docs/reference/index.md",
)
FORBIDDEN_SPHINX_FILES = (
    "docs/conf.py",
    "docs/api/public_api.rst",
    "docs/api/internal_api.rst",
)
REQUIRED_BUILD_FILES = (
    "index.html",
    "usage/01_input_and_types.html",
    "usage/04_storage_rules.html",
    "api/public_api.html",
)
COMMON_MOJIBAKE_FRAGMENTS = (
    "閺傚洦銆",
    "閸忣剙绱",
    "閺嶉攱婀",
    "閸旂姾娴",
    "娣囨繂鐡",
    "闂堛垹鎮",
)
KEY_TOPIC_PAGES = (
    "docs/usage/01_input_and_types.md",
    "docs/usage/02_samples_and_sets.md",
    "docs/usage/03_processing_and_results.md",
    "docs/usage/04_storage_rules.md",
    "docs/usage/05_plotting_logging_resources.md",
)
REQUIRED_TOPIC_SECTIONS = (
    "## 这页解决什么问题",
    "## 最短可运行用法",
    "## 关键代码片段",
    "## 标准类型 / 枚举 / 参数契约",
    "## 常见误区",
    "## 相关示例",
    "## 相关 API",
)
TOP_LEVEL_NAV_LABELS = ("首页", "入门与使用", "教程", "参考与附录")
SNIPPET_PATTERN = re.compile(r"# docs:begin ([a-z0-9_]+)")
OLD_EXAMPLE_PREFIXES = (
    "examples/01_",
    "examples/02_",
    "examples/03_",
    "examples/04_",
    "examples/05_",
    "examples/06_",
    "examples/07_",
    "examples/08_",
    "examples/09_",
    "examples/10_resource_standards",
    "examples/11_custom_extension",
    "examples/90_workflows",
)


def _flatten_nav(items: list[object]) -> list[str]:
    """提取导航中的所有文档路径。"""

    result: list[str] = []
    for item in items:
        if isinstance(item, str):
            result.append(item)
            continue
        if isinstance(item, dict):
            for value in item.values():
                if isinstance(value, str):
                    result.append(value)
                elif isinstance(value, list):
                    result.extend(_flatten_nav(value))
    return result


def _load_manifest() -> list[dict[str, object]]:
    """读取示例映射清单。"""

    payload = tomllib.loads(EXAMPLES_MANIFEST.read_text(encoding="utf-8"))
    return list(payload.get("example", []))


def _iter_known_snippet_ids() -> set[str]:
    known: set[str] = set()
    for root in (PROJECT_ROOT / "examples", PROJECT_ROOT / "src" / "dyntool"):
        for path in root.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            known.update(SNIPPET_PATTERN.findall(text))
    return known


def _check_example_layout(violations: list[str]) -> None:
    scenario_root = PROJECT_ROOT / "examples" / "10_scenarios"
    recipe_root = PROJECT_ROOT / "examples" / "90_recipes"
    for rel in ("examples/README.md", "examples/10_scenarios/README.md", "examples/90_recipes/README.md"):
        if not (PROJECT_ROOT / rel).exists():
            violations.append(f"{rel}: missing")

    for path in sorted(scenario_root.iterdir()):
        if not path.is_dir():
            continue
        if not (path / "README.md").exists():
            violations.append(f"{path.relative_to(PROJECT_ROOT).as_posix()}/README.md: missing")
        if not (path / "main.py").exists():
            violations.append(f"{path.relative_to(PROJECT_ROOT).as_posix()}/main.py: missing")

    for path in sorted(recipe_root.iterdir()):
        if not path.is_dir():
            continue
        if not (path / "README.md").exists():
            violations.append(f"{path.relative_to(PROJECT_ROOT).as_posix()}/README.md: missing")


def _check_no_sphinx_language(violations: list[str]) -> None:
    for rel in ("README.md", "ARCHITECTURE.md", "AGENTS.md"):
        path = PROJECT_ROOT / rel
        if path.exists() and "Sphinx" in path.read_text(encoding="utf-8"):
            violations.append(f"{rel}: should not mention Sphinx")


def _check_no_old_example_references(violations: list[str]) -> None:
    targets = [
        PROJECT_ROOT / "README.md",
        PROJECT_ROOT / "docs" / "examples_overview.md",
        PROJECT_ROOT / "docs" / "workflow_guide.md",
        *sorted((PROJECT_ROOT / "docs" / "usage").glob("*.md")),
        *sorted((PROJECT_ROOT / "docs" / "workflows").glob("*.md")),
    ]
    for path in targets:
        text = path.read_text(encoding="utf-8")
        for prefix in OLD_EXAMPLE_PREFIXES:
            if prefix in text:
                violations.append(f"{path.relative_to(PROJECT_ROOT).as_posix()}: contains legacy example path {prefix}")


def main() -> int:
    """执行 MkDocs 站点一致性检查。"""

    violations: list[str] = []

    if not MKDOCS_CONFIG.exists():
        violations.append("mkdocs.yml: missing")
    else:
        config_text = MKDOCS_CONFIG.read_text(encoding="utf-8")
        for token in ("material", "mkdocstrings", "gen-files", "literate-nav", "use_directory_urls: false"):
            if token not in config_text:
                violations.append(f"mkdocs.yml: missing required token {token!r}")
        config = yaml.safe_load(config_text)
        top_level_labels = tuple(next(iter(item)) for item in config.get("nav", []))
        if top_level_labels != TOP_LEVEL_NAV_LABELS:
            violations.append(f"mkdocs.yml: unexpected top-level nav {top_level_labels!r}")
        nav_entries = set(_flatten_nav(config.get("nav", [])))
        for required in (
            "index.md",
            "user_guide.md",
            "usage/index.md",
            "usage/01_input_and_types.md",
            "usage/02_samples_and_sets.md",
            "usage/03_processing_and_results.md",
            "usage/04_storage_rules.md",
            "usage/05_plotting_logging_resources.md",
            "workflow_guide.md",
            "examples_overview.md",
            "api/public_api.md",
            "api/index.md",
            "reference/index.md",
            "developer/index.md",
        ):
            if required not in nav_entries:
                violations.append(f"mkdocs.yml: navigation missing {required}")

    for rel in REQUIRED_DOC_FILES:
        if not (PROJECT_ROOT / rel).exists():
            violations.append(f"{rel}: missing")

    _check_example_layout(violations)
    _check_no_sphinx_language(violations)
    _check_no_old_example_references(violations)

    for rel in FORBIDDEN_SPHINX_FILES:
        if (PROJECT_ROOT / rel).exists():
            violations.append(f"{rel}: should be removed")

    manifest_entries = _load_manifest()
    if not manifest_entries:
        violations.append("docs/examples_manifest.toml: no examples defined")

    overview = (PROJECT_ROOT / "docs" / "examples_overview.md").read_text(encoding="utf-8")
    for token in ("示例附录", "场景主线", "Recipes", "功能 -> 示例 -> 文档 -> 测试"):
        if token not in overview:
            violations.append(f"docs/examples_overview.md: missing token {token!r}")

    known_snippet_ids = _iter_known_snippet_ids()

    for entry in manifest_entries:
        for key in (
            "id",
            "kind",
            "title",
            "primary_task",
            "topic",
            "featured",
            "covers",
            "snippet_ids",
            "inputs",
            "outputs",
            "script",
            "readme",
            "doc",
            "test",
        ):
            if key not in entry:
                violations.append(f"docs/examples_manifest.toml: missing key {key!r} in entry {entry!r}")
        kind = entry.get("kind")
        if kind not in {"scenario", "recipe"}:
            violations.append(f"docs/examples_manifest.toml: invalid kind {kind!r} in entry {entry.get('id')!r}")
        for key in ("covers", "snippet_ids", "inputs", "outputs"):
            if not isinstance(entry.get(key), list):
                violations.append(f"docs/examples_manifest.toml: {key} must be list in entry {entry.get('id')!r}")
        for key in ("script", "readme", "doc"):
            rel = entry.get(key)
            if isinstance(rel, str) and not (PROJECT_ROOT / rel).exists():
                violations.append(f"{rel}: missing (from examples_manifest.toml)")
        if (
            kind == "scenario"
            and isinstance(entry.get("script"), str)
            and not entry["script"].startswith("examples/10_scenarios/")
        ):
            violations.append(f"{entry['id']!r}: scenario script must live under examples/10_scenarios")
        if (
            kind == "recipe"
            and isinstance(entry.get("script"), str)
            and not entry["script"].startswith("examples/90_recipes/")
        ):
            violations.append(f"{entry['id']!r}: recipe script must live under examples/90_recipes")
        for snippet_id in entry.get("snippet_ids", []):
            if snippet_id not in known_snippet_ids:
                violations.append(
                    f"docs/examples_manifest.toml: unknown snippet id {snippet_id!r} in entry {entry.get('id')!r}"
                )
        script = entry.get("script")
        doc = entry.get("doc")
        if isinstance(script, str) and script not in overview:
            violations.append(f"docs/examples_overview.md: missing script {script}")
        if isinstance(doc, str) and doc not in overview:
            violations.append(f"docs/examples_overview.md: missing doc {doc}")

    for rel in sorted((PROJECT_ROOT / "examples" / "10_scenarios").glob("*/README.md")):
        text = rel.read_text(encoding="utf-8")
        for token in ("任务目标", "输入", "输出", "运行命令", "关键 API", "对应测试"):
            if token not in text:
                violations.append(f"{rel.relative_to(PROJECT_ROOT).as_posix()}: missing token {token!r}")

    for rel in sorted((PROJECT_ROOT / "examples" / "90_recipes").glob("*/README.md")):
        text = rel.read_text(encoding="utf-8")
        for token in ("适用场景", "最小代码", "常见误区", "关联场景"):
            if token not in text:
                violations.append(f"{rel.relative_to(PROJECT_ROOT).as_posix()}: missing token {token!r}")

    for rel in KEY_TOPIC_PAGES:
        text = (PROJECT_ROOT / rel).read_text(encoding="utf-8")
        for token in REQUIRED_TOPIC_SECTIONS:
            if token not in text:
                violations.append(f"{rel}: missing section {token!r}")
        if "```python" not in text:
            violations.append(f"{rel}: missing Python code block")
        if "--8<--" not in text:
            violations.append(f"{rel}: missing embedded snippet include")

    for rel in KEY_TOPIC_PAGES:
        featured_count = sum(
            1 for entry in manifest_entries if entry.get("topic") == rel and entry.get("featured") is True
        )
        if featured_count < 1:
            violations.append(f"{rel}: requires at least one featured example")

    if SITE_ROOT.exists():
        build_paths = [SITE_ROOT / rel for rel in REQUIRED_BUILD_FILES]
        if all(path.exists() for path in build_paths):
            for path in build_paths:
                text = path.read_text(encoding="utf-8")
                if any(fragment in text for fragment in COMMON_MOJIBAKE_FRAGMENTS):
                    violations.append(f"{path.relative_to(PROJECT_ROOT).as_posix()}: contains mojibake fragments")

    if violations:
        print("MkDocs site check failed:")
        for violation in violations:
            print(f"  - {violation}")
        return 1

    print("MkDocs site check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
