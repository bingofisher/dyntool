"""统计导出示例入口。"""

from __future__ import annotations

from pathlib import Path

from examples._scenario_impls import _recipe_statistics_export


def main(output_dir: Path | None = None) -> dict[str, object]:
    """运行统计导出示例。"""

    return _recipe_statistics_export(output_dir=output_dir)


if __name__ == "__main__":
    from examples._bootstrap import print_summary

    print_summary(main())
