"""核心库后续整改回归；所有损坏注入只针对临时合成仓库。"""

from pathlib import Path
import json
import sqlite3

import h5py
import numpy as np
import pytest
from copy import deepcopy

from dyntool import (
    AccelSeries,
    DefaultSample,
    DefaultSampleSet,
    Metadata,
    VelSeries,
    OTOVLEval,
    ZVLEval,
    FPVDVEval,
    FDMVLEval,
    TransferFunctionAnalyzer,
    FreqSpec,
    FreqAmpSeries,
    FreqPhaSeries,
    RespSpec,
    SpecAccelSeries,
    SpecVelSeries,
)
from dyntool import storage
from dyntool.compute import ComputeContext, ComputeFlow
from dyntool import FPVDVLimit, FPVDVLimitStandard


def sample(name="review"):
    """创建固定的合成样本。"""
    return DefaultSample(metadata=Metadata(identity={"case": name}), accel=AccelSeries.from_data(np.ones(256), dt=0.01))


def test_immediate_dependency_invalidated():
    """位移通过当前速度求得，替换速度必须使其过期。"""
    current = sample()
    current.update(vel=current.accel.calc_vel())
    current.update(disp=current.vel.calc_disp())
    current.update(vel=VelSeries.from_data(np.zeros(256), dt=0.01))
    assert current._slot_state["disp"]["status"] == "stale"


def test_transfer_phase_matches_independent_dft():
    """输出相位比输入超前 45 度，输出/输入的增益相位应为正 45 度。"""
    times = np.arange(4096) / 256
    x = np.sin(2 * np.pi * 32 * times)
    y = 2 * np.sin(2 * np.pi * 32 * times + np.pi / 4)
    result = TransferFunctionAnalyzer(x, y, fs=256, nperseg=512, noverlap=256, nfft=512).solve()
    index = np.argmin(abs(result.frequencies - 32))
    reference = np.fft.rfft(y)[512] / np.fft.rfft(x)[512]
    assert np.angle(result.transfer_function[index]) == pytest.approx(np.angle(reference), abs=1e-4)


def test_transfer_preserves_fractional_sampling_rate():
    """从模型推导采样率不得取整，频率轴应保持真实的 Hz。"""
    x = AccelSeries.from_data(np.random.default_rng(20261004).normal(size=2048), dt=1 / 100.4)
    analyzer = TransferFunctionAnalyzer.from_models(x, x)
    assert analyzer.fs == pytest.approx(100.4)


def test_transfer_rejects_different_fractional_sampling_rates():
    """两个不同采样率不能因取整落入同一个整数而通过。"""
    x = AccelSeries.from_data(np.ones(1024), dt=1 / 100.4)
    y = AccelSeries.from_data(np.ones(1024), dt=1 / 100.49)
    with pytest.raises(ValueError):
        TransferFunctionAnalyzer.from_models(x, y)


def test_transfer_rejects_multichannel():
    """单输入单输出边界不能展平并拼接不同通道。"""
    with pytest.raises(ValueError):
        TransferFunctionAnalyzer(np.ones((1024, 2)), np.ones((1024, 2)), fs=256)


@pytest.mark.parametrize("data", [{}, {"zvl": [50, 60], "aw": [1, 2]}])
def test_zvl_payload_rejects_missing_or_multiple_values(data):
    """评价标量不应补零或截断首项。"""
    with pytest.raises(ValueError):
        ZVLEval.from_dict(data)


def test_fpvdv_payload_rejects_missing_scalar():
    """剂量载荷已有加权时程时，缺失剂量仍不应伪造为零。"""
    with pytest.raises(ValueError):
        FPVDVEval.from_dict({"aw_time": [0, 1], "aw_value": [1, 1]})


def test_fdmvl_payload_rejects_missing_scalar():
    """已有频带曲线时，缺失最大振级不应默认为零。"""
    with pytest.raises(ValueError):
        FDMVLEval.from_dict({"freq": [4, 8], "fdvls": [40, 50]})


