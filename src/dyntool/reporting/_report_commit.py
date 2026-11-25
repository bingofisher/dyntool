"""Private / implementation detail：完整报告的暂存、发布与回滚。"""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
from tempfile import mkdtemp
from typing import Any
from uuid import uuid4

from ..infrastructure._storage_commit import _StorageConsistencyError, _WriteMarker


class _ReportCommit:
    """清单约束目录所有权，保留清单外文件并发布完整版本。"""

    def __init__(self, target: Path) -> None:
        self.target = target
        self.stage: Path | None = None
        self.managed: set[Path] = set()
        self.backup = target.with_name(f".dyntool-report-backup-{uuid4().hex}")
        self.marker = _WriteMarker(target.parent, f"发布报告 {target}")
        self.published = False

    def _paths(self, root: Path, manifest: dict[str, Any]) -> set[Path]:
        if not isinstance(manifest.get("tables"), list) or not isinstance(manifest.get("figures"), list):
            raise ValueError(f"报告清单无效：{root / 'manifest.json'}")
        try:
            names = ["manifest.json", "metadata_summary.json", manifest["report_workbook"]]
            names.extend(entry["path"] for entry in [*manifest["tables"], *manifest["figures"]])
        except (KeyError, TypeError) as error:
            raise ValueError(f"报告清单无效：{root / 'manifest.json'}") from error
        paths = set()
        for name in names:
            relative = Path(name)
            resolved = (root / relative).resolve()
            if relative.is_absolute() or not resolved.is_relative_to(root.resolve()) or resolved == root.resolve():
                raise ValueError(f"报告清单路径越界：{name}")
            paths.add(relative)
        return paths

    def __enter__(self) -> _ReportCommit:
        self.target.parent.mkdir(parents=True, exist_ok=True)
        _WriteMarker.check(self.target.parent)
        if self.target.exists() and any(self.target.iterdir()):
            manifest_path = self.target / "manifest.json"
            if not manifest_path.is_file():
                raise ValueError(f"非空目录缺少有效报告清单，拒绝覆盖：{self.target}")
            self.managed = self._paths(self.target, json.loads(manifest_path.read_text(encoding="utf-8")))
        self.stage = Path(mkdtemp(prefix=".dyntool-report-stage-", dir=self.target.parent))
        return self

    def publish(self) -> None:
        assert self.stage is not None
        new_paths = self._paths(self.stage, json.loads((self.stage / "manifest.json").read_text(encoding="utf-8")))
        if self.target.exists():
            for existing in self.target.rglob("*"):
                if existing.is_symlink():
                    raise ValueError(f"报告目录存在链接，无法确认写入归属：{existing}")
                relative = existing.relative_to(self.target)
                if existing.is_file() and relative not in self.managed:
                    if relative in new_paths or (self.stage / relative).exists():
                        raise ValueError(f"新报告与清单外用户文件冲突：{existing}")
                    destination = self.stage / relative
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(existing, destination)
        self.marker.start()
        moved = False
        try:
            if self.target.exists():
                os.replace(self.target, self.backup)
                moved = True
            os.replace(self.stage, self.target)
            self.published = True
            self.marker.finish()
        except BaseException as exc:
            published = self.published
            self.published = False
            try:
                if published:
                    os.replace(self.target, self.stage)
                if moved:
                    os.replace(self.backup, self.target)
                self.marker.finish()
            except BaseException as rollback_error:
                exc.add_note(f"报告回滚失败：{rollback_error}；中断标记：{self.marker.path}")
                raise _StorageConsistencyError(f"报告回滚失败，保留中断标记：{self.marker.path}") from exc
            raise

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        for path in (self.stage, self.backup if self.published else None):
            if path is None or not path.exists():
                continue
            try:
                shutil.rmtree(path)
            except OSError as cleanup_error:
                if isinstance(exc, BaseException):
                    exc.add_note(f"报告暂存资源清理失败：{path}；{cleanup_error}")
                else:
                    # 已提交的完整报告不因旧备份回收失败改变成功结果。
                    import warnings

                    warnings.warn(f"报告已完成，暂存资源待回收：{path}；{cleanup_error}", RuntimeWarning, stacklevel=2)
