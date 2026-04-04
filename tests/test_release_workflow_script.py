"""本地发布收口脚本回归测试。"""

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


def test_finish_local_release_bumps_patch_version() -> None:
    script = _load_script_module(
        "finish_local_release_script",
        PROJECT_ROOT / "scripts" / "finish_local_release.py",
    )
    assert script._bump_patch_version("1.1.1") == "1.1.2"


def test_finish_local_release_classifies_paths_into_fixed_groups() -> None:
    script = _load_script_module(
        "finish_local_release_group_script",
        PROJECT_ROOT / "scripts" / "finish_local_release.py",
    )
    grouped, uncovered = script.classify_paths(
        {
            "src/dyntool/storage/runtime.py",
            "src/dyntool/infrastructure/sample_storage_sqlite_h5.py",
            "tests/test_samples.py",
            "scripts/check_public_api_baseline.py",
            "README.md",
            "docs/developer/development_workflow.md",
            "scripts/fix_text_hygiene.py",
            "task_plan.md",
        }
    )

    assert uncovered == []
    assert "src/dyntool/storage/runtime.py" in grouped["core"]
    assert "src/dyntool/infrastructure/sample_storage_sqlite_h5.py" in grouped["core"]
    assert "tests/test_samples.py" in grouped["tests"]
    assert "scripts/check_public_api_baseline.py" in grouped["tests"]
    assert "README.md" in grouped["docs"]
    assert "docs/developer/development_workflow.md" in grouped["docs"]
    assert "scripts/fix_text_hygiene.py" in grouped["chore"]


def test_finish_local_release_updates_version_files(tmp_path: Path) -> None:
    script = _load_script_module(
        "finish_local_release_version_script",
        PROJECT_ROOT / "scripts" / "finish_local_release.py",
    )
    version_file = tmp_path / "_version.py"
    readme_file = tmp_path / "README.md"
    docs_index_file = tmp_path / "index.md"
    version_file.write_text('__version__ = "1.1.1"\n', encoding="utf-8")
    readme_file.write_text("当前发布版本：`v1.1.1`\n", encoding="utf-8")
    docs_index_file.write_text("当前发布版本：`v1.1.1`\n", encoding="utf-8")

    script.VERSION_FILE = version_file
    script.README_FILE = readme_file
    script.DOCS_INDEX_FILE = docs_index_file
    script._update_version_strings("1.1.1", "1.1.2")

    assert '__version__ = "1.1.2"' in version_file.read_text(encoding="utf-8")
    assert "当前发布版本：`v1.1.2`" in readme_file.read_text(encoding="utf-8")
    assert "当前发布版本：`v1.1.2`" in docs_index_file.read_text(encoding="utf-8")


def test_finish_local_release_builds_changelog_entry() -> None:
    script = _load_script_module(
        "finish_local_release_changelog_script",
        PROJECT_ROOT / "scripts" / "finish_local_release.py",
    )
    entry = script._build_changelog_entry("1.1.2")
    assert "## v1.1.2 -" in entry
    assert "当前阶段收口" in entry


def test_finish_local_release_cleans_generated_artifacts(tmp_path: Path) -> None:
    script = _load_script_module(
        "finish_local_release_cleanup_script",
        PROJECT_ROOT / "scripts" / "finish_local_release.py",
    )
    script.PROJECT_ROOT = tmp_path
    script.GENERATED_ARTIFACT_DIRS = (
        tmp_path / ".ruff_cache",
        tmp_path / ".pytest_cache",
        tmp_path / "site",
        tmp_path / "docs" / "_build",
    )

    for path in script.GENERATED_ARTIFACT_DIRS:
        path.mkdir(parents=True)
        (path / "marker.txt").write_text("x", encoding="utf-8")
    pycache_dir = tmp_path / "src" / "__pycache__"
    pycache_dir.mkdir(parents=True)
    (pycache_dir / "cache.pyc").write_bytes(b"pyc")

    script._clean_generated_artifacts()

    assert all(not path.exists() for path in script.GENERATED_ARTIFACT_DIRS)
    assert not pycache_dir.exists()
