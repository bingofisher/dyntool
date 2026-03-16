"""最终清理相关的守卫测试。"""

from __future__ import annotations

import importlib.util
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _load_script_module(name: str, path: Path) -> object:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_check_layer_imports_detects_dynamic_imports(tmp_path: Path) -> None:
    script = _load_script_module(
        "check_layer_imports_script",
        PROJECT_ROOT / "scripts" / "check_layer_imports.py",
    )
    source_root = tmp_path / "src" / "dyntool" / "application"
    source_root.mkdir(parents=True)
    target = source_root / "demo.py"
    target.write_text(
        'import importlib\nruntime = importlib.import_module("dyntool.storage.types")\n',
        encoding="utf-8",
    )

    script.PROJECT_ROOT = tmp_path
    script.SOURCE_ROOT = tmp_path / "src" / "dyntool"

    imports = script._iter_imported_modules(target)

    assert "dyntool.storage.types" in {item[1] for item in imports}


def test_check_text_quality_covers_planning_files_and_control_files(tmp_path: Path) -> None:
    script = _load_script_module(
        "check_text_quality_script",
        PROJECT_ROOT / "scripts" / "check_text_quality.py",
    )
    (tmp_path / ".editorconfig").write_text(
        "root = true\n[*]\ncharset = utf-8\nend_of_line = lf\n",
        encoding="utf-8",
    )
    (tmp_path / ".gitattributes").write_text(
        "* text=auto eol=lf\n*.py text eol=lf\n*.md text eol=lf\n",
        encoding="utf-8",
    )
    (tmp_path / "README.md").write_text("# 标题\n中文说明\n", encoding="utf-8")
    (tmp_path / "ARCHITECTURE.md").write_text("# 架构\n中文说明\n", encoding="utf-8")
    (tmp_path / "findings.md").write_text("bad \u0081 mojibake\n", encoding="utf-8")

    script.PROJECT_ROOT = tmp_path
    script.TEXT_GLOBS = [
        ".editorconfig",
        ".gitattributes",
        "README.md",
        "ARCHITECTURE.md",
        "findings.md",
    ]
    script.STRICT_CHINESE_DOC_GLOBS = []

    assert script.main() == 1


def test_examples_use_public_entrypoints_only() -> None:
    example_files = [
        path for path in sorted((PROJECT_ROOT / "examples").rglob("*.py")) if "11_custom_extension" not in path.parts
    ]
    assert example_files
    forbidden_tokens = (
        "from dyntool.domain",
        "import dyntool.domain",
        "from dyntool.application",
        "import dyntool.application",
    )
    offenders: list[str] = []
    for path in example_files:
        text = path.read_text(encoding="utf-8")
        if any(token in text for token in forbidden_tokens):
            offenders.append(str(path.relative_to(PROJECT_ROOT)))

    assert not offenders, f"examples should use public entrypoints only: {offenders}"


def test_docs_and_examples_do_not_reference_removed_plot_backends() -> None:
    scan_roots = [
        PROJECT_ROOT / "README.md",
        PROJECT_ROOT / "ARCHITECTURE.md",
        PROJECT_ROOT / "mkdocs.yml",
        PROJECT_ROOT / "docs" / "examples_overview.md",
        PROJECT_ROOT / "examples",
    ]
    forbidden_tokens = (
        "plotly",
        "hvplot",
        "render_interactive",
        "plot_interactive",
        "preview_interactive",
    )
    offenders: list[str] = []
    for root in scan_roots:
        paths = [root] if root.is_file() else sorted(root.rglob("*.md")) + sorted(root.rglob("*.py"))
        for path in paths:
            text = path.read_text(encoding="utf-8")
            if any(token in text for token in forbidden_tokens):
                offenders.append(str(path.relative_to(PROJECT_ROOT)))

    assert not offenders, f"docs/examples reference removed plotting APIs: {offenders}"


