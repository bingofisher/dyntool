"""示例和文档中的公开 API 基线测试。"""

from __future__ import annotations

import tomllib
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BASELINE_PATH = PROJECT_ROOT / "docs" / "baselines" / "public_api_baseline.toml"
EXAMPLES_MANIFEST_PATH = PROJECT_ROOT / "docs" / "examples_manifest.toml"


def _internal_example_paths() -> set[Path]:
    manifest = tomllib.loads(EXAMPLES_MANIFEST_PATH.read_text(encoding="utf-8"))
    internal: set[Path] = set()
    for entry in manifest.get("example", []):
        if entry.get("kind") != "internal":
            continue
        for key in ("script", "readme"):
            value = entry.get(key)
            if isinstance(value, str):
                internal.add((PROJECT_ROOT / value).resolve())
    return internal


def test_examples_and_docs_follow_public_api_baseline() -> None:
    baseline = tomllib.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    forbidden_tokens = baseline["forbidden_tokens"]
    scan_files = [
        *sorted((PROJECT_ROOT / "examples").rglob("*.py")),
        *sorted((PROJECT_ROOT / "docs").rglob("*.md")),
        PROJECT_ROOT / "README.md",
        PROJECT_ROOT / "ARCHITECTURE.md",
    ]
    excluded_prefixes = (
        PROJECT_ROOT / "docs" / "plans",
        PROJECT_ROOT / "docs" / "archive",
    )
    internal_example_paths = _internal_example_paths()
    for path in scan_files:
        if path == BASELINE_PATH:
            continue
        if path.resolve() in internal_example_paths:
            continue
        if any(str(path).startswith(str(prefix)) for prefix in excluded_prefixes):
            continue
        text = path.read_text(encoding="utf-8")
        for token in forbidden_tokens:
            assert token not in text, f"{path}: {token}"