def test_xarray_preserves_evaluation_units():
    """评价 Dataset 的字段属性已声明非 SI 单位，重开须保持物理量。"""
    original = OTOVLEval.from_data(freq=np.array([1.0, 2.0]), comps=np.array([[30.0, 31.0], [40.0, 41.0]]))
    original.convert_units({"freq": "kilohertz"})
    recovered = OTOVLEval.from_xarray(original.to_xarray())
    np.testing.assert_allclose(recovered.get_axis(unit="hertz"), original.get_axis(unit="hertz"))


def test_xarray_preserves_known_result_provenance():
    """模型自身快照往返不应丢弃已有计算依据。"""
    velocity = sample().accel.calc_vel()
    recovered = VelSeries.from_xarray(velocity.to_xarray())
    assert recovered.to_dict()["_dyntool"] == velocity.to_dict()["_dyntool"]


@pytest.mark.parametrize("scheme", [storage.StorageScheme.SAMPLE_H5, storage.StorageScheme.SET_H5])
def test_deep_inspection_detects_missing_value(tmp_path: Path, scheme):
    """深度检查不能把无法加载的缺值载荷判为完整。"""
    current = sample(str(scheme))
    target = tmp_path / "repository"
    DefaultSampleSet([current]).save(target, storage_scheme=scheme)
    payload_file = next(target.rglob("*.h5"))
    with h5py.File(payload_file, "r+") as handle:
        root = handle if scheme is storage.StorageScheme.SAMPLE_H5 else handle[current.uid]
        del root["accel"]["value"]
    before = payload_file.read_bytes()
    report = storage.inspect_storage_repository(target, storage_scheme=scheme, level="deep")
    assert payload_file.read_bytes() == before
    with pytest.raises(Exception):
        DefaultSampleSet().load(target, storage_scheme=scheme, load_mode=storage.SampleLoadMode.EAGER)
    assert not report.is_valid


def test_sample_flow_branch_retains_explicit_commit():
    """样本计算流的分支显式提交不应悄悄失去提交回调。"""
    current = sample("branch")
    branch = current.compute.flow(source="accel").branch("analysis")
    branch.set_result(AccelSeries.from_data(np.zeros(256), dt=0.01))
    result = branch.commit(replace=True)
    assert result is current


def test_deep_inspection_detects_duplicate_provenance_basis_conflict(tmp_path: Path):
    """状态允许因部分保存过期，但同版本的实际计算参数不应存在矛盾。"""
    current = sample("trace-conflict")
    current.compute.freqspec()
    target = tmp_path / "repository"
    DefaultSampleSet([current]).save(target, storage_scheme=storage.StorageScheme.SET_SQLITE_H5)
    with sqlite3.connect(target / "index.sqlite") as conn:
        metadata = json.loads(conn.execute("SELECT metadata_json FROM sample").fetchone()[0])
        state = metadata["_dyntool_state"]
        state["freqspec"]["parameters"]["review_fake_parameter"] = 123
        conn.execute("UPDATE sample SET metadata_json = ?", (json.dumps(metadata),))
        conn.execute(
            "UPDATE sample_summary_projection SET value_text = ? WHERE key = '_dyntool_state'", (json.dumps(state),)
        )
    before = {path: path.read_bytes() for path in target.iterdir() if path.is_file()}
    report = storage.inspect_storage_repository(target, level="deep")
    assert {path: path.read_bytes() for path in before} == before
    assert not report.is_valid


def test_control_transfer_known_gain():
    """独立常增益对照保证传递函数例子本身有效。"""
    values = np.random.default_rng(20261004).normal(size=2048)
    result = TransferFunctionAnalyzer(values, values * 2, fs=256).solve()
    np.testing.assert_allclose(abs(result.transfer_function), 2, atol=1e-12)


