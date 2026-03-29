"""文档系统与正式示例口径守卫测试。"""

from __future__ import annotations

import importlib.util
from pathlib import Path
import tomllib

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
USAGE_PAGES = [
    PROJECT_ROOT / "docs" / "usage" / "index.md",
    PROJECT_ROOT / "docs" / "usage" / "01_input_and_types.md",
    PROJECT_ROOT / "docs" / "usage" / "02_samples_and_sets.md",
    PROJECT_ROOT / "docs" / "usage" / "03_processing_and_results.md",
    PROJECT_ROOT / "docs" / "usage" / "04_storage_rules.md",
    PROJECT_ROOT / "docs" / "usage" / "05_plotting_logging_resources.md",
]


def _load_script_module(name: str, path: Path) -> object:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_mkdocs_scaffold_exists() -> None:
    required_files = [
        PROJECT_ROOT / "mkdocs.yml",
        PROJECT_ROOT / "docs" / "index.md",
        PROJECT_ROOT / "docs" / "user_guide.md",
        PROJECT_ROOT / "docs" / "workflow_guide.md",
        PROJECT_ROOT / "docs" / "examples_overview.md",
        PROJECT_ROOT / "docs" / "examples_manifest.toml",
        *USAGE_PAGES,
        PROJECT_ROOT / "docs" / "api" / "index.md",
        PROJECT_ROOT / "docs" / "api" / "public_api.md",
        PROJECT_ROOT / "docs" / "api" / "internal_api.md",
        PROJECT_ROOT / "docs" / "developer" / "index.md",
        PROJECT_ROOT / "docs" / "developer" / "custom_extension.md",
        PROJECT_ROOT / "docs" / "gen_snippets.py",
        PROJECT_ROOT / "docs" / "gen_reference_pages.py",
    ]
    missing = [path.relative_to(PROJECT_ROOT).as_posix() for path in required_files if not path.exists()]
    assert not missing, f"缺少文档脚手架文件: {missing}"


def test_mkdocs_config_uses_expected_stack_and_layout() -> None:
    config_path = PROJECT_ROOT / "mkdocs.yml"
    config_text = config_path.read_text(encoding="utf-8")
    payload = yaml.safe_load(config_text)

    assert "material" in config_text
    assert "mkdocstrings" in config_text
    assert "gen-files" in config_text
    assert "literate-nav" in config_text
    assert "docs/gen_reference_pages.py" in config_text
    assert "docs/gen_snippets.py" in config_text
    assert "use_directory_urls: false" in config_text
    top_level_labels = [next(iter(item)) for item in payload["nav"]]
    assert top_level_labels == ["首页", "入门与使用", "教程", "参考与附录"]


def test_examples_manifest_is_machine_readable() -> None:
    manifest = tomllib.loads((PROJECT_ROOT / "docs" / "examples_manifest.toml").read_text(encoding="utf-8"))

    assert "example" in manifest
    example_ids = {entry["id"] for entry in manifest["example"]}
    assert "import_and_normalize" in example_ids
    assert "resource_driven_eval" in example_ids
    assert "custom_extension" in example_ids
    custom_extension = next(entry for entry in manifest["example"] if entry["id"] == "custom_extension")
    assert custom_extension["kind"] == "internal"


def test_examples_overview_excludes_internal_custom_extension() -> None:
    overview = (PROJECT_ROOT / "docs" / "examples_overview.md").read_text(encoding="utf-8")
    assert "examples/10_scenarios/01_import_and_normalize/main.py" in overview
    assert "examples/10_scenarios/08_custom_extension/main.py" not in overview


def test_public_api_page_mentions_all_formal_module_apis() -> None:
    text = (PROJECT_ROOT / "docs" / "api" / "public_api.md").read_text(encoding="utf-8")

    assert "dyntool.storage" in text
    assert "dyntool.plotting" in text
    assert "dyntool.logging" in text
    assert "dyntool.config" in text
    assert "dyntool.resources" in text
    assert "`dyntool.resource`" not in text


