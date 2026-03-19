"""使用资源驱动评价流程。"""

from __future__ import annotations

from pathlib import Path

from examples._scenario_impls import _scenario_resource_driven_eval


def main(output_dir: Path | None = None) -> dict[str, object]:
    """运行对应示例入口。"""

    # docs:begin workflow_resource_driven_eval
    return _scenario_resource_driven_eval(output_dir=output_dir)
    # docs:end workflow_resource_driven_eval


if __name__ == "__main__":
    from examples._bootstrap import print_summary

    print_summary(main())
