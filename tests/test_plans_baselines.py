"""重构计划基线文件存在性测试。"""

from __future__ import annotations

from pathlib import Path


def test_baseline_inventory_files_exist() -> None:
    root = Path(__file__).resolve().parents[1]
    required = [
        "docs/baselines/public_api_baseline.toml",
        "docs/plans/baselines/module_inventory.md",
        "docs/plans/baselines/dependency_inventory.md",
        "docs/plans/baselines/docs_examples_tests_inventory.md",
    ]
    for rel in required:
        assert (root / rel).exists(), rel
