"""核心架构缺陷回归，所有写入仅使用临时合成仓库。"""

from pathlib import Path
from copy import deepcopy
import gc
import logging
import json
from unittest.mock import patch

import h5py
import numpy as np
import pandas as pd
import pytest

from dyntool import AccelSeries, DefaultSample, DefaultSampleSet, Metadata, UnitSystem
from dyntool import reporting
from dyntool.compute import ComputeContext
from dyntool.compute.pipelines import resp_eval_template
from dyntool.compute.signals import IntegMethod
from dyntool.domain.runtime import core as runtime_core
from dyntool.domain.runtime.errors import RecoverableIOError
from dyntool.domain.samples.registry import sample_from_structured_payload, sample_set_from_structured_payload
from dyntool.domain.samples.types import SampleSetViewOptions, StorageAccessMode
from dyntool.logging.config import LoggingConfig
from dyntool.logging.provider import _FeatureFileRouterHandler
from dyntool.storage import SampleLoadMode, StorageScheme, StorageMode


def make_sample(name: str, unit: str = "m/s**2") -> DefaultSample:
    """创建可区分身份的合成样本。"""
    return DefaultSample(
        metadata=Metadata(identity={"case": name}), accel=AccelSeries.from_data([1, 2, 3], dt=0.01, data_unit=unit)
    )


def make_store(path: Path) -> tuple[DefaultSampleSet, DefaultSample]:
    """创建已保存的最小 SQLite/H5 仓库。"""
    sample = make_sample("first")
    samples = DefaultSampleSet([sample])
    samples.save(path, storage_scheme=StorageScheme.SET_SQLITE_H5)
    return samples, sample


def test_queries_preserve_owner_and_lazy_payload(tmp_path: Path) -> None:
    """查询和摘要不得改变拥有者或破坏后续懒读取。"""
    samples, sample = make_store(tmp_path / "source")
    view = samples.find(uids=[sample.uid])
    assert sample._storage_set is samples
    assert view[sample.uid] is not sample
    samples.scalar_frame(features=["pga"])
    sample.update(accel=AccelSeries.from_data([10, 20, 30], dt=0.01))
    assert samples.storage_dirty
    assert samples.scalar_frame(features=["pga"]).iloc[0]["pga"] == 30
    lazy = DefaultSampleSet().load(
        tmp_path / "source", storage_scheme=StorageScheme.SET_SQLITE_H5, load_mode=SampleLoadMode.LAZY
    )
    lazy.scalar_frame(features=["pga"])
    np.testing.assert_array_equal(lazy[sample.uid].accel.get_value(), [1, 2, 3])


def test_readonly_view_blocks_source_and_can_save_elsewhere(tmp_path: Path) -> None:
    """只读子集独立计算、禁止源写入，但可另存。"""
    samples, sample = make_store(tmp_path / "source")
    view = samples.find_many(uids=[sample.uid])
    assert view.storage is not samples.storage
    view[sample.uid].update(accel=AccelSeries.from_data([7, 8, 9], dt=0.01))
    with pytest.raises(PermissionError, match="只读"):
        view.save_all(show_progress=False)
    with pytest.raises(PermissionError, match="只读"):
        view.save(tmp_path / "source" / ".." / "source")
    view.save(tmp_path / "analysis", storage_scheme=StorageScheme.SET_SQLITE_H5)
    assert sample.pga() == 3
    reopened = DefaultSampleSet().load(tmp_path / "analysis", storage_scheme=StorageScheme.SET_SQLITE_H5)
    assert reopened[sample.uid].pga() == 9


def test_readwrite_view_only_commits_selected_members(tmp_path: Path) -> None:
    """显式可写视图的报告与真实写入成员相同。"""
    samples, first = make_store(tmp_path / "source")
    second = make_sample("second")
    samples.add_sample(second)
    samples.save_all(show_progress=False)
    view = samples.find_many(
        uids=[first.uid], view_options=SampleSetViewOptions(access_mode=StorageAccessMode.READ_WRITE)
    )
    view[first.uid].update(accel=AccelSeries.from_data([7, 8, 9], dt=0.01))
    strategy = view.storage._sample_storage.strategy
    with patch.object(strategy, "_write_payload", wraps=strategy._write_payload) as writer:
        report = view.save_all(show_progress=False)
    assert writer.call_count == report.stats.succeeded == 1
    assert first.pga() == 3
    loaded = DefaultSampleSet().load(tmp_path / "source", storage_scheme=StorageScheme.SET_SQLITE_H5)
    assert loaded[first.uid].pga() == 9
    assert loaded[second.uid].pga() == 3


def test_metadata_failures_leave_identity_and_alias_unchanged() -> None:
    """冲突及多字段校验失败后恢复全部身份状态。"""
    first, second = make_sample("first"), make_sample("second")
    samples = DefaultSampleSet([first, second])
    old = (first.uid, first.alias, first.metadata.to_dict(), tuple(samples))
    with pytest.raises(ValueError, match="UID 冲突"):
        first.replace_metadata(second.metadata.model_copy(deep=True))
    assert (first.uid, first.alias, first.metadata.to_dict(), tuple(samples)) == old
    with pytest.raises(KeyError, match="未知"):
        first.update_metadata(identity={"case": "changed"}, nonexistent_field=True)
    assert (first.uid, first.alias, first.metadata.to_dict(), tuple(samples)) == old