@pytest.mark.parametrize("scheme", [storage.StorageScheme.SAMPLE_H5, storage.StorageScheme.SET_H5])
def test_control_deep_undamaged_repository(tmp_path: Path, scheme):
    """完好仓库的 deep 与真实加载均有效。"""
    current = sample(str(scheme))
    target = tmp_path / "repository"
    DefaultSampleSet([current]).save(target, storage_scheme=scheme)
    assert storage.inspect_storage_repository(target, storage_scheme=scheme, level="deep").is_valid
    recovered = DefaultSampleSet().load(target, storage_scheme=scheme, load_mode=storage.SampleLoadMode.EAGER)
    np.testing.assert_array_equal(recovered[current.uid].accel.get_value(), current.accel.get_value())


def test_control_xarray_si_units():
    """默认 SI 往返对照，确认问题只在已有非 SI 字段单位被丢弃时出现。"""
    original = OTOVLEval.from_data(freq=np.array([1.0, 2.0]), comps=np.array([[30.0, 31.0], [40.0, 41.0]]))
    recovered = OTOVLEval.from_xarray(original.to_xarray())
    np.testing.assert_allclose(recovered.get_axis(unit="hertz"), original.get_axis(unit="hertz"))


def test_composite_frequency_requires_same_physical_axis():
    """不同频率的幅值和相位不得按数组位置组成同一个频点。"""
    amp = FreqAmpSeries.from_data([1, 2], [1, 2])
    pha = FreqPhaSeries.from_data([10, 20], [0.1, 0.2])
    with pytest.raises(ValueError):
        FreqSpec.from_series(amp=amp, pha=pha)


def test_composite_response_requires_same_physical_axis():
    """不同周期的加速度谱和速度谱不得按数组位置误对齐。"""
    sa = SpecAccelSeries.from_data([0.1, 0.2], [1, 2])
    sv = SpecVelSeries.from_data([1, 2], [0.5, 0.8])
    with pytest.raises(ValueError):
        RespSpec(sa=sa, sv=sv)


def test_control_composite_equivalent_axis_units():
    """同一物理轴的 Hz/kHz 表示仍是有效组合，不要求标签字符串相同。"""
    amp = FreqAmpSeries.from_data([1, 2], [1, 2], units={"freq": "hertz"})
    pha = FreqPhaSeries.from_data([0.001, 0.002], [0.1, 0.2], units={"freq": "kilohertz"})
    spectrum = FreqSpec.from_series(amp=amp, pha=pha)
    np.testing.assert_allclose(spectrum.amp.get_axis(unit="hertz"), spectrum.pha.get_axis(unit="hertz"))


@pytest.mark.parametrize("phase", [-np.pi / 4, np.pi / 4, -np.pi / 2])
def test_transfer_lead_lag_matches_dft(phase: float) -> None:
    """解析正弦与独立 DFT 同时验证增益及相位方向。"""
    t = np.arange(4096) / 256
    x, y = np.sin(2 * np.pi * 32 * t), 2 * np.sin(2 * np.pi * 32 * t + phase)
    result = TransferFunctionAnalyzer(x, y, fs=256, nperseg=512, noverlap=256, nfft=512).solve()
    reference = np.fft.rfft(y)[512] / np.fft.rfft(x)[512]
    np.testing.assert_allclose(result.transfer_function[64], reference, atol=1e-10)


def test_transfer_explicit_fs_validates_models_and_zero() -> None:
    """显式频率只覆盖分析轴，不掩盖不同采样率；零值不得回退。"""
    x = AccelSeries.from_data(np.ones(1024), dt=1 / 100.4)
    y = AccelSeries.from_data(np.ones(1024), dt=1 / 100.49)
    with pytest.raises(ValueError, match="采样频率"):
        TransferFunctionAnalyzer.from_models(x, y, fs=256)
    with pytest.raises(ValueError, match="正数"):
        TransferFunctionAnalyzer.from_models(x, x, fs=0)
    assert TransferFunctionAnalyzer.from_models(x, x, fs=256.5).fs == 256.5


