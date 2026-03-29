"""演示 ComputeFlow 的分支、恢复与提交。"""

from __future__ import annotations

from pathlib import Path

from examples._scenario_impls import _recipe_compute_flow


def main(output_dir: Path | None = None) -> dict[str, object]:
    """运行 ComputeFlow recipe。"""

    return _recipe_compute_flow(output_dir=output_dir)


if __name__ == "__main__":
    from examples._bootstrap import print_summary

    print_summary(main())
