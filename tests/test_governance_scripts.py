"""仓库治理门禁脚本回归测试。"""

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


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _canonical_quality_gates() -> tuple[str, ...]:
    return (
        "uv run python -B scripts/check_codex_assets.py",
        "uv run ruff check --no-cache src/dyntool tests examples",
        "uv run ruff format --check src/dyntool tests examples",
        "uv run python -B scripts/check_layer_imports.py",
        "uv run python -B scripts/check_text_quality.py",
        "uv run python -B scripts/check_docstring_coverage.py",
        "uv run python -B scripts/check_public_api_baseline.py",
        "uv run python -B scripts/check_resource_consistency.py",
        "uv run python -B scripts/check_mkdocs_site.py",
        "uv run python -B scripts/check_repository_governance.py",
        "uv run python -B scripts/check_helper_structure.py",
        "$env:PYTHONDONTWRITEBYTECODE='1'; uv run python -B -m mkdocs build --strict --site-dir .pytest_tmp/mkdocs-site",
        "uv run pyright src/dyntool tests/typing_public_api.py",
        "$env:PYTHONDONTWRITEBYTECODE='1'; uv run python -B -m pytest -q --basetemp .pytest_tmp/pytest -p no:cacheprovider",
    )


def _seed_governance_docs(root: Path) -> None:
    commands = "\n".join(f"- `{command}`" for command in _canonical_quality_gates())
    _write_text(
        root / "AGENTS.md",
        "\n".join(
            (
                "# AdvDynTool Codex Rules",
                "",
                "## 9) 质量门禁",
                commands,
                "",
                "## 13) 内部聚合与 helper 规则",
                "- 禁止在单文件顶层平铺成组私有 helper。",
                "- 推荐用私有 runtime / parser / adapter 对象收敛内部实现。",
                "",
                "## 14) plotting 配置口径",
                "- 正式 TOML schema 只能使用当前 `axis.x` / `axis.y` / `grid.x.major` 写法。",
                "- 运行时对象字段名只在 Python API 说明中使用。",
                "- 项目级 profile / variant patch 不得伪装成 plotting 正式 schema。",
            )
        )
        + "\n",
    )
    _write_text(root / "README.md", f"# README\n\n{commands}\n")
    _write_text(root / "ARCHITECTURE.md", "# ARCHITECTURE\n\n- PlotTheme.axis_config 是运行时对象字段。\n")
    _write_text(root / "docs" / "developer" / "release_checklist.md", f"# release\n\n{commands}\n")
    _write_text(
        root / "docs" / "developer" / "doc_conventions.md",
        "\n".join(
            (
                "# conventions",
                "",
                "- `uv run python -B scripts/check_text_quality.py`",
                "- `uv run python -B scripts/check_repository_governance.py`",
                "- `uv run python -B scripts/check_helper_structure.py`",
            )
        )
        + "\n",
    )
    _write_text(root / "docs" / "api" / "public_api.md", "# public\n\n- `PlotTheme.axis_config` 是运行时对象字段。\n")
    _write_text(
        root / "docs" / "usage" / "06_plotting_config_reference.md", "# usage\n\n[axis.x]\nkind = 'continuous'\n"
    )
    _write_text(root / "docs" / "developer" / "migration_1_2_0.md", "# migration\n\n[axis_config.x]\n")
    _write_text(root / "examples" / "demo" / "README.md", "# example\n\n[grid.x.major]\nenabled = true\n")
    _write_text(
        root / "src" / "dyntool" / "plotting" / "assets" / "plot_theme_report.toml", "[axis.x]\nkind='continuous'\n"
    )


def test_check_repository_governance_passes_for_canonical_docs(tmp_path: Path) -> None:
    script = _load_script_module(
        "check_repository_governance_script",
        PROJECT_ROOT / "scripts" / "check_repository_governance.py",
    )
    _seed_governance_docs(tmp_path)

    assert script.main(project_root=tmp_path) == 0


def test_check_repository_governance_detects_non_canonical_quality_commands(tmp_path: Path) -> None:
    script = _load_script_module(
        "check_repository_governance_bad_commands_script",
        PROJECT_ROOT / "scripts" / "check_repository_governance.py",
    )
    _seed_governance_docs(tmp_path)
    _write_text(
        tmp_path / "docs" / "developer" / "doc_conventions.md",
        "# conventions\n\n- `python -B scripts/check_text_quality.py`\n",
    )

    assert script.main(project_root=tmp_path) == 1


def test_check_repository_governance_detects_removed_plotting_schema_tokens(tmp_path: Path) -> None:
    script = _load_script_module(
        "check_repository_governance_legacy_schema_script",
        PROJECT_ROOT / "scripts" / "check_repository_governance.py",
    )
    _seed_governance_docs(tmp_path)
    _write_text(
        tmp_path / "docs" / "usage" / "06_plotting_config_reference.md",
        "# usage\n\n[axis_config.x]\nkind = 'continuous'\n",
    )

    assert script.main(project_root=tmp_path) == 1


def test_check_repository_governance_allows_legacy_plotting_schema_in_migration_docs(tmp_path: Path) -> None:
    script = _load_script_module(
        "check_repository_governance_migration_exempt_script",
        PROJECT_ROOT / "scripts" / "check_repository_governance.py",
    )
    _seed_governance_docs(tmp_path)
    _write_text(
        tmp_path / "docs" / "developer" / "migration_1_2_0.md",
        "# migration\n\n[axis_config.x]\nspine_top = false\n",
    )

    assert script.main(project_root=tmp_path) == 0


def test_check_helper_structure_detects_scattered_private_helper_cluster(tmp_path: Path) -> None:
    script = _load_script_module(
        "check_helper_structure_script",
        PROJECT_ROOT / "scripts" / "check_helper_structure.py",
    )
    target = tmp_path / "src" / "dyntool" / "plotting" / "_demo.py"
    _write_text(
        target,
        "\n".join(
            (
                "def _normalize_locale(payload):",
                "    return payload or {}",
                "",
                "def _normalize_figure(payload):",
                "    return payload or {}",
                "",
                "def _normalize_axes(payload):",
                "    return payload or {}",
                "",
                "def _normalize_grid(payload):",
                "    return payload or {}",
                "",
            )
        )
        + "\n",
    )

    assert script.main(project_root=tmp_path) == 1


def test_check_helper_structure_allows_parser_style_aggregation(tmp_path: Path) -> None:
    script = _load_script_module(
        "check_helper_structure_parser_script",
        PROJECT_ROOT / "scripts" / "check_helper_structure.py",
    )
    target = tmp_path / "src" / "dyntool" / "plotting" / "_demo.py"
    _write_text(
        target,
        "\n".join(
            (
                "class _ThemeSchemaParser:",
                "    def normalize_locale(self, payload):",
                "        return payload or {}",
                "",
                "    def normalize_figure(self, payload):",
                "        return payload or {}",
                "",
                "PARSER = _ThemeSchemaParser()",
                "",
                "def normalize_locale(payload):",
                "    return PARSER.normalize_locale(payload)",
                "",
                "def normalize_figure(payload):",
                "    return PARSER.normalize_figure(payload)",
                "",
            )
        )
        + "\n",
    )

    assert script.main(project_root=tmp_path) == 0
