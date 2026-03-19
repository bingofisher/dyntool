"""绘图并导出结果。"""

from __future__ import annotations

from pathlib import Path

from examples._scenario_impls import _scenario_plot_and_export


def main(output_dir: Path | None = None) -> dict[str, object]:
    """运行对应示例入口。"""

    # docs:begin plotting_minimal
    return _scenario_plot_and_export(output_dir=output_dir)
    # docs:end plotting_minimal


if __name__ == "__main__":
    from examples._bootstrap import print_summary

    print_summary(main())
