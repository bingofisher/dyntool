"""GUI Internal 筛选查询树测试。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from dyntool_gui.session import FilterGroup, FilterPredicate, FilterSpec, ProjectSession, SampleSetSummary


@dataclass(slots=True)
class _Metadata:
    case: str
    point: str
    level: float


@dataclass(slots=True)
class _Sample:
    alias: str
    metadata: _Metadata
    accel: object | None = None
    freqspec: object | None = None
    zvl: object | None = None


class _Runtime:
    def __init__(self, samples: dict[str, _Sample]) -> None:
        self._samples = samples

    def items(self) -> tuple[tuple[str, _Sample], ...]:
        return tuple(self._samples.items())

    def keys(self) -> tuple[str, ...]:
        return tuple(self._samples.keys())

    def get(self, uid: str) -> _Sample | None:
        return self._samples.get(uid)


def _build_session(samples: dict[str, _Sample]) -> ProjectSession:
    summary = SampleSetSummary(
        name="测试主样本集",
        class_name="DefaultSampleSet",
        sample_type="DefaultSample",
        sample_domain="default",
        metadata_type="_Metadata",
        metadata_fields=("case", "point", "level"),
        supported_categories=("accel", "freqspec", "zvl"),
        storable_categories=("accel", "freqspec", "zvl"),
        supported_fields=("accel", "freqspec", "zvl", "alias", "metadata"),
        sample_count=len(samples),
        loaded_count=len(samples),
        unloaded_count=0,
        storage_binding="memory",
        strict=True,
        storage_dirty=False,
    )
    return ProjectSession(
        project_name="筛选测试",
        workdir=Path.cwd(),
        export_dir=Path.cwd() / "exports",
        note="",
        last_saved="",
        primary_sampleset=summary,
        compare_sampleset=None,
        other_samplesets=(),
        primary_runtime=_Runtime(samples),  # type: ignore[arg-type]
    )


def _samples() -> dict[str, _Sample]:
    return {
        "S1": _Sample("alpha-main", _Metadata("A", "P1", 1.0), accel=object(), freqspec=object(), zvl=object()),
        "S2": _Sample("beta-side", _Metadata("B", "P2", 2.5), accel=object(), freqspec=None, zvl=object()),
        "S3": _Sample("gamma-main", _Metadata("A", "P3", 4.0), accel=None, freqspec=object(), zvl=None),
        "S4": _Sample("delta-back", _Metadata("C", "P4", 7.5), accel=object(), freqspec=object(), zvl=object()),
        "S5": _Sample("epsilon-main", _Metadata("B", "P5", 9.0), accel=object(), freqspec=object(), zvl=None),
    }


def test_filter_query_tree_supports_boolean_groups_and_predicate_operators() -> None:
    """FilterGroup/FilterPredicate 应覆盖布尔组合、集合、比较、文本和存在性查询。"""

    query = FilterGroup(
        operator="and",
        children=(
            FilterPredicate("metadata.case", "in", ("A", "B")),
            FilterPredicate("metadata.case", "not_in", ("C",)),
            FilterPredicate("metadata.level", ">=", 2.0),
            FilterPredicate("metadata.level", "<", 10.0),
            FilterPredicate("alias", "contains", "main"),
            FilterPredicate("uid", "!=", "S3"),
            FilterPredicate("data.accel", "exists"),
            FilterPredicate("result.zvl", "not_exists"),
            FilterGroup("not", (FilterPredicate("metadata.point", "=", "P4"),)),
        ),
    )
    session = _build_session(_samples())

    rows = session.preview_subset(FilterSpec(query=query))

    assert tuple(row[0] for row in rows) == ("S5",)


def test_subset_preview_rows_are_limited_but_saved_dynamic_subset_keeps_all_matching_uids() -> None:
    """预览行数限制不应截断动态子集保存的完整命中 UID。"""

    session = _build_session(_samples())
    filter_spec = FilterSpec(
        query=FilterPredicate("alias", "contains", "main"),
        sort_by="uid",
        limit=1,
    )

    rows = session.preview_subset(filter_spec)
    definition = session.save_subset_definition(name="动态 main", freeze=False)

    assert tuple(row[0] for row in rows) == ("S1",)
    assert definition.mode == "dynamic"
    assert definition.resolved_uids == ("S1", "S3", "S5")
    assert definition.sample_count == 3


def test_subset_sort_by_uid_uses_runtime_key_not_sample_attribute() -> None:
    """按 UID 排序时应使用运行态 key，而不是样本对象上的可选属性。"""

    samples = _samples()
    session = _build_session({"S5": samples["S5"], "S1": samples["S1"], "S3": samples["S3"]})

    rows = session.preview_subset(
        FilterSpec(
            query=FilterPredicate("alias", "contains", "main"),
            sort_by="uid",
            sort_desc=True,
        )
    )

    assert tuple(row[0] for row in rows) == ("S5", "S3", "S1")


def test_frozen_subset_scope_uses_resolved_uids_instead_of_replaying_query() -> None:
    """冻结子集进入当前范围时应使用保存时的 resolved_uids。"""

    session = _build_session(_samples())
    session.preview_subset(FilterSpec(query=FilterPredicate("alias", "contains", "main")))
    definition = session.save_subset_definition(name="冻结 main", freeze=True)
    session.primary_runtime._samples["S6"] = _Sample("zeta-main", _Metadata("A", "P6", 6.0), accel=object())  # type: ignore[union-attr]
    session.set_current_scope("saved_subset", subset_ids=(definition.id,))

    from dyntool_gui.session import resolve_scope_uids

    assert resolve_scope_uids(session) == ["S1", "S3", "S5"]