def test_read_surfaces_isolate_mutable_state(tmp_path: Path) -> None:
    """数组只读，xarray 与字典为可编辑但不会写回对象的快照。"""
    samples, sample = make_store(tmp_path / "source")
    with pytest.raises(ValueError):
        sample.accel.get_value()[:] *= 10
    with pytest.raises(ValueError):
        sample.accel.get_value().setflags(write=True)
    exported = sample.accel.xr
    exported.values[:] *= 10
    sample.metadata.identity["case"] = "changed"
    sample.data_vars.clear()
    samples.data.clear()
    assert sample.pga() == 3
    assert sample.metadata.identity == {"case": "first"}
    assert len(samples) == 1 and not samples.storage_dirty


def test_unit_conversion_and_mapping_updates_invalidate_summary(tmp_path: Path) -> None:
    """正式单位转换和集合赋值均维护脏状态与真实摘要。"""
    samples, sample = make_store(tmp_path / "source")
    sample.accel.convert_units({"value": "cm/s**2"})
    assert samples.storage_dirty
    assert samples.scalar_frame(features=["pga"]).iloc[0]["pga"] == pytest.approx(300)
    samples.save_all(show_progress=False)
    second = make_sample("second")
    samples[second.uid] = second
    assert samples.storage_dirty
    assert samples.scalar_frame(features=["pga"]).set_index("uid").loc[second.uid, "pga"] == 3


@pytest.mark.parametrize("method", [IntegMethod.SCIPY_CUMTRAPZ, IntegMethod.SELF_CUMTRAPZ])
def test_multichannel_integration_uses_time_axis(method: IntegMethod) -> None:
    """非方阵常量多通道积分符合解析结果。"""
    axis = np.arange(7) * 0.1
    values = np.tile([1.0, 2.0, 3.0], (7, 1))
    model = AccelSeries.from_data(values, time=axis)
    velocity = model.calc_vel(method=method)
    np.testing.assert_allclose(velocity.get_value(), axis[:, None] * [1, 2, 3], atol=1e-12)


def test_array_pipeline_respects_input_units() -> None:
    """数组工程输入与 SI 输入得到相同物理响应谱。"""
    signal = np.sin(np.arange(1024) * 0.1)
    si = resp_eval_template(signal * 9.80665, dt=0.01).result()
    engineering = resp_eval_template(
        signal,
        dt=0.01,
        context=ComputeContext(input_unit_system=UnitSystem.engineering(), output_unit_system=UnitSystem.si()),
    ).result()
    np.testing.assert_allclose(engineering["sa"], si["sa"], rtol=1e-12)


def test_scalar_export_canonicalizes_units(tmp_path: Path) -> None:
    """同物理加速度混合表示导出为相同 SI 数值并标注单位。"""
    first = make_sample("si")
    second = make_sample("cm", "cm/s**2")
    second.update(accel=AccelSeries.from_data([100, 200, 300], dt=0.01, data_unit="cm/s**2"))
    samples = DefaultSampleSet([first, second])
    path = reporting.export_scalar_frame(samples, tmp_path / "scalar.csv", features=["pga"], format="csv")
    frame = pd.read_csv(path)
    column = next(name for name in frame if name.startswith("pga"))
    assert column != "pga"
    np.testing.assert_allclose(frame[column], [3, 3])


def test_default_report_exports_without_evaluation_slots(tmp_path: Path) -> None:
    """通用样本默认报告不读取 schema 不支持的评价槽位。"""
    result = reporting.export_report_package(
        DefaultSampleSet([make_sample("report")]), tmp_path / "report", include_plots=False
    )
    assert (result / "manifest.json").is_file()


def test_default_exchange_payload_roundtrips_and_rejects_future() -> None:
    """正式类别可注册往返，未来版本不得被静默降写。"""
    sample = make_sample("payload")
    payload = sample.to_structured_payload()
    assert payload.category == "DefaultSample"
    assert sample_from_structured_payload(payload).uid == sample.uid
    samples = DefaultSampleSet([sample])
    assert len(sample_set_from_structured_payload(samples.to_structured_payload())) == 1
    payload.schema_version = "99.0.0"
    with pytest.raises(ValueError, match="版本"):
        sample_from_structured_payload(payload)


