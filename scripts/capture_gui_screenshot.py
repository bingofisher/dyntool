"""生成 AdvDynTool GUI 内部截图。"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_SCALE_FACTOR", "1")
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")

from dyntool_gui.screenshot import GuiScreenshotOptions, capture_main_window_screenshot


def main() -> int:
    """命令行入口。"""

    parser = argparse.ArgumentParser(description="生成 AdvDynTool GUI 内部截图。")
    parser.add_argument("--output", type=Path, default=Path(".pytest_tmp/gui-screenshot.png"), help="输出 PNG 路径。")
    parser.add_argument("--demo", choices=("bridge", "generic"), default="bridge", help="演示会话。")
    parser.add_argument("--project", type=Path, default=None, help="可选 GUI 项目文件。")
    parser.add_argument(
        "--module",
        choices=("project", "overview", "import", "filter", "processing", "plotting"),
        default="project",
        help="截图页面。",
    )
    parser.add_argument("--width", type=int, default=1920, help="截图宽度。")
    parser.add_argument("--height", type=int, default=1080, help="截图高度。")
    args = parser.parse_args()

    output = capture_main_window_screenshot(
        GuiScreenshotOptions(
            output_path=args.output,
            demo_key=args.demo,
            project_path=args.project,
            module_key=args.module,
            width=args.width,
            height=args.height,
        )
    )
    print(f"GUI 截图已生成：{output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
