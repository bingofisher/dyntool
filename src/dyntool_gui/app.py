"""GUI 应用启动入口。"""

from __future__ import annotations

import sys

from .session import ProjectSession


def _build_startup_session(argv: list[str]) -> ProjectSession:
    """根据启动参数构造 GUI 初始会话。"""

    args = list(argv)
    if len(args) >= 2 and args[0] == "--demo":
        demo_key = args[1].strip().lower()
        if demo_key not in {"bridge", "generic"}:
            raise ValueError("`--demo` 仅支持 `bridge` 或 `generic`。")
        return ProjectSession.build_demo(demo_key)
    return ProjectSession.build_empty()


def main(argv: list[str] | None = None) -> int:
    """启动 GUI 骨架应用。"""

    launch_args = list(sys.argv[1:] if argv is None else argv)
    try:
        from PySide6.QtWidgets import QApplication
    except ModuleNotFoundError:
        print(
            "未安装 PySide6。请先执行 `uv sync --group gui` 或 `uv run --with PySide6 python -B -m dyntool_gui.app`。",
            file=sys.stderr,
        )
        return 1

    try:
        session = _build_startup_session(launch_args)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    from .main_window import MainWindow

    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow(session)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
