"""样本选择与独立查询视图，不改变原样本拥有者。"""

from __future__ import annotations

from typing import Any, Callable, Iterable, Mapping


class _SampleSetSelection:
    """将成员选择和独立视图构造集中到一个私有对象。"""

    def __init__(self, source: Any) -> None:
        self.source = source

    def items(
        self,
        *,
        uids: Iterable[str] | None = None,
        criteria: Mapping[str, Any] | None = None,
        filter: Callable | None = None,
        sort_by: str | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[tuple[str, Any]]:
        """只读取原成员，按原有查询顺序筛选。"""
        selected = {str(uid).strip() for uid in uids} if uids is not None else None
        items = [(uid, sample) for uid, sample in self.source.items() if selected is None or uid in selected]
        if criteria:
            items = [
                (uid, sample)
                for uid, sample in items
                if all(getattr(sample.metadata, field, None) == expected for field, expected in criteria.items())
            ]
        if filter is not None:
            items = [(uid, sample) for uid, sample in items if filter(sample)]
        if sort_by is not None:
            items.sort(key=lambda item: getattr(item[1].metadata, sort_by, None))
        if offset > 0:
            items = items[offset:]
        return items[:limit] if limit is not None else items

    def view(self, items: list[tuple[str, Any]], *, options: Any, categories: Any = None) -> Any:
        """复制成员状态并配置独立仓库门面，数组保持共享只读。"""
        subset = type(self.source)({uid: sample._clone_for_view() for uid, sample in items})
        return self.source._postprocess_subset_view(subset, view_options=options, categories=categories)


__all__ = ["_SampleSetSelection"]
