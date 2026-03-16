"""构建样本并组织样本集。"""

from __future__ import annotations

from pathlib import Path

from examples._legacy_runner import run_legacy_example


def main(output_dir: Path | None = None) -> dict[str, object]:
    """运行样本与样本集组织场景。"""

    # docs:begin sample_set_minimal
    return run_legacy_example("examples/05_sample_sets/sample_set_ops.py", output_dir=output_dir)
    # docs:end sample_set_minimal


if __name__ == "__main__":
    from examples._bootstrap import print_summary

    print_summary(main())
