"""利用内置资源完成评价。"""

from __future__ import annotations

from pathlib import Path

from examples._legacy_runner import run_legacy_example


def main(output_dir: Path | None = None) -> dict[str, object]:
    """运行资源驱动评价场景。"""

    # docs:begin workflow_resource_driven_eval
    return run_legacy_example("examples/90_workflows/workflow_resource_driven_eval.py", output_dir=output_dir)
    # docs:end workflow_resource_driven_eval


if __name__ == "__main__":
    from examples._bootstrap import print_summary

    print_summary(main())
