"""任务区数据协调器。"""

from __future__ import annotations

from ..models import BottomPanelSnapshot, PanelDataBuilder
from ..session import ProjectSession


class TaskManager:
    """负责构造底部任务区数据。"""

    def __init__(self) -> None:
        self._builder = PanelDataBuilder()

    def build_bottom_rows(self, session: ProjectSession) -> dict[str, list[tuple[str, ...]]]:
        """根据当前会话构造底部行数据。"""

        return self._builder.build_bottom_rows(session)

    def build_snapshot(self, session: ProjectSession) -> BottomPanelSnapshot:
        """根据当前会话构造底部快照。"""

        return self._builder.build_bottom_snapshot(session)
