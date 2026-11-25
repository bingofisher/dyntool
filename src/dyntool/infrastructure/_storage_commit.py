"""Private / implementation detail：样本提交、中断检测与文件回滚。"""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
from tempfile import mkstemp
from uuid import uuid4
import warnings


class _StorageConsistencyError(RuntimeError):
    """仓库状态无法保证一致，必须停止整个批次。"""

    def __init__(self, message: str, *, committed: bool = False) -> None:
        super().__init__(message)
        self.committed = committed


class _WriteMarker:
    """记录未完成的写入；仅在提交或回滚确定完成后移除。"""

    pattern = ".dyntool-write-*.json"

    def __init__(self, directory: Path, description: str) -> None:
        self.path = directory / f".dyntool-write-{uuid4().hex}.json"
        self.description = description

    @classmethod
    def check(cls, directory: Path) -> None:
        markers = sorted(directory.glob(cls.pattern))
        if markers:
            raise _StorageConsistencyError(f"发现未完成写入标记：{markers[0]}；请先执行只读完整性检查")

    def start(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({"operation": self.description}, ensure_ascii=False), encoding="utf-8")

    def finish(self) -> None:
        self.path.unlink(missing_ok=True)


class _FileCommit:
    """暂存一个样本的所有文件，并在捕获异常时恢复已替换的文件。"""

    def __init__(self, directory: Path, description: str) -> None:
        self.marker = _WriteMarker(directory, description)
        self.staged: list[tuple[Path, Path]] = []
        self.backups: dict[Path, Path | None] = {}
        self.applied: list[Path] = []

    def __enter__(self) -> _FileCommit:
        _WriteMarker.check(self.marker.path.parent)
        self.marker.start()
        return self

    def stage(self, target: Path, *, preserve: bool = False) -> Path:
        target.parent.mkdir(parents=True, exist_ok=True)
        descriptor, name = mkstemp(prefix=".dyntool-stage-", suffix=target.suffix, dir=target.parent)
        os.close(descriptor)
        staged = Path(name)
        self.staged.append((target, staged))
        if preserve and target.exists():
            shutil.copy2(target, staged)
        return staged

    def commit(self) -> None:
        for target, staged in self.staged:
            backup = None
            if target.exists():
                descriptor, name = mkstemp(prefix=".dyntool-backup-", suffix=target.suffix, dir=target.parent)
                os.close(descriptor)
                backup = Path(name)
                self.backups[target] = backup
                shutil.copy2(target, backup)
            else:
                self.backups[target] = None
            os.replace(staged, target)
            self.applied.append(target)

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        rollback_ok = True
        if exc_type is not None:
            try:
                for target in reversed(self.applied):
                    backup = self.backups[target]
                    if backup is None:
                        target.unlink(missing_ok=True)
                    else:
                        os.replace(backup, target)
            except BaseException as rollback_error:
                rollback_ok = False
                if isinstance(exc, BaseException):
                    exc.add_note(f"回滚异常：{rollback_error}")
                raise _StorageConsistencyError(f"样本文件回滚失败，保留中断标记 {self.marker.path}") from exc
            finally:
                if not rollback_ok and isinstance(exc, BaseException):
                    exc.add_note(f"回滚失败；中断标记：{self.marker.path}")
        if rollback_ok:
            for path in [*(staged for _, staged in self.staged), *(p for p in self.backups.values() if p is not None)]:
                try:
                    path.unlink(missing_ok=True)
                except OSError as cleanup_error:
                    warnings.warn(f"临时文件清理失败：{path}：{cleanup_error}", RuntimeWarning, stacklevel=2)
            try:
                self.marker.finish()
            except OSError as cleanup_error:
                raise _StorageConsistencyError(
                    f"中断标记无法移除：{self.marker.path}",
                    committed=exc_type is None,
                ) from (exc if isinstance(exc, BaseException) else cleanup_error)
