"""GUI 私有样本范围解析，区分未冻结请求和冻结空范围。"""

from __future__ import annotations

from dataclasses import dataclass

from .session import ProjectSession, resolve_scope_uids


@dataclass(frozen=True, slots=True)
class _ResolvedSampleScope:
    """保存明确的 UID 范围，空范围永不代表全量。"""

    uids: tuple[str, ...]

    @classmethod
    def resolve(
        cls,
        session: ProjectSession,
        frozen_uids: tuple[str, ...] | None = None,
        *,
        uids_text: str = "",
        all_samples: bool = False,
    ) -> _ResolvedSampleScope:
        """消费冻结范围，或在未冻结时解析当前范围。"""

        if frozen_uids is not None:
            return cls(frozen_uids)
        runtime = session.primary_runtime
        keys = getattr(runtime, "keys", None)
        items = getattr(runtime, "items", None)
        if all_samples or session.current_scope.scope_kind == "all_samples":
            if not callable(keys) and not callable(items):
                raise ValueError("当前主样本集无法枚举 UID，GUI 不能解析全部样本范围。")
        if all_samples:
            uids = tuple(str(uid) for uid in keys()) if callable(keys) else tuple(str(uid) for uid, _ in items())
            return cls(uids)
        return cls(tuple(resolve_scope_uids(session, uids_text)))

    def require_samples(self, operation: str) -> tuple[str, ...]:
        """拒绝空范围，并返回已解析 UID。"""

        if not self.uids:
            raise ValueError(f"当前范围没有可{operation}样本。")
        return self.uids
