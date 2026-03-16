"""导出 payload 并交给 plotter。"""

from __future__ import annotations

from pathlib import Path

from examples._legacy_runner import run_legacy_example


def main(output_dir: Path | None = None) -> dict[str, object]:
    """运行 plotter-first recipe。"""

    return run_legacy_example("examples/08_visualization/plotting_demo.py", output_dir=output_dir)


if __name__ == "__main__":
    from examples._bootstrap import print_summary

    print_summary(main())
