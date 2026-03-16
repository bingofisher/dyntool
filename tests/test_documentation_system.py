"""MkDocs 文档站与文档门禁回归测试。"""

from __future__ import annotations

import importlib.util
from pathlib import Path
import re
import shutil
import textwrap
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
KEY_TOPIC_PAGES = USAGE_PAGES[1:]


def _extract_snippet_ids(path: Path) -> set[str]:
    text = path.read_text(encoding="utf-8")
    return set(re.findall(r"# docs:begin ([a-z0-9_]+)", text))


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
    assert not missing, f"missing documentation scaffold files: {missing}"


def test_mkdocs_config_uses_expected_stack_and_html_layout() -> None:
    config_path = PROJECT_ROOT / "mkdocs.yml"
    config = config_path.read_text(encoding="utf-8")
    payload = yaml.safe_load(config)

    assert "theme:" in config
    assert "material" in config
    assert "mkdocstrings" in config
    assert "gen-files" in config
    assert "literate-nav" in config
    assert "docs/gen_reference_pages.py" in config
    assert "docs/gen_snippets.py" in config
    assert "use_directory_urls: false" in config
    top_level_labels = [next(iter(item)) for item in payload["nav"]]
    assert top_level_labels == ["首页", "入门与使用", "教程", "参考与附录"]


def test_examples_manifest_is_machine_readable() -> None:
    manifest = tomllib.loads((PROJECT_ROOT / "docs" / "examples_manifest.toml").read_text(encoding="utf-8"))

    assert "example" in manifest
    example_ids = {entry["id"] for entry in manifest["example"]}
    assert "import_and_normalize" in example_ids
    assert "custom_extension" in example_ids
    assert "structured_payload_roundtrip" in example_ids
    for entry in manifest["example"]:
        assert entry["kind"] in {"scenario", "recipe"}
        assert "primary_task" in entry
        assert "topic" in entry
        assert "featured" in entry
        assert "covers" in entry
        assert "snippet_ids" in entry
        assert "inputs" in entry
        assert "outputs" in entry
        assert isinstance(entry["covers"], list)
        assert isinstance(entry["snippet_ids"], list)
        assert isinstance(entry["inputs"], list)
        assert isinstance(entry["outputs"], list)


def test_examples_overview_contains_manifest_mapping() -> None:
    overview = (PROJECT_ROOT / "docs" / "examples_overview.md").read_text(encoding="utf-8")
    assert "示例附录" in overview
    assert "场景主线" in overview
    assert "Recipes" in overview
    assert "examples/10_scenarios/01_import_and_normalize/main.py" in overview
    assert "examples/10_scenarios/08_custom_extension/main.py" in overview
    assert "examples/90_recipes/structured_payload_roundtrip/main.py" in overview


def test_usage_pages_have_required_sections_and_direct_code() -> None:
    required_sections = (
        "## 这页解决什么问题",
        "## 最短可运行用法",
        "## 关键代码片段",
        "## 标准类型 / 枚举 / 参数契约",
        "## 常见误区",
        "## 相关示例",
        "## 相关 API",
    )
    for path in KEY_TOPIC_PAGES:
        text = path.read_text(encoding="utf-8")
        for token in required_sections:
            assert token in text, f"{path.name} missing section {token}"
        assert "```python" in text, f"{path.name} must contain a Python code block"
        assert "--8<--" in text or "```python" in text


def test_manifest_snippet_ids_exist_in_sources() -> None:
    manifest = tomllib.loads((PROJECT_ROOT / "docs" / "examples_manifest.toml").read_text(encoding="utf-8"))
    source_dirs = [PROJECT_ROOT / "examples", PROJECT_ROOT / "src" / "dyntool"]
    known_ids: set[str] = set()
    for root in source_dirs:
        for path in root.rglob("*.py"):
            known_ids.update(_extract_snippet_ids(path))

    for entry in manifest["example"]:
        for snippet_id in entry["snippet_ids"]:
            assert snippet_id in known_ids, f"unknown snippet id {snippet_id!r} declared by {entry['id']}"


def test_docstring_coverage_script_passes() -> None:
    script = _load_script_module(
        "check_docstring_coverage_script",
        PROJECT_ROOT / "scripts" / "check_docstring_coverage.py",
    )
    assert script.main() == 0


def test_mkdocs_site_check_script_passes() -> None:
    script = _load_script_module(
        "check_mkdocs_site_script",
        PROJECT_ROOT / "scripts" / "check_mkdocs_site.py",
    )
    assert script.main() == 0


def test_docstring_coverage_script_scans_all_source_modules() -> None:
    script = _load_script_module(
        "check_docstring_coverage_script_all_source",
        PROJECT_ROOT / "scripts" / "check_docstring_coverage.py",
    )

    target_files = {path.relative_to(PROJECT_ROOT).as_posix() for path in script._iter_target_files()}

    assert "src/dyntool/storage/runtime.py" in target_files
    assert "src/dyntool/infrastructure/sample_set_storage.py" in target_files


def test_docstring_coverage_script_checks_focused_structure() -> None:
    script = _load_script_module(
        "check_docstring_coverage_script_structure",
        PROJECT_ROOT / "scripts" / "check_docstring_coverage.py",
    )

    violations: list[str] = []
    for path in script._iter_target_files():
        violations.extend(script._iter_structure_violations(path))

    assert violations == []


def test_docstring_coverage_script_ignores_private_class_methods() -> None:
    script = _load_script_module(
        "check_docstring_coverage_script_private_class",
        PROJECT_ROOT / "scripts" / "check_docstring_coverage.py",
    )
    temp_dir = PROJECT_ROOT / "tmp" / "docstring_coverage_test"
    temp_dir.mkdir(parents=True, exist_ok=True)
    module_path = temp_dir / "private_module.py"
    try:
        module_path.write_text(
            textwrap.dedent(
                '''\
                """临时模块。"""

                class _InternalHelper:
                    def exposed_name(self) -> None:
                        pass
                '''
            ),
            encoding="utf-8",
        )

        violations = script._iter_missing_docstrings(module_path)

        assert violations == []
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_docstring_coverage_script_reports_missing_focused_sections(monkeypatch: object) -> None:
    script = _load_script_module(
        "check_docstring_coverage_script_missing_section",
        PROJECT_ROOT / "scripts" / "check_docstring_coverage.py",
    )
    temp_dir = PROJECT_ROOT / "tmp" / "docstring_structure_test"
    temp_dir.mkdir(parents=True, exist_ok=True)
    module_path = temp_dir / "focused_module.py"
    rel = module_path.relative_to(PROJECT_ROOT).as_posix()
    try:
        module_path.write_text(
            textwrap.dedent(
                '''\
                """临时重点模块。"""

                class PublicApi:
                    """缺少结构段落。"""
                '''
            ),
            encoding="utf-8",
        )

        monkeypatch.setitem(script.FOCUSED_SECTION_REQUIREMENTS, rel, {"PublicApi": ("Attributes:",)})
        violations = script._iter_structure_violations(module_path)

        assert violations == [f"{rel}: PublicApi missing section Attributes:"]
    finally:
        script.FOCUSED_SECTION_REQUIREMENTS.pop(rel, None)
        shutil.rmtree(temp_dir, ignore_errors=True)