@pytest.mark.parametrize(
    "model,field,extra",
    [
        (ZVLEval, "zvl", {"aw": 1}),
        (ZVLEval, "aw", {"zvl": 50}),
        (FPVDVEval, "fpvdv", {"aw_time": [0, 1], "aw_value": [1, 1]}),
        (FDMVLEval, "fdmvl", {"freq": [4, 8], "fdvls": [40, 50]}),
    ],
)
@pytest.mark.parametrize("value", [None, [], [1, 2]])
def test_evaluation_invalid_scalar(model, field, extra, value) -> None:
    """四个必需标量均拒绝空值或多个值。"""
    with pytest.raises(ValueError):
        model.from_dict({**extra, field: value})


@pytest.mark.parametrize("value", [2.0, np.array(2.0), [2.0]])
def test_evaluation_single_scalar_forms(value) -> None:
    """合法标量、零维数组和单元素数组均可恢复。"""
    result = ZVLEval.from_dict({"zvl": value, "aw": value})
    assert result.get_field("zvl").item() == 2


def test_dependency_order_self_update_and_all_matching_slots() -> None:
    """直接输入与全部已知祖先不依赖槽位顺序，自更新保留历史而无自循环。"""
    current = sample()
    current.update(vel=current.accel.calc_vel())
    current._slot_state = dict(reversed(list(current._slot_state.items())))
    current.update(disp=current.vel.calc_disp())
    assert set(current._slot_state["disp"]["inputs"]) == {"accel", "vel"}
    old = current._slot_state["accel"]["revision"]
    current.update(accel=current.accel.truncate(0, 1))
    assert current._slot_state["accel"]["historical_inputs"] == {"accel": old}
    assert "accel" not in current._slot_state["accel"].get("inputs", {})
    assert current._slot_state["vel"]["status"] == "stale"
    assert current._slot_state["disp"]["status"] == "stale"


def test_branch_preview_nested_context_and_snapshot() -> None:
    """嵌套分支隔离可变上下文，预览不更新样本，显式提交不改变主流。"""
    current = sample()
    flow = current.compute.flow(source="accel")
    flow.context = ComputeContext(extras={"nested": {"value": 1}})
    branch = flow.branch("first").branch("second")
    branch.context.extras["nested"]["value"] = 2
    branch.set_result(AccelSeries.from_data(np.zeros(256), dt=0.01))
    assert branch.commit(replace=False) is branch.result()
    assert current.accel.get_value()[0] == 1
    assert branch.commit() is current
    assert current.accel.get_value()[0] == 0
    assert flow.result().get_value()[0] == 1
    assert flow.context.extras["nested"]["value"] == 1
    assert ComputeFlow(_result={"value": 1}).branch("plain").commit() == {"value": 1}


def test_branch_commit_failure_rolls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    """受控写回中断后恢复原槽位、追溯和脏状态，分支结果仍可重试。"""
    current = sample()
    flow = current.compute.flow().branch("failure")
    flow.set_result(AccelSeries.from_data(np.zeros(256), dt=0.01))
    states, dirty = deepcopy(current._slot_state), set(current._dirty_categories)
    original = DefaultSample.set_data_var

    def fail(self, name, value):
        original(self, name, value)
        raise ValueError("注入提交回调失败")

    monkeypatch.setattr(DefaultSample, "set_data_var", fail)
    with pytest.raises(ValueError, match="注入"):
        flow.commit()
    assert current._slot_state == states
    assert current._dirty_categories == dirty
    assert current.accel.get_value()[0] == 1
    monkeypatch.undo()
    assert flow.commit() is current