def test_formal_docs_do_not_use_removed_entrypoints() -> None:
    scan_roots = [
        PROJECT_ROOT / "README.md",
        PROJECT_ROOT / "ARCHITECTURE.md",
        PROJECT_ROOT / "AGENTS.md",
        PROJECT_ROOT / "docs" / "api",
        PROJECT_ROOT / "docs" / "usage",
        PROJECT_ROOT / "docs" / "workflows",
        PROJECT_ROOT / "docs" / "index.md",
        PROJECT_ROOT / "docs" / "user_guide.md",
        PROJECT_ROOT / "docs" / "examples_overview.md",
    ]
    forbidden = (
        "`dyntool.resource`",
        "dyntool.resource.",
        "DynTool(",
        "from dyntool import DynTool",
        "from dyntool.domain",
        "import dyntool.domain",
        "from dyntool.application",
        "import dyntool.application",
        "interfaces -> application",
    )
    offenders: list[str] = []
    for root in scan_roots:
        paths = [root] if root.is_file() else sorted(root.rglob("*.md"))
        for path in paths:
            text = path.read_text(encoding="utf-8")
            if any(token in text for token in forbidden):
                offenders.append(path.relative_to(PROJECT_ROOT).as_posix())

    assert offenders == [], f"正式文档仍包含已删除入口: {offenders}"


def test_active_docs_do_not_use_workspace_absolute_links() -> None:
    scan_roots = [PROJECT_ROOT / "README.md", PROJECT_ROOT / "ARCHITECTURE.md", PROJECT_ROOT / "docs"]
    offenders: list[str] = []
    for root in scan_roots:
        paths = [root] if root.is_file() else sorted(root.rglob("*.md"))
        for path in paths:
            text = path.read_text(encoding="utf-8")
            if "/D:/BaiduSyncdisk/13_CodeRepository/Projects/AdvDynTool/" in text:
                offenders.append(path.relative_to(PROJECT_ROOT).as_posix())

    assert offenders == [], f"文档仍包含工作区绝对路径: {offenders}"


def test_formal_navigation_pages_declare_stability() -> None:
    payload = yaml.safe_load((PROJECT_ROOT / "mkdocs.yml").read_text(encoding="utf-8"))
    labels = ("Public API", "Internal API", "Private / implementation detail")

    def flatten(items: list[object]) -> list[str]:
        result: list[str] = []
        for item in items:
            if isinstance(item, str):
                result.append(item)
            elif isinstance(item, dict):
                for value in item.values():
                    if isinstance(value, str):
                        result.append(value)
                    elif isinstance(value, list):
                        result.extend(flatten(value))
        return result

    for rel in flatten(payload["nav"]):
        text = (PROJECT_ROOT / "docs" / rel).read_text(encoding="utf-8")
        assert any(label in text for label in labels), f"{rel} 缺少稳定性标签"


def test_custom_extension_doc_is_internal_only() -> None:
    text = (PROJECT_ROOT / "docs" / "developer" / "custom_extension.md").read_text(encoding="utf-8")

    assert "Internal API" in text
    assert "examples/10_scenarios/08_custom_extension/main.py" in text


def test_docstring_coverage_script_passes() -> None:
    script = _load_script_module(
        "check_docstring_coverage_script",
        PROJECT_ROOT / "scripts" / "check_docstring_coverage.py",
    )
    assert script.main() == 0


def test_mkdocs_site_check_script_passes() -> None:
    script = _load_script_module("check_mkdocs_site_script", PROJECT_ROOT / "scripts" / "check_mkdocs_site.py")
    assert script.main() == 0


def test_resource_consistency_script_passes() -> None:
    script = _load_script_module(
        "check_resource_consistency_script",
        PROJECT_ROOT / "scripts" / "check_resource_consistency.py",
    )
    assert script.main() == 0
