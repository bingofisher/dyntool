"""切换日志 provider 与输出模式。"""

from __future__ import annotations

from pathlib import Path

from examples._legacy_runner import run_legacy_example


def main(output_dir: Path | None = None) -> dict[str, object]:
    """运行日志 provider 与模式 recipe。"""

    # docs:begin logging_mode_compare
    return run_legacy_example("examples/09_logging_config/logging_modes.py", output_dir=output_dir)
    # docs:end logging_mode_compare


if __name__ == "__main__":
    from examples._bootstrap import print_summary

    print_summary(main())