@pytest.mark.parametrize("kind", ["velocity", "freqspec", "respspec", "zvl", "otovl", "fpvdv", "fdmvl"])
def test_xarray_complete_model_roundtrip(kind: str) -> None:
    """简单、复合及评价快照完整保持形状、物理单位和已有追溯。"""
    current = sample()
    models = {
        "velocity": current.accel.calc_vel(),
        "freqspec": current.accel.calc_freqspec(),
        "respspec": RespSpec.from_data([0.1, 0.2], sa=[1, 2], sv=[3, 4]),
        "zvl": ZVLEval.from_data(zvl=50, aw=1),
        "otovl": OTOVLEval.from_data(freq=[1, 2], comps=[[30, 31], [40, 41]]),
        "fpvdv": FPVDVEval.from_data(fpvdv=1, aw_time=[0, 1], aw_value=[1, 1]),
        "fdmvl": FDMVLEval.from_data(fdmvl=50, freq=[4, 8], fdvls=[40, 50]),
    }
    model = models[kind]
    snapshot = model.to_xarray()
    recovered = type(model).from_xarray(snapshot)
    from dyntool.domain.models._model_payload import _ModelPayloadCodec

    assert _ModelPayloadCodec.equal(model.to_dict(), recovered.to_dict(), compare_provenance=True)
    snapshot.attrs["_dyntool"]["status"] = "stale"
    assert model._provenance == recovered._provenance


@pytest.mark.parametrize("declaration", ["_units", "_current_units", "explicit"])
def test_xarray_unit_conflict_rejected(declaration: str) -> None:
    """字段与任一重复单位声明的尺度冲突不能静默覆盖。"""
    model = AccelSeries.from_data([1, 2], dt=0.01)
    snapshot = model.to_xarray()
    explicit = None
    if declaration == "explicit":
        explicit = {"value": "cm/s**2"}
    else:
        snapshot.attrs[declaration] = {"value": "cm/s**2"}
    with pytest.raises(ValueError, match="不一致"):
        AccelSeries.from_xarray(snapshot, units=explicit)


def test_xarray_external_without_trace_is_unknown() -> None:
    """外部修改删除原依据后恢复为未知，二维通道形状保持。"""
    model = AccelSeries.from_data(np.ones((16, 2)), dt=0.01)
    snapshot = model.to_xarray()
    snapshot.attrs.pop("_dyntool")
    snapshot.values[:] = 3
    result = AccelSeries.from_xarray(snapshot)
    assert result.get_value().shape == (16, 2)
    assert result._provenance["status"] == "unknown"
    assert model.get_value()[0, 0] == 1


@pytest.mark.parametrize("scheme", list(storage.StorageScheme))
def test_dependency_partial_save_reopen_and_deep(tmp_path: Path, scheme: storage.StorageScheme) -> None:
    """六策略保留合法未更新载荷，同时恢复派生结果过期状态。"""
    current = sample(str(scheme))
    current.update(vel=current.accel.calc_vel())
    current.update(disp=current.vel.calc_disp())
    source = DefaultSampleSet([current])
    target = tmp_path / "repository"
    source.save(target, storage_scheme=scheme)
    current.update(vel=VelSeries.from_data(np.zeros(256), dt=0.01))
    source.save(target, storage_scheme=scheme, categories=["vel"])
    report = storage.inspect_storage_repository(target, storage_scheme=scheme, level="deep")
    assert report.is_valid, report.issues
    reopened = DefaultSampleSet().load(target, storage_scheme=scheme, load_mode=storage.SampleLoadMode.EAGER)
    assert reopened[current.uid]._slot_state["disp"]["status"] == "stale"


