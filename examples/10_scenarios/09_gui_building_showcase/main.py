"""生成可计算、可保存的建筑室内振动展示项目。"""

from __future__ import annotations

import argparse
from pathlib import Path

from examples._bootstrap import print_summary
from dyntool_gui._building_showcase import build_building_showcase


def main(output_dir: Path | None = None) -> dict[str, object]:
    """生成项目和结果，不默认启动桌面窗口。

    Args:
        output_dir: 空目标目录，省略时创建独立展示目录。

    Returns:
        项目路径、输出目录和实际样本数量。
    """

    result = build_building_showcase(output_dir)
    return {"project_file": str(result.project_file), "output_dir": str(result.output_dir), "sample_count": 36}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="生成建筑室内振动与隔振效果展示项目（合成数据）。")
    parser.add_argument("--output-dir", type=Path, help="空输出目录；默认自动创建独立目录。")
    parser.add_argument("--open", action="store_true", dest="open_gui", help="生成后打开 GUI 并渲染默认对比图。")
    arguments = parser.parse_args()
    summary = main(arguments.output_dir)
    print_summary(summary)
    if arguments.open_gui:
        from dyntool_gui._showcase_launch import open_showcase

        raise SystemExit(open_showcase(Path(str(summary["project_file"]))))
