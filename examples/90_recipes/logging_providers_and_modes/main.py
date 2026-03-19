"""比较日志 provider 与模式。"""

from __future__ import annotations

from pathlib import Path

from examples._scenario_impls import _recipe_logging_providers_and_modes


def main(output_dir: Path | None = None) -> dict[str, object]:
    """运行对应示例入口。"""

    # docs:begin logging_mode_compare
    return _recipe_logging_providers_and_modes(output_dir=output_dir)
    # docs:end logging_mode_compare


if __name__ == "__main__":
    from examples._bootstrap import print_summary

    print_summary(main())
