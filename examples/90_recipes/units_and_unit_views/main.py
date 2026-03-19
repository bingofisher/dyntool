"""查看单位并执行单位往返。"""

from __future__ import annotations

from pathlib import Path

from examples._scenario_impls import _recipe_units_and_unit_views


def main(output_dir: Path | None = None) -> dict[str, object]:
    """运行对应示例入口。"""

    # docs:begin csv_unit_roundtrip
    return _recipe_units_and_unit_views(output_dir=output_dir)
    # docs:end csv_unit_roundtrip


if __name__ == "__main__":
    from examples._bootstrap import print_summary

    print_summary(main())
