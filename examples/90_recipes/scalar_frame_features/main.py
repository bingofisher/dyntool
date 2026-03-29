"""演示 scalar_frame 的特征聚合与严格模式。"""

from __future__ import annotations

from pathlib import Path

from examples._scenario_impls import _recipe_scalar_frame_features


def main(output_dir: Path | None = None) -> dict[str, object]:
    """运行 scalar_frame features recipe。"""

    return _recipe_scalar_frame_features(output_dir=output_dir)


if __name__ == "__main__":
    from examples._bootstrap import print_summary

    print_summary(main())