def test_h5_unit_inspection_does_not_read_arrays(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """单位查询不得读取任何 Dataset 数值。"""
    path = tmp_path / "accel.h5"
    make_sample("units").accel.to_h5(path)

    def fail(*args: object, **kwargs: object) -> None:
        raise AssertionError("单位查询读取了数组")

    monkeypatch.setattr(h5py.Dataset, "__getitem__", fail)
    assert AccelSeries.inspect_units(path)["value"]


def test_log_router_constructs_one_handler_per_feature(tmp_path: Path) -> None:
    """重复日志不会构造并遗留未使用 handler。"""
    router = _FeatureFileRouterHandler(LoggingConfig(log_dir=str(tmp_path)))
    try:
        with patch.object(router, "_build_handler", wraps=router._build_handler) as build:
            for _ in range(20):
                router.handle(logging.LogRecord("dyntool.sample", logging.INFO, __file__, 1, "test", (), None))
        assert build.call_count == 1
    finally:
        router.close()


def test_runtime_binding_disappears_when_target_is_collected() -> None:
    """对象回收即时释放实例 runtime 绑定。"""
    target = make_sample("runtime")
    key = id(target)
    runtime_core._bind_instance_runtime(runtime_core._sample_instance_runtimes, target, object())
    del target
    gc.collect()
    assert key not in runtime_core._sample_instance_runtimes


@pytest.mark.parametrize("scheme", list(StorageScheme))
def test_result_state_survives_partial_save(tmp_path: Path, scheme: StorageScheme) -> None:
    """改变输入后只保存输入，未选中的频谱和过期依据一起保留。"""
    sample = DefaultSample(
        metadata=Metadata(identity={"case": "trace"}), accel=AccelSeries.from_data(np.sin(np.arange(64)), dt=0.01)
    )
    sample.update(freqspec=sample.accel.calc_freqspec())
    assert sample._slot_state["freqspec"]["status"] == "fresh"
    samples = DefaultSampleSet([sample])
    path = tmp_path / "source"
    samples.save(path, storage_scheme=scheme)
    sample.accel.convert_units({"value": "cm/s**2"})
    assert sample._slot_state["freqspec"]["status"] == "fresh"
    sample.update(accel=AccelSeries.from_data(np.cos(np.arange(64)), dt=0.01))
    assert sample._slot_state["freqspec"]["status"] == "stale"
    samples.save_all(categories=["accel"], show_progress=False)
    loaded = DefaultSampleSet().load(path, storage_scheme=scheme, load_mode=SampleLoadMode.EAGER)
    assert loaded[sample.uid]._slot_state["freqspec"]["status"] == "stale"
    assert loaded[sample.uid].freqspec is not None
    assert loaded[sample.uid].freqspec.to_dict()["_dyntool"]["status"] == "stale"


@pytest.mark.parametrize("scheme", list(StorageScheme))
@pytest.mark.parametrize("strict", [True, False])
def test_name_collision_preserves_prior_commit(tmp_path: Path, scheme: StorageScheme, strict: bool) -> None:
    """文件命名冲突遵循严格合同；集合方案使用 UID，不误覆盖其他成员。"""
    members = [make_sample("one"), make_sample("two"), make_sample("three")]
    samples = DefaultSampleSet(members)
    first, second, third = members
    samples.connect_storage(
        tmp_path / "names",
        mode=StorageMode.CREATE,
        storage_scheme=scheme,
        name_resolver=lambda sample, context: "third" if sample.uid == third.uid else "same",
    )
    named_files = scheme not in {StorageScheme.SET_H5, StorageScheme.SET_SQLITE_H5}
    if strict and named_files:
        with pytest.raises(RecoverableIOError, match="保存样本失败") as error:
            samples.save_all(strict=True, show_progress=False)
        assert "命名冲突" in str(error.value.__cause__)
    else:
        report = samples.save_all(strict=strict, show_progress=False)
        assert report.stats.succeeded == (2 if named_files else 3)
        assert report.stats.failed == (1 if named_files else 0)
    loaded = DefaultSampleSet().load(tmp_path / "names", storage_scheme=scheme, load_mode=SampleLoadMode.EAGER)
    expected = [first.uid] if strict and named_files else [first.uid, third.uid] if named_files else list(samples)
    assert set(loaded) == set(expected)
    for uid in expected:
        np.testing.assert_array_equal(loaded[uid].accel.get_value(), samples[uid].accel.get_value())
    if named_files:
        assert not samples[second.uid]._committed_slot_state


def test_report_failure_keeps_previous_version(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """完整报告生成中途失败不混入旧版本，清单外文件仍保留。"""
    from dyntool.reporting import _api

    samples = DefaultSampleSet([make_sample("report")])
    target = reporting.export_report_package(samples, tmp_path / "report", include_plots=False)
    before = (target / "report.xlsx").read_bytes()
    (target / "notes.txt").write_text("用户文件", encoding="utf-8")

    def fail(*args: object, **kwargs: object) -> None:
        raise ValueError("注入报告失败")

    monkeypatch.setattr(_api, "write_frames_workbook", fail)
    with pytest.raises(ValueError, match="注入"):
        reporting.export_report_package(samples, target, include_plots=False)
    assert (target / "report.xlsx").read_bytes() == before
    assert (target / "notes.txt").read_text(encoding="utf-8") == "用户文件"


def test_structured_payload_rejects_duplicate_conflict() -> None:
    """结构化字段不能被重复的旧字典静默覆盖。"""
    payload = make_sample("conflict").accel.to_structured_payload()
    payload.data_vars["value"] = np.array([10, 20, 30])
    with pytest.raises(ValueError, match="不一致"):
        AccelSeries.from_structured_payload(payload)


def test_structured_payload_rejects_conflicting_coordinate_and_variable() -> None:
    """坐标和值重复声明同名字段时，不允许后者静默覆盖坐标。"""
    payload = make_sample("axis-conflict").accel.to_structured_payload()
    payload.meta.clear()
    payload.data_vars["time"] = np.array([0.0, 0.1, 0.2])
    with pytest.raises(ValueError, match="不一致"):
        AccelSeries.from_structured_payload(payload)


@pytest.mark.parametrize("schema_version", ["1.-1.0", "1.0.-1", "1.+0.0", "1. 0.0", "01.0.0", "1.０.0"])
def test_exchange_payload_rejects_invalid_version_format(schema_version: str) -> None:
    """版本必须使用规范的非负 ASCII 三段编号，不能借负数绕过范围校验。"""
    from dyntool.domain.serialization import StructuredPayload

    with pytest.raises(ValueError, match="版本"):
        StructuredPayload(schema_version=schema_version)


@pytest.mark.parametrize("missing", ["operation", "parameters", "inputs", "input_units", "computed_at"])
def test_result_provenance_rejects_fresh_record_without_basis(missing: str) -> None:
    """新计算状态必须具有计算依据，不能只有 fresh 标签或残缺属性。"""
    model = make_sample("basis").accel.calc_freqspec()
    payload = model.to_dict()
    payload["_dyntool"].pop(missing)
    with pytest.raises(ValueError, match="追溯"):
        type(model).from_dict(payload)


def test_result_provenance_rejects_history_without_input_revision() -> None:
    """损坏的历史记录应在恢复处明确报错，不在样本绑定时发生键错误。"""
    model = make_sample("history-basis").accel.calc_freqspec()
    payload = model.to_dict()
    payload["_dyntool"]["history"][-1].pop("input_revision")
    with pytest.raises(ValueError, match="追溯"):
        type(model).from_dict(payload)


@pytest.mark.parametrize(
    ("field", "invalid"),
    [("inputs", []), ("inputs", {"source": 123}), ("computed_at", "无效时间"), ("computed_at", "2026-10-05T00:00:00")],
)
def test_result_provenance_rejects_invalid_basis_values(field: str, invalid) -> None:
    """输入版本类型和 UTC 计算时间在恢复边界明确校验。"""
    model = make_sample("invalid-basis").accel.calc_freqspec()
    payload = model.to_dict()
    payload["_dyntool"][field] = invalid
    with pytest.raises(ValueError, match="追溯"):
        type(model).from_dict(payload)


def test_deep_inspection_rejects_incomplete_provenance_without_mutation(tmp_path: Path) -> None:
    """深度检查定位残缺的已知状态，且不修复或修改合成源仓库。"""
    from dyntool.storage import inspect_storage_repository

    sample = make_sample("deep-basis")
    sample.compute.freqspec()
    samples = DefaultSampleSet([sample])
    target = tmp_path / "source"
    samples.save(target, storage_scheme=StorageScheme.SET_SQLITE_H5)
    payload_file = samples.storage._sample_storage.strategy.ctx.sqlite_payload_h5_path()
    with h5py.File(payload_file, "r+") as handle:
        group = handle[f"/samples/{sample._storage_payload_id}/slots/freqspec"]
        record = json.loads(group.attrs["_dyntool"])
        record.pop("operation")
        group.attrs["_dyntool"] = json.dumps(record, ensure_ascii=False)
    before = {path: path.read_bytes() for path in target.iterdir() if path.is_file()}
    report = inspect_storage_repository(target, level="deep")
    assert not report.is_valid
    assert any("追溯" in issue and "operation" in issue for issue in report.issues)
    assert {path: path.read_bytes() for path in before} == before


@pytest.mark.parametrize("nested", [False, True])
def test_structured_payload_rejects_conflicting_provenance(nested: bool) -> None:
    """重复追溯的矛盾不能被静默忽略，历史缺失属性仍可读取。"""
    model = make_sample("provenance").accel
    if nested:
        model = model.calc_freqspec()
    payload = model.to_structured_payload()
    payload.meta["raw_dict"] = deepcopy(payload.meta["raw_dict"])
    raw = payload.meta["raw_dict"]["amp"] if nested else payload.meta["raw_dict"]
    raw["_dyntool"]["status"] = "stale"
    with pytest.raises(ValueError, match="不一致"):
        type(model).from_structured_payload(payload)
    raw.pop("_dyntool")
    restored = type(model).from_structured_payload(payload)
    assert restored.to_dict()["_dyntool"] == model.to_dict()["_dyntool"]


@pytest.mark.parametrize("target", ["accel", "freqspec", "component"])
@pytest.mark.parametrize("error_type", [ValueError, KeyboardInterrupt])
def test_unit_conversion_callback_failure_restores_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, target: str, error_type: type[BaseException]
) -> None:
    """单位发布回调失败后恢复模型、组合绑定、追溯、摘要和脏状态。"""
    samples, sample = make_store(tmp_path / "source")
    sample.update(freqspec=sample.accel.calc_freqspec())
    samples.save_all(show_progress=False)
    model = sample.accel if target == "accel" else sample.freqspec
    if target == "component":
        model = sample.freqspec.amp
    unit_patch = {"value" if target == "accel" else "amp": "cm/s**2"}
    units, provenance = model.current_units(), deepcopy(model.to_dict()["_dyntool"])
    old_components = (sample.freqspec.amp, sample.freqspec.pha)
    old_root_provenance = deepcopy(sample.freqspec.to_dict()["_dyntool"])
    old_states = deepcopy(sample._slot_state)
    dirty = set(sample._dirty_categories)
    original = DefaultSample._on_model_representation_changed

    def fail(self: DefaultSample, field: object) -> None:
        original(self, field)
        raise error_type("注入单位回调失败")

    monkeypatch.setattr(DefaultSample, "_on_model_representation_changed", fail)
    with pytest.raises(error_type, match="注入"):
        model.convert_units(unit_patch)
    assert model.current_units() == units
    assert model.to_dict()["_dyntool"] == provenance
    assert sample._slot_state == old_states
    assert sample.freqspec.to_dict()["_dyntool"] == old_root_provenance
    assert sample._dirty_categories == dirty
    assert not samples.storage_dirty
    assert (sample.freqspec.amp, sample.freqspec.pha) == old_components
    assert all(component._owner_ref() is sample for component in old_components)
    assert samples.scalar_frame(features=["pga"]).iloc[0]["pga"] == 3.0
    monkeypatch.undo()
    model.convert_units(unit_patch)
    assert samples.storage_dirty
    root = sample.accel if target == "accel" else sample.freqspec
    assert root.to_dict()["_dyntool"]["output_units"] == root.current_units()
    samples.save_all(show_progress=False)
    reopened = DefaultSampleSet().load(tmp_path / "source", storage_scheme=StorageScheme.SET_SQLITE_H5)
    assert reopened[sample.uid].accel.get_value(unit="m/s**2")[-1] == pytest.approx(3.0)


def test_collection_standard_mutations_and_copy(tmp_path: Path) -> None:
    """标准映射修改维护绑定；复制不夺走成员拥有者。"""
    samples, first = make_store(tmp_path / "source")
    second = make_sample("second")
    samples.update({second.uid: second})
    copied = samples.copy()
    assert first._storage_set is samples and copied[first.uid] is not first
    assert np.shares_memory(first.accel.get_value(), copied[first.uid].accel.get_value())
    removed = samples.pop(second.uid)
    assert removed._storage_set is None
    samples.clear()
    assert len(samples) == 0 and first._storage_set is None and samples.storage_dirty
    assert len(copied) == 2


def test_metadata_callback_failure_restores_aggregate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """拥有者已经更新索引后回调失败，所有身份状态仍恢复。"""
    samples, sample = make_store(tmp_path / "source")
    old = sample.uid, sample.alias, sample.metadata.to_dict(), list(samples)
    original = samples._on_sample_metadata_changed

    def fail(item: DefaultSample, old_uid: str) -> None:
        original(item, old_uid)
        raise ValueError("注入身份回调失败")

    monkeypatch.setattr(samples, "_on_sample_metadata_changed", fail)
    with pytest.raises(ValueError, match="注入"):
        sample.update_metadata(identity={"case": "changed"})
    assert (sample.uid, sample.alias, sample.metadata.to_dict(), list(samples)) == old
    assert not samples.storage_dirty and sample._storage_set is samples


def test_slot_callback_failure_restores_provenance(monkeypatch: pytest.MonkeyPatch) -> None:
    """更新第二个槽位失败时恢复第一个槽位与失效结果状态。"""
    sample = make_sample("rollback")
    sample.update(freqspec=sample.accel.calc_freqspec())
    original = sample.set_data_var
    before = sample.freqspec.to_dict()["_dyntool"]
    calls = 0

    def fail(field: object, value: object) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise ValueError("注入槽位回调失败")
        original(field, value)

    monkeypatch.setattr(DefaultSample, "set_data_var", lambda self, field, value: fail(field, value))
    with pytest.raises(ValueError, match="注入"):
        sample.update(accel=AccelSeries.from_data([4, 5, 6], dt=0.01), freqspec=sample.freqspec)
    assert sample.pga() == 3
    assert sample.freqspec.to_dict()["_dyntool"] == before


def test_load_many_does_not_overwrite_dirty_loaded_slot(tmp_path: Path) -> None:
    """补载派生结果时保留内存中已修改的输入。"""
    samples, sample = make_store(tmp_path / "source")
    sample.update(freqspec=sample.accel.calc_freqspec())
    samples.save_all(show_progress=False)
    loaded = DefaultSampleSet().load(tmp_path / "source", storage_scheme=StorageScheme.SET_SQLITE_H5)
    loaded[sample.uid].update(accel=AccelSeries.from_data([10, 20, 30], dt=0.01))
    loaded.load_many(categories=["accel", "freqspec"])
    assert loaded[sample.uid].pga() == 30
    assert loaded[sample.uid].freqspec is not None


def test_readonly_view_rejects_all_source_write_routes(tmp_path: Path) -> None:
    """整理、重建、跨格式覆盖和单样本保存统一拒绝源写入。"""
    samples, sample = make_store(tmp_path / "source")
    view = samples.find()
    with pytest.raises(PermissionError, match="只读"):
        view.storage.organize()
    with pytest.raises(PermissionError, match="只读"):
        view.connect_storage(tmp_path / "source", mode=StorageMode.RECREATE)
    with pytest.raises(PermissionError, match="只读"):
        view.convert_storage(tmp_path / "source", storage_scheme=StorageScheme.SET_DIR, mode=StorageMode.RECREATE)
    with pytest.raises(PermissionError, match="只读"):
        view[sample.uid].save(tmp_path / "source", mode=StorageMode.RECREATE)


def test_constructor_isolates_caller_array() -> None:
    """构造后调用者继续编辑原数组不会修改模型。"""
    values = np.array([1.0, 2.0, 3.0])
    series = AccelSeries.from_data(values, dt=0.01)
    values[:] = 10
    np.testing.assert_array_equal(series.get_value(), [1, 2, 3])


def test_multichannel_derivative_has_independent_analytic_reference() -> None:
    """矩形矩阵逐通道线性函数的一阶导数为已知常量。"""
    from dyntool.compute.signals import Differentiation

    time = np.linspace(0, 1, 7)
    slopes = np.array([1.0, -2.0, 3.0])
    values = time[:, None] * slopes + [2, 4, 6]
    actual = Differentiation(values, x=time).diff1d()
    np.testing.assert_allclose(actual, np.broadcast_to(slopes, values.shape), atol=1e-14)


def test_fractional_sampling_frequency_band_boundary() -> None:
    """非整数采样率进入求解器，已知正弦 RMS 符合独立积分基准。"""
    from dyntool.compute.features import band_rms_feature

    fs, n, bin_number = 100.25, 1024, 100
    frequency = fs * bin_number / n
    signal = 3 * np.sin(2 * np.pi * bin_number * np.arange(n) / n)
    center = frequency
    from dyntool.compute import features

    with patch.object(features, "_band_rms", wraps=features._band_rms) as solver:
        actual = band_rms_feature(signal, fs=fs, center_freq=center)["band_rms"]
    assert solver.call_args.kwargs["fs"] == fs
    expected = np.sqrt((np.sum(signal**2) - 0.5 * (signal[0] ** 2 + signal[-1] ** 2)) / n)
    assert actual == pytest.approx(expected, rel=1e-10)


def test_response_pipeline_damping_matches_step_solution() -> None:
    """恒定地面加速度的位移峰值满足解析阶跃解，并记录上下文阻尼。"""
    damping = 0.2
    accel = AccelSeries.from_data(np.ones(2048), dt=0.01)
    result = resp_eval_template(accel, context=ComputeContext(damping_ratio=damping)).result()
    period = result.sd.get_axis()
    index = np.argmin(abs(period - 1))
    expected = (1 + np.exp(-damping * np.pi / np.sqrt(1 - damping**2))) / (2 * np.pi) ** 2
    assert result.sd.get_value()[index] == pytest.approx(expected, rel=0.003)
    assert result.to_dict()["_dyntool"]["parameters"]["damping_ratio"] == damping


def test_explicit_fft_context_converts_values_and_units() -> None:
    """默认频谱保留 g，显式输出 SI 后幅值和标签一起转换。"""
    from dyntool.compute.pipelines import freq_eval_template

    values = 2 * np.cos(2 * np.pi * 20 * np.arange(1024) / 1024 + 0.3)
    accel = AccelSeries.from_data(values, dt=0.01, data_unit="g_force")
    ordinary = freq_eval_template(accel).result()
    explicit = freq_eval_template(accel, context=ComputeContext(output_unit_system=UnitSystem.si())).result()
    assert ordinary.amp.get_value()[20] == pytest.approx(2, rel=2e-5)
    assert explicit.amp.get_value()[20] == pytest.approx(2 * 9.80665, rel=2e-5)
    assert explicit.pha.get_value(unit="radian")[20] == pytest.approx(0.3, abs=2e-5)


def test_exchange_migration_preserves_source(tmp_path: Path) -> None:
    """离线迁移只改已知类别，新输出经过注册验证，源文件原样保留。"""
    import json
    import subprocess
    import sys

    payload = DefaultSampleSet([make_sample("migration")]).to_structured_payload().to_dict()
    payload["category"] = "SampleSet"
    for child in payload["data_vars"].values():
        child["category"] = "Sample"
    payload["attrs"]["sample_type"] = "Sample"
    source, target = tmp_path / "old.json", tmp_path / "new.json"
    source.write_text(json.dumps(payload, default=lambda array: array.tolist()), encoding="utf-8")
    before = source.read_bytes()
    subprocess.run(
        [
            sys.executable,
            "-B",
            "scripts/migrate_default_exchange_payload.py",
            "--input",
            str(source),
            "--output",
            str(target),
        ],
        check=True,
    )
    restored = sample_set_from_structured_payload(json.loads(target.read_text(encoding="utf-8")))
    assert len(restored) == 1 and source.read_bytes() == before


def test_sqlite_lazy_batch_does_not_scan_whole_index(tmp_path: Path) -> None:
    """单样本和批次补载只刷新目标索引，摘要无需索引全表刷新。"""
    samples, first = make_store(tmp_path / "source")
    for i in range(4):
        samples.add_sample(make_sample(str(i)))
    samples.save_all(show_progress=False)
    loaded = DefaultSampleSet().load(tmp_path / "source", storage_scheme=StorageScheme.SET_SQLITE_H5)
    strategy = loaded.storage._sample_storage.strategy
    with patch.object(strategy, "_refresh_cache", wraps=strategy._refresh_cache) as refresh:
        loaded.scalar_frame(features=["pga"])
        assert refresh.call_count == 0
        loaded.load_many(uids=[first.uid], categories=["accel"])
        assert refresh.call_count == 1
        assert refresh.call_args.kwargs["uids"] == [first.uid]


def test_after_commit_never_rebuilds_serialization_plan(tmp_path: Path) -> None:
    """提交后的状态发布复用实际写入计划，避免二次序列化再失败。"""
    samples, sample = make_store(tmp_path / "source")
    context = samples.storage._sample_storage.ctx
    with patch.object(context, "write_plan", wraps=context.write_plan) as build:
        samples.save_all(show_progress=False)
    assert build.call_count == 1
    assert sample._committed_slot_state == sample._slot_state


def test_model_export_cannot_overwrite_readonly_source(tmp_path: Path) -> None:
    """绑定到只读视图的模型也不能把文件导出到源仓库内。"""
    samples, sample = make_store(tmp_path / "source")
    view = samples.find()
    with pytest.raises(PermissionError, match="只读"):
        view[sample.uid].accel.to_h5(tmp_path / "source" / "payloads.h5")


def test_log_close_failure_still_closes_remaining_handlers(monkeypatch: pytest.MonkeyPatch) -> None:
    """关闭一个 handler 失败不会遗留后续 handler。"""
    from dyntool.logging.provider import _StdlibLoggerFactory

    root = logging.Logger("isolated")
    first, second = logging.Handler(), logging.Handler()
    first._dyntool_managed = second._dyntool_managed = True
    root.addHandler(first)
    root.addHandler(second)
    monkeypatch.setattr(first, "close", lambda: (_ for _ in ()).throw(OSError("注入关闭失败")))
    with patch.object(second, "close", wraps=second.close) as close:
        with pytest.raises(ExceptionGroup, match="关闭失败"):
            _StdlibLoggerFactory._clear_managed_handlers(root)
    assert close.call_count == 1 and not root.handlers


def test_si_series_peaks_workbook_and_state_manifest(tmp_path: Path) -> None:
    """混合单位的序列、峰值和 Excel 单位页保持同一 SI 物理量。"""
    import json
    from openpyxl import load_workbook
    from dyntool.reporting._frame_builders import _ReportFrames

    first, second = make_sample("si"), make_sample("cm")
    first.update(accel=AccelSeries.from_data([0, 2, 0, 3, 0], dt=0.01))
    second.update(accel=AccelSeries.from_data([0, 200, 0, 300, 0], dt=0.01, data_unit="cm/s**2"))
    first.compute.freqspec()
    first.update(accel=AccelSeries.from_data([0, 4, 0, 6, 0], dt=0.01))
    result = first.compute.freqspec()
    assert result.status == "skipped" and "过期" in result.message
    samples = DefaultSampleSet([first, second])
    frame = _ReportFrames.series(samples, "accel")
    np.testing.assert_allclose(frame.iloc[:, 0], [0, 4, 0, 6, 0])
    np.testing.assert_allclose(frame.iloc[:, 1], [0, 2, 0, 3, 0])
    peaks = _ReportFrames.peaks(samples)
    value_columns = [column for column in peaks if column[-1] == "peak_value"]
    np.testing.assert_allclose(peaks[value_columns].to_numpy(), [[4, 2], [6, 3]])
    target = reporting.export_report_package(samples, tmp_path / "report", include_plots=False, series_vars=["accel"])
    workbook = load_workbook(target / "report.xlsx", read_only=True)
    try:
        assert "单位说明" in workbook.sheetnames
    finally:
        workbook.close()
    manifest = json.loads((target / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["result_states"][first.uid]["freqspec"]["status"] == "stale"


@pytest.mark.parametrize("rollback_fails", [False, True])
def test_report_publication_rollback_and_interruption(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, rollback_fails: bool
) -> None:
    """发布替换失败恢复旧报告；回滚失败留下明确中断标记。"""
    from dyntool.reporting import _report_commit
    from dyntool.infrastructure._storage_commit import _StorageConsistencyError

    samples = DefaultSampleSet([make_sample("report")])
    target = reporting.export_report_package(samples, tmp_path / "report", include_plots=False)
    old = (target / "report.xlsx").read_bytes()
    original = _report_commit.os.replace

    def replace(source: object, destination: object) -> None:
        source_path, destination_path = Path(source), Path(destination)
        if destination_path == target and (source_path.name.startswith(".dyntool-report-stage-") or rollback_fails):
            raise OSError("注入目录替换失败")
        original(source, destination)

    monkeypatch.setattr(_report_commit.os, "replace", replace)
    expected = _StorageConsistencyError if rollback_fails else OSError
    with pytest.raises(expected):
        reporting.export_report_package(samples, target, include_plots=False)
    if rollback_fails:
        assert list(tmp_path.glob(".dyntool-write-*.json"))
        assert list(tmp_path.glob(".dyntool-report-backup-*"))
    else:
        assert (target / "report.xlsx").read_bytes() == old
        assert not list(tmp_path.glob(".dyntool-write-*.json"))


def test_legacy_nested_structured_payload_is_validated() -> None:
    """旧零维对象数组载荷可恢复，重复的组合分量仍须一致。"""
    from dyntool import FreqSpec

    spectrum = make_sample("legacy").accel.calc_freqspec()
    payload = spectrum.to_structured_payload()
    for name in ("amp", "pha"):
        payload.data_vars[name] = np.asarray(payload.data_vars[name], dtype=object)
    restored = FreqSpec.from_structured_payload(payload)
    np.testing.assert_allclose(restored.amp.get_value(), spectrum.amp.get_value())
    from copy import deepcopy

    payload.meta["raw_dict"] = deepcopy(payload.meta["raw_dict"])
    raw = payload.meta["raw_dict"]["amp"]["amp"]
    payload.meta["raw_dict"]["amp"]["amp"] = raw + 10
    with pytest.raises(ValueError, match="不一致"):
        FreqSpec.from_structured_payload(payload)


def test_replaced_model_and_composite_components_have_independent_owners(tmp_path: Path) -> None:
    """已替换模型解除通知，组合构造不会共享可变的单位状态。"""
    from dyntool import FreqSpec

    samples, sample = make_store(tmp_path / "source")
    old = sample.accel
    sample.update(accel=AccelSeries.from_data([4, 5, 6], dt=0.01))
    samples.save_all(show_progress=False)
    old.convert_units({"value": "cm/s**2"})
    assert not samples.storage_dirty
    spectrum = sample.accel.calc_freqspec()
    composite = FreqSpec(amp=spectrum.amp, pha=spectrum.pha)
    spectrum.amp.convert_units({"amp": "cm/s**2"})
    assert composite.amp.value_unit != spectrum.amp.value_unit


def test_checkpoint_shares_arrays_and_isolates_unit_representation() -> None:
    """检查点共享不可变载荷，恢复及分支的表示状态相互独立。"""
    sample = make_sample("flow")
    flow = sample.accel.compute.flow().checkpoint("input")
    branch = flow.branch("analysis")
    assert np.shares_memory(flow.result().get_value(), branch.result().get_value())
    branch.result().convert_units({"value": "cm/s**2"})
    assert flow.result().get_value()[-1] == 3
    flow.result().convert_units({"value": "mm/s**2"})
    flow.restore("input")
    assert flow.result().get_value()[-1] == 3


def test_storage_precision_invalidates_only_persisted_dependency(tmp_path: Path) -> None:
    """存储舍入确实改变输入时，磁盘派生状态过期，内存原结果保持独立。"""
    sample = DefaultSample(
        metadata=Metadata(identity={"case": "precision"}),
        accel=AccelSeries.from_data([0.1234567, 0.9876543, 0.3333333], dt=0.01),
    )
    sample.compute.freqspec()
    samples = DefaultSampleSet([sample])
    samples.save(tmp_path / "rounded", storage_scheme=StorageScheme.SET_SQLITE_H5, data_options={"decimal_round": 3})
    loaded = DefaultSampleSet().load(
        tmp_path / "rounded", storage_scheme=StorageScheme.SET_SQLITE_H5, load_mode=SampleLoadMode.EAGER
    )
    assert loaded[sample.uid]._slot_state["freqspec"]["status"] == "stale"
    assert sample._slot_state["freqspec"]["status"] == "fresh"
    revision = loaded[sample.uid]._slot_state["accel"]["revision"]
    samples.save_all(show_progress=False)
    reopened = DefaultSampleSet().load(tmp_path / "rounded", storage_scheme=StorageScheme.SET_SQLITE_H5)
    assert reopened[sample.uid]._slot_state["accel"]["revision"] == revision


@pytest.mark.parametrize("scheme", list(StorageScheme))
def test_storage_precision_preserves_calculation_parameters(tmp_path: Path, scheme: StorageScheme) -> None:
    """精度选项只作用于数值载荷，保留真实参数且不误判未改变的输入版本。"""
    sample = DefaultSample(
        metadata=Metadata(identity={"case": "precision-parameters"}),
        accel=AccelSeries.from_data(np.zeros(64), dt=1.0),
    )
    cutoff = 0.123456789
    sample.update(accel=sample.accel.filter_lowpass(cutoff))
    sample.compute.freqspec()
    revision = sample._slot_state["accel"]["revision"]
    samples = DefaultSampleSet([sample])
    samples.save(tmp_path / "rounded", storage_scheme=scheme, data_options={"decimal_round": 3})
    context = samples.storage._sample_storage.strategy.ctx
    serialized = context.serialize_container(sample.accel)
    assert serialized["_dyntool"]["parameters"]["freq"] == cutoff
    assert serialized["_dyntool"]["history"][-1]["parameters"]["freq"] == cutoff
    loaded = DefaultSampleSet().load(tmp_path / "rounded", storage_scheme=scheme, load_mode=SampleLoadMode.EAGER)
    assert loaded[sample.uid]._slot_state["accel"]["revision"] == revision
    assert loaded[sample.uid]._slot_state["freqspec"]["status"] == "fresh"


def test_query_subset_computes_through_formal_namespace(tmp_path: Path) -> None:
    """通用子集通过 compute 计算，保持父集独立及旧方法的类型边界。"""
    samples, sample = make_store(tmp_path / "source")
    view = samples.find()
    result = view.compute.freqspec()
    assert result.stats.succeeded == 1
    assert view[sample.uid].freqspec is not None and sample.freqspec is None
    assert result.stats.total == len(view) == 1
    with pytest.raises(TypeError, match="calc_freqspec"):
        view.calc_freqspec()


def test_report_marker_failure_restores_old_version(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """报告发布后标记收尾失败也恢复旧版本，保留未完成标记。"""
    from dyntool.reporting import _report_commit
    from dyntool.infrastructure._storage_commit import _StorageConsistencyError

    samples = DefaultSampleSet([make_sample("report")])
    target = reporting.export_report_package(samples, tmp_path / "report", include_plots=False)
    old = (target / "report.xlsx").read_bytes()
    original = _report_commit._WriteMarker.finish

    def finish(marker: object) -> None:
        if Path(marker.path).parent == target.parent:
            raise OSError("注入报告标记清理失败")
        original(marker)

    monkeypatch.setattr(_report_commit._WriteMarker, "finish", finish)
    with pytest.raises(_StorageConsistencyError, match="中断标记"):
        reporting.export_report_package(samples, target, include_plots=False)
    assert (target / "report.xlsx").read_bytes() == old
    assert list(tmp_path.glob(".dyntool-write-*.json"))


def test_series_export_tracks_each_member_unit_and_missing_first() -> None:
    """同类频谱可来自不同物理量，缺失首个成员也不丢失轴单位。"""
    from dyntool import VelSeries
    from dyntool.reporting._frame_builders import _ReportFrames

    absent = DefaultSample(metadata=Metadata(identity={"case": "absent"}))
    acceleration = make_sample("acceleration")
    velocity = make_sample("velocity")
    acceleration.update(freqspec=acceleration.accel.calc_freqspec())
    velocity.update(freqspec=VelSeries.from_data([100, 200, 300], dt=0.01, data_unit="cm/s").calc_freqspec())
    frame = _ReportFrames.series(DefaultSampleSet([absent, acceleration, velocity]), "freqspec", strict=False)
    assert frame.attrs["index_unit"] is not None
    amp_units = {column[0]: unit for column, unit in frame.attrs["column_units"].items() if column[-1] == "amp"}
    assert amp_units[acceleration.uid] == "meter / second ** 2"
    assert amp_units[velocity.uid] == "meter / second"
