"""对比不同元数据模式。"""

from __future__ import annotations

from pathlib import Path

from examples._scenario_impls import _recipe_metadata_patterns


def main(output_dir: Path | None = None) -> dict[str, object]:
    """运行对应示例入口。"""

    # docs:begin metadata_minimal
    return _recipe_metadata_patterns(output_dir=output_dir)
    # docs:end metadata_minimal


if __name__ == "__main__":
    from examples._bootstrap import print_summary

    print_summary(main())
