"""GUI 应用启动入口。"""

from __future__ import annotations

import sys

from .session import ProjectSession


def main(argv: list[str] | None = None) -> int:
    """启动 GUI 骨架应用。"""

    del argv
    try:
        from PySide6.QtWidgets import QApplication
    except ModuleNotFoundError:
        print(
            "未安装 PySide6。请先执行 `uv sync --group gui` 或 `uv run --with PySide6 python -B -m dyntool_gui.app`。",
            file=sys.stderr,
        )
        return 1

    from .main_window import MainWindow

    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow(ProjectSession.build_demo())
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