def test_quick_never_reads_arrays(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """quick 保持廉价结构检查，不反序列化数组。"""
    target = tmp_path / "repository"
    DefaultSampleSet([sample()]).save(target, storage_scheme=storage.StorageScheme.SET_SQLITE_H5)

    def fail(*args, **kwargs):
        raise AssertionError("quick 不得读取数组")

    monkeypatch.setattr(h5py.Dataset, "__getitem__", fail)
    assert storage.inspect_storage_repository(target, level="quick").is_valid


@pytest.mark.parametrize("scheme", list(storage.StorageScheme))
def test_deep_detects_unrecoverable_payload_across_schemes(tmp_path: Path, scheme: storage.StorageScheme) -> None:
    """六策略缺失必需值均被定位，检查不改写任何源文件。"""
    current = sample(str(scheme))
    target = tmp_path / "repository"
    DefaultSampleSet([current]).save(target, storage_scheme=scheme)
    if scheme is storage.StorageScheme.SAMPLE_JSON:
        path = next(target.glob("*.json"))
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["data"]["accel"].pop("value")
        path.write_text(json.dumps(payload), encoding="utf-8")
    elif scheme in {storage.StorageScheme.SAMPLE_H5, storage.StorageScheme.SET_H5, storage.StorageScheme.SET_SQLITE_H5}:
        path = next(target.glob("*.h5"))
        with h5py.File(path, "r+") as handle:
            if scheme is storage.StorageScheme.SET_SQLITE_H5:
                with sqlite3.connect(target / "index.sqlite") as connection:
                    group = connection.execute(
                        "SELECT h5_path FROM sample_slot_presence WHERE slot_name='accel'"
                    ).fetchone()[0]
                del handle[group]["value"]
            else:
                root = handle if scheme is storage.StorageScheme.SAMPLE_H5 else handle[current.uid]
                del root["accel"]["value"]
    elif scheme is storage.StorageScheme.SET_DIR:
        path = next(target.rglob("data.npz"))
        with np.load(path, allow_pickle=True) as archive:
            payload = archive["accel"].item()
        payload.pop("value")
        np.savez_compressed(path, accel=payload)
    else:
        import pandas as pd

        path = next((target / "accel").glob("*.csv"))
        frame = pd.read_csv(path)
        frame.iloc[:, :1].to_csv(path, index=False)
    before = {path: path.read_bytes() for path in target.rglob("*") if path.is_file()}
    report = storage.inspect_storage_repository(target, storage_scheme=scheme, level="deep")
    assert not report.is_valid
    assert any("accel" in issue for issue in report.issues)
    assert {path: path.read_bytes() for path in before} == before


@pytest.mark.parametrize("key", ["operation", "inputs", "algorithm", "input_units", "history"])
def test_deep_rejects_other_provenance_conflicts(tmp_path: Path, key: str) -> None:
    """同版本操作、输入、单位和历史冲突不能靠同步摘要隐藏。"""
    current = sample()
    current.compute.freqspec()
    target = tmp_path / "repository"
    DefaultSampleSet([current]).save(target, storage_scheme=storage.StorageScheme.SET_SQLITE_H5)
    with sqlite3.connect(target / "index.sqlite") as connection:
        metadata = json.loads(connection.execute("SELECT metadata_json FROM sample").fetchone()[0])
        record = metadata["_dyntool_state"]["freqspec"]
        if key in {"operation", "algorithm"}:
            record[key] += "_changed"
        elif key == "history":
            record[key][-1]["parameters"]["changed"] = True
        else:
            record[key]["changed"] = "fake_revision" if key == "inputs" else "centimeter / second ** 2"
        connection.execute("UPDATE sample SET metadata_json=?", (json.dumps(metadata),))
        connection.execute(
            "UPDATE sample_summary_projection SET value_text=? WHERE key='_dyntool_state'",
            (json.dumps(metadata["_dyntool_state"]),),
        )
    report = storage.inspect_storage_repository(target, level="deep")
    assert not report.is_valid
    assert any("计算依据" in issue for issue in report.issues)


def test_deep_summary_query_is_batched(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """多样本多槽位的完整摘要只扫描一次。"""
    target = tmp_path / "repository"
    members = [sample(str(index)) for index in range(3)]
    for current in members:
        current.compute.freqspec()
    DefaultSampleSet(members).save(target, storage_scheme=storage.StorageScheme.SET_SQLITE_H5)
    queries = []
    connect = sqlite3.connect

    def counted(*args, **kwargs):
        connection = connect(*args, **kwargs)
        connection.set_trace_callback(queries.append)
        return connection

    monkeypatch.setattr(sqlite3, "connect", counted)
    assert storage.inspect_storage_repository(target, level="deep").is_valid
    assert len([query for query in queries if query.startswith("SELECT") and "sample_summary_projection" in query]) == 1


def test_branch_readonly_view_can_compute_but_cannot_save_source(tmp_path: Path) -> None:
    """只读视图允许分支内存提交，源写入仍拒绝，另存不影响源仓库。"""
    target = tmp_path / "source"
    current = sample()
    source = DefaultSampleSet([current])
    source.save(target, storage_scheme=storage.StorageScheme.SET_SQLITE_H5)
    before = {path: path.read_bytes() for path in target.iterdir() if path.is_file()}
    view = source.find(uids=[current.uid])
    selected = view[current.uid]
    selected.compute.flow().branch("preview").set_result(AccelSeries.from_data(np.zeros(256), dt=0.01)).commit()
    assert current.accel.get_value()[0] == 1
    with pytest.raises(PermissionError):
        view.save_all(show_progress=False)
    view.save(tmp_path / "export", storage_scheme=storage.StorageScheme.SET_SQLITE_H5)
    assert {path: path.read_bytes() for path in before} == before


@pytest.mark.parametrize("kind", ["freqspec", "respspec", "fpvdv", "fdmvl"])
def test_non_si_xarray_composite_and_evaluation(kind: str) -> None:
    """非 SI 复合及评价快照保留各分量物理表示和根依据。"""
    models = {
        "freqspec": FreqSpec.from_data([1, 2], amp=[1, 2], pha=[0.1, 0.2]).convert_units(
            {"freq": "kHz", "phase": "degree"}, replace=False
        ),
        "respspec": RespSpec.from_data([0.1, 0.2], sa=[1, 2], sv=[3, 4]).convert_units(
            {"period": "millisecond", "sa": "g_0", "sv": "cm/s"}, replace=False
        ),
        "fpvdv": FPVDVEval.from_data(fpvdv=1, aw_time=[0, 1], aw_value=[1, 1]).convert_units(
            {"aw_time": "millisecond", "aw_value": "cm/s**2"}, replace=False
        ),
        "fdmvl": FDMVLEval.from_data(fdmvl=50, freq=[4, 8], fdvls=[40, 50]).convert_units(
            {"freq": "kHz"}, replace=False
        ),
    }
    model = models[kind]
    result = type(model).from_xarray(model.to_xarray())
    from dyntool.domain.models._model_payload import _ModelPayloadCodec

    assert _ModelPayloadCodec.equal(model.to_dict(), result.to_dict(), compare_provenance=True)


def test_xarray_restore_propagates_original_type_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """恢复实现自身的 TypeError 不应触发第二次调用或被误报为参数不支持。"""
    snapshot = sample().accel.to_xarray()
    calls = []

    def fail(cls, payload, *, units=None):
        calls.append(payload)
        raise TypeError("注入恢复实现错误")

    monkeypatch.setattr(AccelSeries, "from_dict", classmethod(fail))
    with pytest.raises(TypeError, match="注入恢复实现错误"):
        AccelSeries.from_xarray(snapshot)
    assert len(calls) == 1


@pytest.mark.parametrize("damage", ["shape", "unit", "type"])
def test_deep_detects_shape_unit_and_unknown_type(tmp_path: Path, damage: str) -> None:
    """deep 定位形状、单位和未知类型；所有检查保持只读。"""
    current = sample()
    target = tmp_path / "repository"
    DefaultSampleSet([current]).save(target, storage_scheme=storage.StorageScheme.SET_SQLITE_H5)
    with sqlite3.connect(target / "index.sqlite") as connection:
        group = connection.execute("SELECT h5_path FROM sample_slot_presence WHERE slot_name='accel'").fetchone()[0]
        if damage == "type":
            connection.execute("UPDATE sample_slot_presence SET model_type='UnknownModel'")
    if damage != "type":
        with h5py.File(target / "payload.h5", "r+") as handle:
            if damage == "shape":
                del handle[group]["value"]
                handle[group].create_dataset("value", data=np.zeros(16))
            else:
                handle[group]["value"].attrs["unit"] = "bad_unit_review"
    before = {path: path.read_bytes() for path in target.iterdir() if path.is_file()}
    report = storage.inspect_storage_repository(target, level="deep")
    assert not report.is_valid
    assert any("accel" in issue for issue in report.issues)
    assert {path: path.read_bytes() for path in before} == before


@pytest.mark.parametrize("declaration", ["_units", "_current_units", "explicit"])
def test_limit_xarray_uses_shared_unit_contract(declaration: str) -> None:
    """限值恢复同样拒绝所有重复单位尺度冲突，不能覆盖字段单位。"""
    model = FPVDVLimit.from_standard(FPVDVLimitStandard.GB_50868_2013, scene="居住建筑夜间")
    snapshot = model.to_xarray()
    explicit = None
    incompatible = {"fpvdv": "centimeter / second ** 1.75"}
    if declaration == "explicit":
        explicit = incompatible
    else:
        snapshot.attrs[declaration] = incompatible
    with pytest.raises(ValueError, match="不一致"):
        FPVDVLimit.from_xarray(snapshot, units=explicit)


@pytest.mark.parametrize("axis_key", ["distance", "period"])
def test_custom_model_automatic_xarray_export_preserved(axis_key: str) -> None:
    """保留已有无 xr 属性的扩展自动导出，矩阵不能被展平。"""
    from dyntool.domain.models.base import DataModelBase

    class CustomModel(DataModelBase):
        """用于交换验证的临时扩展。"""

        category = "review_xarray_extension"
        axis_field = axis_key
        value_field = "value"

        def __init__(self, data):
            self._payload = data

        def current_units(self):
            """返回扩展的字段单位。"""
            return {axis_key: "meter" if axis_key == "distance" else "second", "value": "dimensionless"}

        def to_dict(self):
            """导出矩阵与独立标量。"""
            return {**self._payload, "_units": self.current_units()}

        @classmethod
        def from_dict(cls, data, *, units=None):
            """恢复已有权威字段。"""
            return cls({key: data[key] for key in (axis_key, "value", "label")})

    try:
        original = CustomModel({axis_key: np.arange(3), "value": np.ones((3, 2)), "label": np.array(5)})
        snapshot = original.to_xarray()
        assert snapshot["value"].shape == (3, 2)
        assert snapshot["label"].shape == ()
        recovered = CustomModel.from_xarray(snapshot)
        np.testing.assert_array_equal(recovered.to_dict()["value"], original.to_dict()["value"])
        assert recovered._provenance == original._provenance
    finally:
        DataModelBase._registry.pop("review_xarray_extension")


def test_response_dataset_axis_alias_checks_units() -> None:
    """响应谱 Dataset 的 T 坐标按声明映射到 period 并校验重复单位。"""
    model = SpecAccelSeries.from_data([0.1, 0.2], [1, 2]).convert_units({"period": "millisecond"}, replace=False)
    snapshot = model.to_xarray().to_dataset(name="value")
    result = SpecAccelSeries.from_xarray(snapshot)
    np.testing.assert_allclose(result.get_axis(unit="second"), model.get_axis(unit="second"))
    with pytest.raises(ValueError, match="不一致"):
        SpecAccelSeries.from_xarray(snapshot, units={"period": "second"})


def test_shared_revision_records_every_source_slot() -> None:
    """多个输入槽位引用同一不可变版本时，替换任一槽位都使结果过期。"""
    from types import SimpleNamespace
    from dyntool.domain._provenance import _SampleResultState

    source = sample().accel
    result = source.calc_vel()
    owner = SimpleNamespace(
        _slot_state={"primary": deepcopy(source._provenance), "backup": deepcopy(source._provenance)},
        _data_map={"velocity": result},
        _resolve_field=lambda name: name,
    )
    state = _SampleResultState(owner)
    state.updated("velocity", result)
    assert set(owner._slot_state["velocity"]["inputs"]) == {"primary", "backup"}
    state.updated("primary", AccelSeries.from_data(np.zeros(256), dt=0.01))
    assert owner._slot_state["velocity"]["status"] == "stale"
