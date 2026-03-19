"""筛选样本集并演示并行 I/O。"""

from __future__ import annotations

from pathlib import Path

from examples._scenario_impls import _recipe_sample_set_filter_parallel_io


def main(output_dir: Path | None = None) -> dict[str, object]:
    """运行对应示例入口。"""

    # docs:begin workflow_sample_set_batch
    return _recipe_sample_set_filter_parallel_io(output_dir=output_dir)
    # docs:end workflow_sample_set_batch


if __name__ == "__main__":
    from examples._bootstrap import print_summary

    print_summary(main())
