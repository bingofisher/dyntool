"""执行 AdvDynTool GUI 主流程巡检。"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_SCALE_FACTOR", "1")
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")

from dyntool_gui.audit import GuiAuditOptions, run_gui_audit

DEFAULT_DATA_SOURCE = Path(r"E:\21_AcademicProjects\P-R1-3_地铁振动分析\C_数据分析\data_v2")


def main() -> int:
    """命令行入口。"""

    parser = argparse.ArgumentParser(description="执行 AdvDynTool GUI 主流程按钮、截图和窗口交互巡检。")
    parser.add_argument("--output-dir", type=Path, default=Path(".pytest_tmp/gui-audit/round-001"))
    parser.add_argument("--data-source", type=Path, default=DEFAULT_DATA_SOURCE)
    parser.add_argument("--project-dir", type=Path, default=None)
    parser.add_argument("--width", type=int, default=1920)
    parser.add_argument("--height", type=int, default=1080)
    parser.add_argument("--run-heavy-actions", action="store_true", help="执行真实绑定、分析、绘图和导出链路。")
    parser.add_argument("--include-deep-check", action="store_true", help="执行深度单位检查。")
    parser.add_argument("--timeout-seconds", type=float, default=120.0)
    parser.add_argument("--no-real-data", action="store_true", help="只执行结构和视觉巡检，不读取真实 data_v2。")
    args = parser.parse_args()

    data_source = None if args.no_real_data else args.data_source
    if data_source is not None and not data_source.exists():
        raise FileNotFoundError(f"真实数据目录不存在：{data_source}")

    report = run_gui_audit(
        GuiAuditOptions(
            output_dir=args.output_dir,
            data_source=data_source,
            project_dir=args.project_dir,
            width=args.width,
            height=args.height,
            run_heavy_actions=args.run_heavy_actions,
            include_deep_check=args.include_deep_check,
            timeout_seconds=args.timeout_seconds,
        )
    )
    print(f"GUI 巡检完成：{report.output_dir}")
    print(f"动作：{len(report.actions)}，截图：{len(report.screenshots)}，问题：{len(report.issues)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
