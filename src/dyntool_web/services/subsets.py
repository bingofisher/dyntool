"""Web 子集筛选服务。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..schemas import SubsetRequest
from ..state import WebSessionState


DATA_SLOT_NAMES = ("accel", "vel", "disp", "force", "freqspec", "respspec", "otovl", "zvl", "fdmvl", "fpvdv")


@dataclass(slots=True)
class SubsetPreviewService:
    """执行 Web 子集筛选、排序与分页。"""

    state: WebSessionState
    request: SubsetRequest

    def build(self) -> dict[str, Any]:
        """返回子集预览结果。"""

        sample_set = self._require_runtime()
        if self._can_page_without_full_scan():
            return self._build_page_only(sample_set)
        rows = [self._row(uid, sample) for uid, sample in sample_set.items()]  # type: ignore[attr-defined]
        matched = [row for row in rows if self._matches(row)]
        sorted_rows = self._sort_rows(matched)
        offset = max(self.request.offset, 0)
        limit = max(min(self.request.limit, 1000), 1)
        page_rows = sorted_rows[offset : offset + limit]
        self.state.add_task("预览子集", "已完成", "1 / 1", f"命中 {len(matched)} 个样本。")
        return {
            "name": self.request.name,
            "count": len(page_rows),
            "total": len(matched),
            "limit": limit,
            "offset": offset,
            "total_mode": "exact",
            "columns": ["uid", "alias", self.request.metadata_field or "metadata", "数据状态"],
            "metadata_fields": self._metadata_fields(rows),
            "rows": page_rows,
            "matched_uids": [str(row["uid"]) for row in matched],
        }

    def _build_page_only(self, sample_set: object) -> dict[str, Any]:
        offset = max(self.request.offset, 0)
        limit = max(min(self.request.limit, 1000), 1)
        page_rows: list[dict[str, Any]] = []
        for index, (uid, sample) in enumerate(sample_set.items()):  # type: ignore[attr-defined]
            if index < offset:
                continue
            page_rows.append(self._row(uid, sample))
            if len(page_rows) >= limit:
                break
        self.state.add_task("预览子集", "已完成", "1 / 1", f"已加载当前页 {len(page_rows)} 个样本。")
        return {
            "name": self.request.name,
            "count": len(page_rows),
            "total": offset + len(page_rows),
            "limit": limit,
            "offset": offset,
            "total_mode": "page",
            "columns": ["uid", "alias", self.request.metadata_field or "metadata", "数据状态"],
            "metadata_fields": self._metadata_fields(page_rows),
            "rows": page_rows,
            "matched_uids": [str(row["uid"]) for row in page_rows],
        }

    def _can_page_without_full_scan(self) -> bool:
        return (
            not self.request.keyword.strip()
            and not self.request.metadata_field
            and not self.request.raw_data_vars
            and not self.request.analysis_data_vars
            and (self.request.sort_by or "uid") == "uid"
            and not self.request.sort_desc
        )

    def _require_runtime(self) -> object:
        if self.state.primary_runtime is None:
            raise ValueError("当前没有可筛选的主样本集。")
        return self.state.primary_runtime

    def _row(self, uid: object, sample: object) -> dict[str, Any]:
        metadata = self._metadata_payload(getattr(sample, "metadata", None))
        data_status = {name: getattr(sample, name, None) is not None for name in DATA_SLOT_NAMES}
        return {
            "uid": str(uid),
            "alias": str(getattr(sample, "alias", uid)),
            "metadata": metadata,
            "data_status": data_status,
        }

    def _matches(self, row: dict[str, Any]) -> bool:
        return self._matches_keyword(row) and self._matches_data_slots(row)

    def _matches_keyword(self, row: dict[str, Any]) -> bool:
        keyword = self.request.keyword.strip()
        if not keyword:
            return True
        if self.request.metadata_field:
            target = str(row["metadata"].get(self.request.metadata_field, ""))
        else:
            target = " ".join([row["uid"], row["alias"], *(str(value) for value in row["metadata"].values())])
        return _match_text(target, keyword, self.request.match_mode)

    def _matches_data_slots(self, row: dict[str, Any]) -> bool:
        data_status: dict[str, bool] = row["data_status"]
        required = [*self.request.raw_data_vars, *self.request.analysis_data_vars]
        return all(data_status.get(name, False) for name in required if name)

    def _sort_rows(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        sort_by = self.request.sort_by or "uid"

        def key(row: dict[str, Any]) -> str:
            if sort_by in {"uid", "alias"}:
                return str(row[sort_by])
            return str(row["metadata"].get(sort_by, ""))

        return sorted(rows, key=key, reverse=self.request.sort_desc)

    @staticmethod
    def _metadata_payload(metadata: object) -> dict[str, str]:
        if metadata is None:
            return {}
        if hasattr(metadata, "model_dump"):
            raw = metadata.model_dump()
        elif hasattr(metadata, "__dict__"):
            raw = vars(metadata)
        else:
            raw = {}
        return {str(key): "" if value is None else str(value) for key, value in raw.items()}

    @staticmethod
    def _metadata_fields(rows: list[dict[str, Any]]) -> list[str]:
        fields = {field for row in rows for field in row["metadata"]}
        return sorted(fields)


def preview_subset(state: WebSessionState, request: SubsetRequest) -> dict[str, Any]:
    """返回子集筛选预览。"""

    return SubsetPreviewService(state, request).build()


def save_subset(state: WebSessionState, request: SubsetRequest) -> dict[str, Any]:
    """保存子集请求并返回预览。"""

    payload = preview_subset(state, request)
    saved_subset = state.upsert_saved_subset(request.name, [str(uid) for uid in payload.get("matched_uids", [])])
    payload["message"] = f"已保存子集：{request.name}"
    payload["saved_subset"] = saved_subset
    return payload


def _match_text(target: str, keyword: str, match_mode: str) -> bool:
    if match_mode == "equals":
        return target == keyword
    if match_mode == "startswith":
        return target.startswith(keyword)
    if match_mode == "endswith":
        return target.endswith(keyword)
    return keyword in target
