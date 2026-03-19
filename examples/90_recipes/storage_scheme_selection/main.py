"""比较标准存储方案。"""

from __future__ import annotations

from pathlib import Path

from examples._scenario_impls import _recipe_storage_scheme_selection


def main(output_dir: Path | None = None) -> dict[str, object]:
    """运行对应示例入口。"""

    # docs:begin storage_scheme_compare
    return _recipe_storage_scheme_selection(output_dir=output_dir)
    # docs:end storage_scheme_compare


if __name__ == "__main__":
    from examples._bootstrap import print_summary

    print_summary(main())
