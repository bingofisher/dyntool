"""演示 series_frame 的索引对齐与缺失补齐。"""

from __future__ import annotations

from pathlib import Path

from examples._scenario_impls import _recipe_series_frame_alignment


def main(output_dir: Path | None = None) -> dict[str, object]:
    """运行 series_frame alignment recipe。"""

    return _recipe_series_frame_alignment(output_dir=output_dir)


if __name__ == "__main__":
    from examples._bootstrap import print_summary

    print_summary(main())
