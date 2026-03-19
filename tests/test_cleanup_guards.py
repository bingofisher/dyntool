"""清理守卫与公开口径守卫测试。"""

from __future__ import annotations

import importlib.util
from pathlib import Path
import tomllib

PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXAMPLES_MANIFEST_PATH = PROJECT_ROOT / "docs" / "examples_manifest.toml"


def _load_script_module(name: str, path: Path) -> object:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _internal_example_scripts() -> set[Path]:
    manifest = tomllib.loads(EXAMPLES_MANIFEST_PATH.read_text(encoding="utf-8"))
    internal: set[Path] = set()
    for entry in manifest.get("example", []):
        if entry.get("kind") != "internal":
            continue
        script = entry.get("script")
        if isinstance(script, str):
            internal.add((PROJECT_ROOT / script).resolve())
    return internal


def test_pytest_imports_current_worktree_source() -> None:
    import dyntool

    package_file = Path(dyntool.__file__).resolve()
    expected = (PROJECT_ROOT / "src" / "dyntool").resolve()
    assert expected in package_file.parents


def test_check_layer_imports_detects_importlib_dynamic_imports(tmp_path: Path) -> None:
    script = _load_script_module("check_layer_imports_script", PROJECT_ROOT / "scripts" / "check_layer_imports.py")
    source_root = tmp_path / "src" / "dyntool" / "application"
    source_root.mkdir(parents=True)
    target = source_root / "demo.py"
    target.write_text(
        'import importlib\nruntime = importlib.import_module("dyntool.infrastructure.persistence")\n',
        encoding="utf-8",
    )

    script.PROJECT_ROOT = tmp_path
    script.SOURCE_ROOT = tmp_path / "src" / "dyntool"

    imports = script._iter_imported_modules(target)
    assert "dyntool.infrastructure.persistence" in {item[1] for item in imports}


def test_check_layer_imports_detects_builtin_dynamic_imports(tmp_path: Path) -> None:
    script = _load_script_module(
        "check_layer_imports_builtin_script", PROJECT_ROOT / "scripts" / "check_layer_imports.py"
    )
    source_root = tmp_path / "src" / "dyntool" / "domain"
    source_root.mkdir(parents=True)
    target = source_root / "demo.py"
    target.write_text(
        'error_type = __import__("dyntool.infrastructure.persistence", fromlist=["RecoverableIOError"])\n',
        encoding="utf-8",
    )

    script.PROJECT_ROOT = tmp_path
    script.SOURCE_ROOT = tmp_path / "src" / "dyntool"

    imports = script._iter_imported_modules(target)
    assert "dyntool.infrastructure.persistence" in {item[1] for item in imports}


def test_check_text_quality_covers_planning_files_and_detects_mojibake(tmp_path: Path) -> None:
    script = _load_script_module("check_text_quality_script", PROJECT_ROOT / "scripts" / "check_text_quality.py")
    (tmp_path / ".editorconfig").write_text("root = true\n[*]\ncharset = utf-8\nend_of_line = lf\n", encoding="utf-8")
    (tmp_path / ".gitattributes").write_text(
        "* text=auto eol=lf\n*.py text eol=lf\n*.md text eol=lf\n",
        encoding="utf-8",
    )
    (tmp_path / "README.md").write_text("# 鏍囬\n中文说明\n", encoding="utf-8")
    (tmp_path / "ARCHITECTURE.md").write_text("# 鏋舵瀯\n中文说明\n", encoding="utf-8")
    (tmp_path / "task_plan.md").write_text("闂傚爼鍋呴崥鍥╃崐\n", encoding="utf-8")

    script.PROJECT_ROOT = tmp_path
    script.TEXT_GLOBS = [".editorconfig", ".gitattributes", "README.md", "ARCHITECTURE.md", "task_plan.md"]
    script.STRICT_CHINESE_DOC_GLOBS = []

    assert script.main() == 1


