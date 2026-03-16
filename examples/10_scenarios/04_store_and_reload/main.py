"""存储并重新加载标准对象。"""

from __future__ import annotations

from pathlib import Path

from examples._legacy_runner import run_legacy_example


def main(output_dir: Path | None = None) -> dict[str, object]:
    """运行标准存储与回读场景。"""

    # docs:begin workflow_minimal_roundtrip
    return run_legacy_example("examples/90_workflows/workflow_minimal_roundtrip.py", output_dir=output_dir)
    # docs:end workflow_minimal_roundtrip


if __name__ == "__main__":
    from examples._bootstrap import print_summary

    print_summary(main())
