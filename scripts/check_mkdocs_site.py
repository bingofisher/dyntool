"""检查 MkDocs 文档站配置、正式文档口径和示例映射。"""

from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MKDOCS_CONFIG = PROJECT_ROOT / "mkdocs.yml"
EXAMPLES_MANIFEST = PROJECT_ROOT / "docs" / "examples_manifest.toml"
ABSOLUTE_WORKSPACE_LINK_FRAGMENT = "/D:/BaiduSyncdisk/13_CodeRepository/Projects/AdvDynTool/"
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
    "docs/usage/06_plotting_config_reference.md",
    "docs/api/index.md",
    "docs/api/public_api.md",
    "docs/api/internal_api.md",
    "docs/developer/index.md",
    "docs/developer/custom_extension.md",
    "docs/gen_snippets.py",
    "docs/gen_reference_pages.py",
    "docs/reference/index.md",
)
TOP_LEVEL_NAV_LABELS = ("首页", "入门与使用", "教程", "参考与附录")
STABILITY_LABELS = ("Public API", "Internal API", "Private / implementation detail")
FORMAL_DOC_SCAN_ROOTS = (
    PROJECT_ROOT / "README.md",
    PROJECT_ROOT / "ARCHITECTURE.md",
    PROJECT_ROOT / "AGENTS.md",
    PROJECT_ROOT / "docs" / "api",
    PROJECT_ROOT / "docs" / "usage",
    PROJECT_ROOT / "docs" / "workflows",
    PROJECT_ROOT / "docs" / "systems",
    PROJECT_ROOT / "docs" / "index.md",
    PROJECT_ROOT / "docs" / "user_guide.md",
    PROJECT_ROOT / "docs" / "workflow_guide.md",
    PROJECT_ROOT / "docs" / "examples_overview.md",
    PROJECT_ROOT / "docs" / "reference" / "index.md",
)
FORMAL_FORBIDDEN_TOKENS = (
    "`dyntool.resource`",
    "DynTool(",
    "from dyntool import DynTool",
    "from dyntool.domain",
    "import dyntool.domain",
    "from dyntool.application",
    "import dyntool.application",
    "interfaces -> application",
)
EXAMPLE_PATH_PATTERN = re.compile(r"examples/[A-Za-z0-9_./()-]+(?:\.py|README\.md)")


def _flatten_nav(items: list[object]) -> list[str]:
    """提取导航中的全部文档路径。"""

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


def _iter_markdown_files(root: Path) -> list[Path]:
    """返回根路径下的 Markdown 文件。"""

    if root.is_file():
        return [root]
    return sorted(root.rglob("*.md"))


def _load_examples_manifest() -> list[dict[str, object]]:
    """读取示例清单。"""

    payload = tomllib.loads(EXAMPLES_MANIFEST.read_text(encoding="utf-8"))
    return list(payload.get("example", []))


def _check_required_docs(violations: list[str]) -> None:
    """检查正式文档脚手架文件。"""

    for rel in REQUIRED_DOC_FILES:
        if not (PROJECT_ROOT / rel).exists():
            violations.append(f"{rel}: missing")


def _check_mkdocs_config(violations: list[str]) -> dict[str, object] | None:
    """检查 MkDocs 配置。"""

    if not MKDOCS_CONFIG.exists():
        violations.append("mkdocs.yml: missing")
        return None

    config_text = MKDOCS_CONFIG.read_text(encoding="utf-8")
    for token in ("material", "mkdocstrings", "gen-files", "literate-nav", "use_directory_urls: false"):
        if token not in config_text:
            violations.append(f"mkdocs.yml: missing required token {token!r}")

    payload = yaml.safe_load(config_text)
    top_level_labels = tuple(next(iter(item)) for item in payload.get("nav", []))
    if top_level_labels != TOP_LEVEL_NAV_LABELS:
        violations.append(f"mkdocs.yml: unexpected top-level nav {top_level_labels!r}")
    return payload


def _check_nav_pages_have_stability_labels(config: dict[str, object], violations: list[str]) -> None:
    """检查导航页的稳定性标签。"""

    for rel in _flatten_nav(config.get("nav", [])):
        path = PROJECT_ROOT / "docs" / rel
        text = path.read_text(encoding="utf-8")
        if not any(label in text for label in STABILITY_LABELS):
            violations.append(f"{path.relative_to(PROJECT_ROOT).as_posix()}: missing stability label")


def _check_formal_docs_tokens(violations: list[str]) -> None:
    """检查正式文档口径中的禁止词。"""

    for root in FORMAL_DOC_SCAN_ROOTS:
        for path in _iter_markdown_files(root):
            text = path.read_text(encoding="utf-8")
            rel = path.relative_to(PROJECT_ROOT).as_posix()
            if ABSOLUTE_WORKSPACE_LINK_FRAGMENT in text:
                violations.append(f"{rel}: contains workspace absolute links")
            for token in FORMAL_FORBIDDEN_TOKENS:
                if token in text:
                    violations.append(f"{rel}: contains forbidden token {token!r}")


def _check_example_manifest(violations: list[str]) -> None:
    """检查示例清单和正式场景边界。"""

    entries = _load_examples_manifest()
    if not entries:
        violations.append("docs/examples_manifest.toml: no examples defined")
        return

    ids = {entry["id"] for entry in entries}
    for example_id in ("import_and_normalize", "resource_driven_eval", "custom_extension"):
        if example_id not in ids:
            violations.append(f"docs/examples_manifest.toml: missing example {example_id!r}")

    custom_extension = next(entry for entry in entries if entry["id"] == "custom_extension")
    if custom_extension.get("kind") != "internal":
        violations.append("docs/examples_manifest.toml: custom_extension must be internal")


def _check_examples_overview(violations: list[str]) -> None:
    """检查正式示例总览。"""

    overview = (PROJECT_ROOT / "docs" / "examples_overview.md").read_text(encoding="utf-8")
    if "examples/10_scenarios/08_custom_extension/main.py" in overview:
        violations.append("docs/examples_overview.md: custom_extension should not appear in formal overview")
    for rel in set(EXAMPLE_PATH_PATTERN.findall(overview)):
        if not (PROJECT_ROOT / rel).exists():
            violations.append(f"docs/examples_overview.md: references missing example path {rel}")


def _check_internal_example_readme(violations: list[str]) -> None:
    """检查内部示例标注。"""

    text = (PROJECT_ROOT / "examples" / "10_scenarios" / "08_custom_extension" / "README.md").read_text(
        encoding="utf-8"
    )
    if "Internal API" not in text:
        violations.append("examples/10_scenarios/08_custom_extension/README.md: missing Internal API label")


def main() -> int:
    """执行 MkDocs 站点一致性检查。"""

    violations: list[str] = []
    _check_required_docs(violations)
    config = _check_mkdocs_config(violations)
    if config is not None:
        _check_nav_pages_have_stability_labels(config, violations)
    _check_formal_docs_tokens(violations)
    _check_example_manifest(violations)
    _check_examples_overview(violations)
    _check_internal_example_readme(violations)

    if violations:
        print("MkDocs site check failed:")
        for item in violations:
            print(f"  - {item}")
        return 1

    print("MkDocs site check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
