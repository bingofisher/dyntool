"""Web 工作台会话状态。"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from threading import RLock
from typing import Any
from uuid import uuid4


NAVIGATION = ["总览", "导入与筛选", "数据处理", "图形绘制"]
DEFAULT_TEST_DATA_PATHS = (Path(r"E:\21_AcademicProjects\P-R1-3_地铁振动分析\C_数据分析\data_v2"),)


@dataclass(slots=True)
class WebTask:
    """Web 任务记录。"""

    id: str
    title: str
    status: str
    progress: str
    progress_percent: int
    stage: str
    cancelable: bool
    detail: str
    timestamp: str


@dataclass(slots=True)
class WebIssue:
    """Web 问题记录。"""

    status: str
    title: str
    detail: str
    timestamp: str


@dataclass(slots=True)
class WebSessionState:
    """Web 工作台内存会话。"""

    project_name: str = "AdvDynTool Web 项目"
    workdir: Path = field(default_factory=lambda: Path.cwd())
    export_dir: Path = field(default_factory=lambda: Path.cwd() / "exports")
    primary_runtime: object | None = None
    primary_summary: dict[str, Any] = field(default_factory=dict)
    capability: dict[str, Any] = field(default_factory=lambda: {"data_slots": [], "eval_results": []})
    recent_paths: list[str] = field(default_factory=list)
    favorite_paths: list[str] = field(default_factory=lambda: list(_default_test_data_paths()))
    current_scope: dict[str, str] = field(default_factory=lambda: {"scope_kind": "all_samples", "target": ""})
    tasks: list[WebTask] = field(default_factory=list)
    issues: list[WebIssue] = field(default_factory=list)
    last_preview: dict[str, Any] = field(default_factory=lambda: {"columns": [], "rows": []})
    last_plot_image: str = ""
    last_plot_format: str = ""
    active_theme_path: Path | None = None
    import_preview_cache: dict[str, Any] = field(default_factory=dict)
    saved_subsets: list[dict[str, Any]] = field(default_factory=list)
    primary_version: int = 0
    scope_version: int = 0
    theme_version: int = 0
    last_preview_versions: dict[str, int] = field(default_factory=dict)
    last_plot_versions: dict[str, int] = field(default_factory=dict)
    _lock: RLock = field(default_factory=RLock, repr=False)

    def snapshot(self) -> dict[str, Any]:
        """返回前端会话快照。"""

        with self._lock:
            return {
                "project": {
                    "name": self.project_name,
                    "workdir": str(self.workdir),
                    "export_dir": str(self.export_dir),
                },
                "navigation": NAVIGATION,
                "primary": self.primary_summary,
                "capability": self.capability,
                "current_scope": self.current_scope,
                "recent_paths": self.recent_paths,
                "favorite_paths": self.favorite_paths,
                "saved_subsets": list(self.saved_subsets),
                "versions": {
                    "primary": self.primary_version,
                    "scope": self.scope_version,
                    "theme": self.theme_version,
                },
                "last_preview": {
                    **self.last_preview,
                    "stale": self._is_stale(self.last_preview_versions, include_theme=False),
                    "versions": dict(self.last_preview_versions),
                },
                "last_plot": {
                    "image_format": self.last_plot_format,
                    "image": self.last_plot_image,
                    "stale": self._is_stale(self.last_plot_versions, include_theme=True),
                    "versions": dict(self.last_plot_versions),
                },
                "debug": {
                    "default_data_path": self.favorite_paths[0] if self.favorite_paths else "",
                },
            }

    def task_snapshot(self) -> dict[str, Any]:
        """返回任务面板快照。"""

        with self._lock:
            return {
                "tasks": [asdict(task) for task in self.tasks],
                "issues": [asdict(issue) for issue in self.issues],
            }

    def set_workdir(self, path: Path) -> None:
        """设置项目目录。"""

        with self._lock:
            self.workdir = path.resolve()
            self.export_dir = self.workdir / "exports"
            self.project_name = self.workdir.name or "AdvDynTool Web 项目"
            self.remember_path(self.workdir)
        self.add_task("设置项目目录", "已完成", "1 / 1", f"当前项目目录：{self.workdir}")

    def remember_path(self, path: Path) -> None:
        """记录最近路径。"""

        text = str(path.resolve())
        with self._lock:
            self.recent_paths = [text, *(item for item in self.recent_paths if item != text)][:12]

    def add_task(
        self,
        title: str,
        status: str,
        progress: str,
        detail: str,
        *,
        progress_percent: int = 100,
        stage: str = "完成",
        cancelable: bool = False,
    ) -> WebTask:
        """追加任务记录。"""

        with self._lock:
            task = WebTask(
                id=uuid4().hex,
                title=title,
                status=status,
                progress=progress,
                progress_percent=max(0, min(progress_percent, 100)),
                stage=stage,
                cancelable=cancelable,
                detail=detail,
                timestamp=_now_text(),
            )
            self.tasks.insert(0, task)
            self.tasks = self.tasks[:100]
            return task

    def start_task(self, title: str, detail: str, *, cancelable: bool = False) -> WebTask:
        """追加运行中任务记录。"""

        return self.add_task(
            title,
            "进行中",
            "0 / 1",
            detail,
            progress_percent=0,
            stage="运行中",
            cancelable=cancelable,
        )

    def add_issue(self, status: str, title: str, detail: str) -> None:
        """追加问题记录。"""

        with self._lock:
            self.issues.insert(0, WebIssue(status, title, detail, _now_text()))
            self.issues = self.issues[:100]

    def mark_primary_changed(self) -> None:
        """标记主样本集已变化。"""

        with self._lock:
            self.primary_version += 1
            self.scope_version += 1
            self.current_scope = {"scope_kind": "all_samples", "target": ""}
            self.saved_subsets = []
            self.last_preview = {"columns": [], "rows": []}
            self.last_preview_versions = {}
            self.last_plot_image = ""
            self.last_plot_format = ""
            self.last_plot_versions = {}

    def set_current_scope(self, scope_kind: str, target: str) -> dict[str, str]:
        """设置当前范围并推进范围版本。"""

        with self._lock:
            self.current_scope = {"scope_kind": scope_kind, "target": target}
            self.scope_version += 1
            return dict(self.current_scope)

    def mark_theme_changed(self) -> None:
        """标记绘图主题已变化。"""

        with self._lock:
            self.theme_version += 1

    def store_preview(self, payload: dict[str, Any]) -> None:
        """保存结果预览并记录来源版本。"""

        with self._lock:
            self.last_preview = payload
            self.last_preview_versions = self._current_versions(include_theme=False)

    def store_plot(self, image: str, image_format: str) -> None:
        """保存图形预览并记录来源版本。"""

        with self._lock:
            self.last_plot_image = image
            self.last_plot_format = image_format
            self.last_plot_versions = self._current_versions(include_theme=True)

    def upsert_saved_subset(self, name: str, uids: list[str]) -> dict[str, Any]:
        """保存或替换内存子集。"""

        subset = {"name": name, "count": len(uids), "uids": uids, "timestamp": _now_text()}
        with self._lock:
            self.saved_subsets = [subset, *(item for item in self.saved_subsets if item.get("name") != name)][:50]
            return dict(subset)

    def saved_subset_uids(self, name: str) -> list[str]:
        """按名称返回已保存子集 UID。"""

        with self._lock:
            for subset in self.saved_subsets:
                if subset.get("name") == name:
                    return [str(uid) for uid in subset.get("uids", [])]
        return []

    def _current_versions(self, *, include_theme: bool) -> dict[str, int]:
        versions = {"primary": self.primary_version, "scope": self.scope_version}
        if include_theme:
            versions["theme"] = self.theme_version
        return versions

    def _is_stale(self, versions: dict[str, int], *, include_theme: bool) -> bool:
        if not versions:
            return False
        return versions != self._current_versions(include_theme=include_theme)


def _now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _default_test_data_paths() -> tuple[str, ...]:
    candidates: list[Path] = []
    env_path = os.environ.get("ADVDYNTOOL_WEB_DEFAULT_DATA_PATH", "").strip()
    if env_path:
        candidates.append(Path(env_path))
    candidates.extend(DEFAULT_TEST_DATA_PATHS)
    return tuple(str(path.expanduser().resolve()) for path in candidates if path.expanduser().exists())