def test_removed_parallel_directories_do_not_exist() -> None:
    for rel in (
        "src/dyntool/persistence",
        "src/dyntool/samples",
        "src/dyntool/utils",
    ):
        assert not (PROJECT_ROOT / rel).exists(), f"{rel} should be removed"


def test_removed_plotting_compat_files_do_not_exist() -> None:
    for rel in (
        "src/dyntool/plotting/adapters.py",
        "src/dyntool/plotting/data.py",
    ):
        assert not (PROJECT_ROOT / rel).exists(), f"{rel} should be removed"


def test_removed_module_specific_presets_do_not_exist_under_config() -> None:
    for rel in (
        "src/dyntool/config/presets/logging_simple.json",
        "src/dyntool/config/presets/logging_standard.json",
        "src/dyntool/config/presets/plotting.json",
    ):
        assert not (PROJECT_ROOT / rel).exists(), f"{rel} should be removed"


def test_empty_config_presets_directory_is_removed() -> None:
    assert not (PROJECT_ROOT / "src" / "dyntool" / "config" / "presets").exists()


def test_repository_control_files_exist() -> None:
    assert (PROJECT_ROOT / ".editorconfig").exists()
    assert (PROJECT_ROOT / ".gitattributes").exists()


def test_legacy_sphinx_scaffold_is_removed() -> None:
    assert not (PROJECT_ROOT / "docs" / "conf.py").exists()
    assert not (PROJECT_ROOT / "docs" / "api" / "public_api.rst").exists()
    assert not (PROJECT_ROOT / "docs" / "api" / "internal_api.rst").exists()


def test_mkdocs_configuration_exists() -> None:
    assert (PROJECT_ROOT / "mkdocs.yml").exists()


def test_repository_has_no_sphinx_build_artifacts() -> None:
    assert not (PROJECT_ROOT / "docs" / "_build").exists()


def test_unused_fixture_duplicates_are_removed() -> None:
    duplicate_candidates = sorted(path.name for path in (PROJECT_ROOT / "tests" / "input_data").glob("*副本*"))

    assert duplicate_candidates == []


def test_active_docs_do_not_reference_removed_storage_terms() -> None:
    scan_roots = [
        PROJECT_ROOT / "AGENTS.md",
        PROJECT_ROOT / "ARCHITECTURE.md",
        PROJECT_ROOT / "README.md",
        PROJECT_ROOT / "docs" / "examples_manifest.toml",
        PROJECT_ROOT / "docs" / "usage",
        PROJECT_ROOT / "docs" / "workflows",
        PROJECT_ROOT / "examples" / "90_recipes",
    ]
    forbidden_tokens = (
        "filter_by",
        "from_directory(",
        "`from_directory()`",
    )
    offenders: list[str] = []
    for root in scan_roots:
        paths = [root] if root.is_file() else sorted(root.rglob("*.md")) + sorted(root.rglob("*.toml"))
        for path in paths:
            text = path.read_text(encoding="utf-8")
            if any(token in text for token in forbidden_tokens):
                offenders.append(str(path.relative_to(PROJECT_ROOT)))

    assert not offenders, f"active docs still reference removed storage terms: {offenders}"


def test_active_rules_do_not_claim_interfaces_is_a_formal_layer() -> None:
    scan_roots = [
        PROJECT_ROOT / "AGENTS.md",
        PROJECT_ROOT / "ARCHITECTURE.md",
        PROJECT_ROOT / "docs" / "REFACTOR_BASELINE.md",
        PROJECT_ROOT / "docs" / "baselines" / "public_api_baseline.toml",
    ]
    bad_tokens = (
        "`interfaces`、`application`、`domain`、`compute`、`infrastructure`",
        "- `interfaces`",
        "interfaces = [",
        "interfaces -> application -> domain/compute",
    )
    offenders: list[str] = []
    for path in scan_roots:
        text = path.read_text(encoding="utf-8")
        if any(token in text for token in bad_tokens):
            offenders.append(str(path.relative_to(PROJECT_ROOT)))

    assert not offenders, f"active rules still claim interfaces as a formal layer: {offenders}"
