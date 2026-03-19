"""演示自定义扩展能力。"""

from __future__ import annotations

from pathlib import Path

from examples._scenario_impls import _scenario_custom_extension


def main(output_dir: Path | None = None) -> dict[str, object]:
    """运行对应示例入口。"""

    # docs:begin custom_extension_minimal
    return _scenario_custom_extension(output_dir=output_dir)
    # docs:end custom_extension_minimal


if __name__ == "__main__":
    from examples._bootstrap import print_summary

    print_summary(main())
