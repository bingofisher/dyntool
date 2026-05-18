"""维护脚本的行为回归测试。"""

from __future__ import annotations

import importlib.util
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BROKEN_TITLE = "\u93cd\u56ec\ue57d"
BROKEN_CHINESE_DOC = "\u6d93\ue15f\u6783\u7487\u5b58\u69d1"
UNKNOWN_MOJIBAKE = "\u95c2\u5099\u7901\u943f\u7248\u7901\u95ae\u4f7d\u6751\u89e6"
CURRENT_MOJIBAKE = "current 楠岃瘉澶辫触锛氭牱鏈暟涓嶄竴鑷淬€?"


def _load_script_module(name: str, path: Path) -> object:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_fix_text_hygiene_repairs_low_risk_text_issues(tmp_path: Path, capsys) -> None:
    script = _load_script_module("fix_text_hygiene_script", PROJECT_ROOT / "scripts" / "fix_text_hygiene.py")
    target = tmp_path / "README.md"
    target.write_bytes(bytes((0xEF, 0xBB, 0xBF)) + f"# {BROKEN_TITLE}\r\n{BROKEN_CHINESE_DOC}\r\n".encode("utf-8"))

    assert script.main(["--check"], project_root=tmp_path) == 1
    check_output = capsys.readouterr().out
    assert "summary" in check_output
    assert "manual_review" in check_output

    assert script.main(["--apply"], project_root=tmp_path) == 0
    apply_output = capsys.readouterr().out
    assert "changed/removed" in apply_output
    assert target.read_text(encoding="utf-8") == "# 标题\n中文说明\n"


def test_fix_text_hygiene_reports_unknown_mojibake_for_manual_review(tmp_path: Path, capsys) -> None:
    script = _load_script_module("fix_text_hygiene_unknown_script", PROJECT_ROOT / "scripts" / "fix_text_hygiene.py")
    target = tmp_path / "docs" / "index.md"
    target.parent.mkdir(parents=True)
    target.write_text(f"{UNKNOWN_MOJIBAKE}\n", encoding="utf-8")

    assert script.main(["--apply"], project_root=tmp_path) == 1
    output = capsys.readouterr().out
    assert "manual_review" in output
    assert UNKNOWN_MOJIBAKE in target.read_text(encoding="utf-8")


def test_check_text_quality_detects_current_mojibake_fragments(tmp_path: Path, capsys) -> None:
    script = _load_script_module(
        "check_text_quality_current_mojibake_script", PROJECT_ROOT / "scripts" / "check_text_quality.py"
    )
    target = tmp_path / "scripts" / "demo.py"
    target.parent.mkdir(parents=True)
    target.write_text(f'raise AssertionError("{CURRENT_MOJIBAKE}")\n', encoding="utf-8")

    script.PROJECT_ROOT = tmp_path
    script.TEXT_GLOBS = ["scripts/**/*.py"]
    script.STRICT_CHINESE_DOC_GLOBS = []

    assert script.main() == 1
    output = capsys.readouterr().out
    assert "contains suspicious mojibake fragment" in output


def test_clean_generated_artifacts_removes_only_allowed_paths(tmp_path: Path, capsys) -> None:
    script = _load_script_module(
        "clean_generated_artifacts_script",
        PROJECT_ROOT / "scripts" / "clean_generated_artifacts.py",
    )
    allowed_paths = [
        tmp_path / "site",
        tmp_path / "docs" / "_build",
        tmp_path / "package" / "__pycache__",
        tmp_path / ".pytest_cache",
        tmp_path / ".ruff_cache",
        tmp_path / "tmp",
        tmp_path / ".tmp_plot_verify",
    ]
    protected_paths = [
        tmp_path / ".venv",
        tmp_path / ".uv-cache",
        tmp_path / ".worktrees",
        tmp_path / ".git",
    ]

    for path in allowed_paths + protected_paths:
        path.mkdir(parents=True, exist_ok=True)
        (path / "sentinel.txt").write_text("keep", encoding="utf-8")

    assert script.main(["--check"], project_root=tmp_path) == 1
    check_output = capsys.readouterr().out
    assert "summary" in check_output

    assert script.main(["--apply"], project_root=tmp_path) == 0
    apply_output = capsys.readouterr().out
    assert "changed/removed" in apply_output

    for path in allowed_paths:
        assert not path.exists()
    for path in protected_paths:
        assert path.exists()
