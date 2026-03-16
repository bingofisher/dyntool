"""筛选并并行读写样本集。"""

from __future__ import annotations

from pathlib import Path

from examples._legacy_runner import run_legacy_example


def main(output_dir: Path | None = None) -> dict[str, object]:
    """运行样本集筛选与并行 I/O recipe。"""

    # docs:begin workflow_sample_set_batch
    return run_legacy_example("examples/90_workflows/workflow_sample_set_batch.py", output_dir=output_dir)
    # docs:end workflow_sample_set_batch


if __name__ == "__main__":
    from examples._bootstrap import print_summary

    print_summary(main())
