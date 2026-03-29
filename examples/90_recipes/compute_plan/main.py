"""演示 ComputePlan 的创建、序列化与复用。"""

from __future__ import annotations

from pathlib import Path

from examples._scenario_impls import _recipe_compute_plan


def main(output_dir: Path | None = None) -> dict[str, object]:
    """运行 ComputePlan recipe。"""

    return _recipe_compute_plan(output_dir=output_dir)


if __name__ == "__main__":
    from examples._bootstrap import print_summary

    print_summary(main())