def test_examples_use_public_entrypoints_only() -> None:
    example_files = sorted((PROJECT_ROOT / "examples").rglob("*.py"))
    assert example_files
    forbidden_tokens = (
        "from dyntool.domain",
        "import dyntool.domain",
        "from dyntool.application",
        "import dyntool.application",
    )
    offenders: list[str] = []
    internal_scripts = _internal_example_scripts()
    for path in example_files:
        if path.resolve() in internal_scripts:
            continue
        text = path.read_text(encoding="utf-8")
        if any(token in text for token in forbidden_tokens):
            offenders.append(path.relative_to(PROJECT_ROOT).as_posix())

    assert not offenders, f"正式示例必须只使用正式公开入口: {offenders}"


def test_docs_and_examples_do_not_reference_removed_plot_backends() -> None:
    scan_roots = [
        PROJECT_ROOT / "README.md",
        PROJECT_ROOT / "ARCHITECTURE.md",
        PROJECT_ROOT / "mkdocs.yml",
        PROJECT_ROOT / "docs" / "api",
        PROJECT_ROOT / "docs" / "developer",
        PROJECT_ROOT / "docs" / "usage",
        PROJECT_ROOT / "docs" / "workflows",
        PROJECT_ROOT / "docs" / "examples_overview.md",
        PROJECT_ROOT / "examples",
        PROJECT_ROOT / "pyproject.toml",
    ]
    forbidden_tokens = (
        "plotly",
        "hvplot",
        "holoviews",
        "render_interactive",
        "plot_interactive",
        "preview_interactive",
    )
    offenders: list[str] = []
    for root in scan_roots:
        paths = (
            [root]
            if root.is_file()
            else sorted(root.rglob("*.md")) + sorted(root.rglob("*.py")) + sorted(root.rglob("*.toml"))
        )
        for path in paths:
            text = path.read_text(encoding="utf-8")
            if any(token in text for token in forbidden_tokens):
                offenders.append(path.relative_to(PROJECT_ROOT).as_posix())

    assert not offenders, f"文档或配置仍引用已删除的绘图链路: {offenders}"


def test_formal_docs_do_not_reference_internal_import_paths() -> None:
    scan_roots = [
        PROJECT_ROOT / "README.md",
        PROJECT_ROOT / "ARCHITECTURE.md",
        PROJECT_ROOT / "docs",
    ]
    forbidden_tokens = (
        "from dyntool.domain",
        "import dyntool.domain",
        "from dyntool.application",
        "import dyntool.application",
    )
    offenders: list[str] = []
    for root in scan_roots:
        paths = [root] if root.is_file() else sorted(root.rglob("*.md"))
        for path in paths:
            text = path.read_text(encoding="utf-8")
            if any(token in text for token in forbidden_tokens):
                offenders.append(path.relative_to(PROJECT_ROOT).as_posix())

    assert not offenders, f"正式文档仍依赖内部导入路径: {offenders}"


def test_custom_extension_is_not_part_of_formal_examples() -> None:
    scan_files = [
        PROJECT_ROOT / "docs" / "examples_overview.md",
        PROJECT_ROOT / "examples" / "README.md",
        PROJECT_ROOT / "tests" / "test_examples_systems.py",
    ]
    offenders: list[str] = []
    for path in scan_files:
        text = path.read_text(encoding="utf-8")
        if "08_custom_extension" in text or "test_scenario_custom_extension" in text:
            offenders.append(path.relative_to(PROJECT_ROOT).as_posix())

    assert not offenders, f"custom_extension 不应继续出现在正式示例口径: {offenders}"


def test_custom_extension_manifest_entry_is_internal_only() -> None:
    manifest_path = PROJECT_ROOT / "docs" / "examples_manifest.toml"
    text = manifest_path.read_text(encoding="utf-8")
    assert 'id = "custom_extension"' in text
    block_start = text.index('id = "custom_extension"')
    block_end = text.find("[[example]]", block_start + 1)
    block = text[block_start:block_end] if block_end != -1 else text[block_start:]
    assert 'kind = "internal"' in block


def test_repository_has_no_mkdocs_build_artifacts() -> None:
    assert not (PROJECT_ROOT / "docs" / "_build").exists()
