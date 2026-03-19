"""带日志运行完整任务。"""

from __future__ import annotations

from pathlib import Path

from examples._scenario_impls import _scenario_logged_run


def main(output_dir: Path | None = None) -> dict[str, object]:
    """运行对应示例入口。"""

    return _scenario_logged_run(output_dir=output_dir)


if __name__ == "__main__":
    from examples._bootstrap import print_summary

    print_summary(main())
