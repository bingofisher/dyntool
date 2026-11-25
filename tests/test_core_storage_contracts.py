"""核心存储更新与故障恢复合同，所有故障仅注入临时仓库。"""

from pathlib import Path
import sqlite3

import numpy as np
import pytest

from dyntool import AccelSeries, DefaultSample, DefaultSampleSet, Metadata, VelSeries
from dyntool.storage import SampleLoadMode, StorageMode, StorageScheme, inspect_storage_repository


def build_store(path: Path, scheme: StorageScheme) -> tuple[DefaultSampleSet, DefaultSample]:
    """构造具有两个独立槽位的最小临时仓库。"""
    sample = DefaultSample(
        metadata=Metadata(extra={"case": "atomic"}),
        accel=AccelSeries.from_data([1, 2, 3], dt=0.01),
        vel=VelSeries.from_data([4, 5, 6], dt=0.01),
    )
    samples = DefaultSampleSet({sample.uid: sample})
    samples.connect_storage(path, mode=StorageMode.CREATE, storage_scheme=scheme)
    samples.storage.save_all(show_progress=False)
    return samples, sample


@pytest.mark.parametrize("scheme", list(StorageScheme))
def test_partial_save_preserves_unselected_and_empty_slots(tmp_path: Path, scheme: StorageScheme) -> None:
    """已存在目标合并非空选择，空选择与空槽位均不删除磁盘数据。"""
    samples, sample = build_store(tmp_path / scheme.value, scheme)
    sample.update(accel=AccelSeries.from_data([7, 8, 9], dt=0.01), vel=None)
    samples.storage.save_all(categories=["accel"], show_progress=False)
    samples.storage.save_all(categories=["vel"], show_progress=False)
    sample.update(accel=AccelSeries.from_data([0, 0, 0], dt=0.01))
    samples.storage.save_all(categories=[], show_progress=False)
    loaded = DefaultSampleSet().load(tmp_path / scheme.value, storage_scheme=scheme, load_mode=SampleLoadMode.EAGER)
    np.testing.assert_array_equal(loaded[sample.uid].accel.get_value(), [7, 8, 9])
    np.testing.assert_array_equal(loaded[sample.uid].vel.get_value(), [4, 5, 6])


def test_sqlite_failure_keeps_old_payload_and_allows_retry(tmp_path: Path, monkeypatch) -> None:
    """摘要写失败后，重新打开得到完整旧版本，连接已释放且可重试。"""
    path = tmp_path / "store"
    samples, sample = build_store(path, StorageScheme.SET_SQLITE_H5)
    strategy = samples.storage._sample_storage.strategy
    old_payload = sample._storage_payload_id
    sample.update(accel=AccelSeries.from_data([7, 8, 9], dt=0.01))
    original = strategy._sync_summary_artifacts

    def fail(*args, **kwargs):
        raise ValueError("注入摘要写入失败")

    monkeypatch.setattr(strategy, "_sync_summary_artifacts", fail)
    errors = samples.storage.save_all(strict=False, show_progress=False)
    assert set(errors) == {sample.uid}
    assert sample._storage_payload_id == old_payload
    loaded = DefaultSampleSet().load(path, storage_scheme=StorageScheme.SET_SQLITE_H5, load_mode=SampleLoadMode.EAGER)
    np.testing.assert_array_equal(loaded[sample.uid].accel.get_value(), [1, 2, 3])
    assert not list(path.glob(".dyntool-write-*.json"))
    monkeypatch.setattr(strategy, "_sync_summary_artifacts", original)
    assert samples.storage.save_all(show_progress=False) == {}
    assert sample._storage_payload_id != old_payload


def test_future_schema_is_not_downgraded(tmp_path: Path) -> None:
    """未知新 schema 明确拒绝，保持原版本号。"""
    path = tmp_path / "store"
    build_store(path, StorageScheme.SET_SQLITE_H5)
    with sqlite3.connect(path / "index.sqlite") as conn:
        conn.execute("PRAGMA user_version = 99")
    with pytest.raises(ValueError, match="版本"):
        DefaultSampleSet().load(path, storage_scheme=StorageScheme.SET_SQLITE_H5)
    with sqlite3.connect(path / "index.sqlite") as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 99


@pytest.mark.parametrize("persist", [False, True])
def test_comparison_uses_physical_units(tmp_path: Path, persist: bool) -> None:
    """摘要快路径与内存路径采用同一物理量比较规则。"""
    metadata = Metadata(extra={"case": "compare"})
    left_sample = DefaultSample(metadata=metadata, accel=AccelSeries.from_data([1, 2, 3], dt=0.01, data_unit="m/s**2"))
    right_sample = DefaultSample(
        metadata=metadata.model_copy(deep=True),
        accel=AccelSeries.from_data([100, 200, 300], dt=0.01, data_unit="cm/s**2"),
    )
    left = DefaultSampleSet({left_sample.uid: left_sample})
    right = DefaultSampleSet({right_sample.uid: right_sample})
    if persist:
        left.save(tmp_path / "left", storage_scheme=StorageScheme.SET_SQLITE_H5)
        right.save(tmp_path / "right", storage_scheme=StorageScheme.SET_SQLITE_H5)
        left = DefaultSampleSet().load(tmp_path / "left", storage_scheme=StorageScheme.SET_SQLITE_H5)
        right = DefaultSampleSet().load(tmp_path / "right", storage_scheme=StorageScheme.SET_SQLITE_H5)
    assert left.compare_with(right, features=["pga"]).scalar_diff.empty


@pytest.mark.parametrize("scheme", list(StorageScheme))
def test_serialization_failure_preserves_metadata_and_payload(
    tmp_path: Path, monkeypatch, scheme: StorageScheme
) -> None:
    """序列化失败不发布新 metadata，不改变任何已有槽位。"""
    path = tmp_path / "store"
    samples, sample = build_store(path, scheme)
    old_alias = sample.alias
    sample.set_alias("待提交的新名称")
    context = samples.storage._sample_storage.ctx

    def fail(data):
        raise ValueError("注入序列化失败")

    monkeypatch.setattr(context, "serialize_container", fail)
    errors = samples.storage.save_all(strict=False, show_progress=False)
    assert sample.uid in errors
    loaded = DefaultSampleSet().load(path, storage_scheme=scheme, load_mode=SampleLoadMode.EAGER)
    assert loaded[sample.uid].alias == old_alias
    np.testing.assert_array_equal(loaded[sample.uid].accel.get_value(), [1, 2, 3])
    np.testing.assert_array_equal(loaded[sample.uid].vel.get_value(), [4, 5, 6])


@pytest.mark.parametrize("strict", [True, False])
@pytest.mark.parametrize("scheme", list(StorageScheme))
def test_batch_failure_retains_prior_commits(tmp_path: Path, monkeypatch, strict: bool, scheme: StorageScheme) -> None:
    """中间样本失败时前序成功保留；非严格模式继续第三个样本。"""
    path = tmp_path / "store"
    samples, first = build_store(path, scheme)
    second = DefaultSample(metadata=Metadata(extra={"index": 2}), accel=AccelSeries.from_data([2, 3, 4], dt=0.01))
    third = DefaultSample(metadata=Metadata(extra={"index": 3}), accel=AccelSeries.from_data([3, 4, 5], dt=0.01))
    samples[second.uid] = second
    samples[third.uid] = third
    first.update(accel=AccelSeries.from_data([7, 8, 9], dt=0.01))
    context = samples.storage._sample_storage.ctx
    serialize = context.serialize_container

    def fail_second(data):
        if data is second.accel:
            raise ValueError("中间样本失败")
        return serialize(data)

    monkeypatch.setattr(context, "serialize_container", fail_second)
    if strict:
        with pytest.raises(Exception, match="保存样本失败"):
            samples.save_all(strict=True, workers=3, show_progress=False)
    else:
        report = samples.save_all(strict=False, workers=1, show_progress=False)
        assert report.stats.failed == 1
        assert report.stats.succeeded == 2
    assert samples.storage_dirty
    loaded = DefaultSampleSet().load(path, storage_scheme=scheme, load_mode=SampleLoadMode.EAGER)
    np.testing.assert_array_equal(loaded[first.uid].accel.get_value(), [7, 8, 9])
    assert second.uid not in loaded
    assert (third.uid in loaded) is not strict


@pytest.mark.parametrize("scheme", [StorageScheme.SET_DIR, StorageScheme.SET_ATTR_TABLE])
def test_multifile_commit_rolls_back_replaced_files(tmp_path: Path, monkeypatch, scheme: StorageScheme) -> None:
    """第二个文件替换失败时恢复第一个文件，确保 metadata 与数据成对。"""
    from dyntool.infrastructure import _storage_commit

    path = tmp_path / "store"
    samples, sample = build_store(path, scheme)
    sample.update(accel=AccelSeries.from_data([7, 8, 9], dt=0.01))
    original = _storage_commit.os.replace
    count = 0

    def fail_once(source, target):
        nonlocal count
        count += 1
        if count == 2:
            raise OSError("注入文件替换失败")
        return original(source, target)

    monkeypatch.setattr(_storage_commit.os, "replace", fail_once)
    with pytest.raises(Exception):
        samples.storage.save_all(show_progress=False)
    loaded = DefaultSampleSet().load(path, storage_scheme=scheme, load_mode=SampleLoadMode.EAGER)
    np.testing.assert_array_equal(loaded[sample.uid].accel.get_value(), [1, 2, 3])
    assert not list(path.glob(".dyntool-write-*.json"))


def test_sqlite_commit_failure_is_retryable(tmp_path: Path, monkeypatch) -> None:
    """SQLite commit 失败发生在 H5 关闭后，回滚保留旧版本。"""
    path = tmp_path / "store"
    samples, sample = build_store(path, StorageScheme.SET_SQLITE_H5)
    strategy = samples.storage._sample_storage.strategy
    original = strategy._connect

    class FailingConnection:
        def __init__(self, connection):
            self.connection = connection

        def __getattr__(self, name):
            return getattr(self.connection, name)

        def commit(self):
            raise ValueError("注入 commit 失败")

    sample.update(accel=AccelSeries.from_data([7, 8, 9], dt=0.01))
    monkeypatch.setattr(strategy, "_connect", lambda **kwargs: FailingConnection(original(**kwargs)))
    errors = samples.storage.save_all(strict=False, show_progress=False)
    assert sample.uid in errors
    loaded = DefaultSampleSet().load(path, storage_scheme=StorageScheme.SET_SQLITE_H5, load_mode=SampleLoadMode.EAGER)
    np.testing.assert_array_equal(loaded[sample.uid].accel.get_value(), [1, 2, 3])
    monkeypatch.setattr(strategy, "_connect", original)
    assert samples.storage.save_all(show_progress=False) == {}


def test_progress_failure_occurs_after_durable_commit(tmp_path: Path) -> None:
    """进度回调失败不能撤销已经提交的样本。"""
    path = tmp_path / "store"
    samples, sample = build_store(path, StorageScheme.SET_SQLITE_H5)
    sample.update(accel=AccelSeries.from_data([7, 8, 9], dt=0.01))

    def fail_progress(completed: int, total: int) -> None:
        raise ValueError("注入回调失败")

    with pytest.raises(ValueError, match="回调"):
        samples.save_all(progress_callback=fail_progress, show_progress=False)
    loaded = DefaultSampleSet().load(path, storage_scheme=StorageScheme.SET_SQLITE_H5, load_mode=SampleLoadMode.EAGER)
    np.testing.assert_array_equal(loaded[sample.uid].accel.get_value(), [7, 8, 9])
    assert samples.last_operation_report.stats.succeeded == 1


@pytest.mark.parametrize("scheme", list(StorageScheme))
def test_interruption_marker_blocks_open_and_inspection_is_readonly(tmp_path: Path, scheme: StorageScheme) -> None:
    """遗留标记阻止普通读写，检查报告位置与原因且不修改文件。"""
    path = tmp_path / "store"
    build_store(path, scheme)
    marker = path / ".dyntool-write-interrupted.json"
    marker.write_text('{"operation":"注入中断"}', encoding="utf-8")
    before = {p: p.read_bytes() for p in path.rglob("*") if p.is_file()}
    for level in ["quick", "deep"]:
        report = inspect_storage_repository(path, storage_scheme=scheme, level=level)
        assert not report.is_valid
        assert any(str(marker) in issue and "注入中断" in issue for issue in report.issues)
    assert before == {p: p.read_bytes() for p in path.rglob("*") if p.is_file()}
    with pytest.raises(RuntimeError, match="标记"):
        DefaultSampleSet().load(path, storage_scheme=scheme)


def test_deep_inspection_detects_summary_split_without_mutation(tmp_path: Path) -> None:
    """深检查重算峰值，识别索引与 payload 摘要分裂。"""
    path = tmp_path / "store"
    build_store(path, StorageScheme.SET_SQLITE_H5)
    with sqlite3.connect(path / "index.sqlite") as conn:
        conn.execute("UPDATE sample_summary_projection SET value_real = 999 WHERE key = 'pga'")
    before = (path / "index.sqlite").read_bytes()
    report = inspect_storage_repository(path, level="deep")
    assert not report.is_valid
    assert any("摘要" in issue for issue in report.issues)
    assert (path / "index.sqlite").read_bytes() == before


@pytest.mark.parametrize("scheme", list(StorageScheme))
@pytest.mark.parametrize("module_api", [False, True])
def test_lazy_partial_copy_loads_only_selected_slots(tmp_path: Path, scheme: StorageScheme, module_api: bool) -> None:
    """复制到新目标只加载选中的懒槽位，不读取或写入其他槽位。"""
    source = tmp_path / "source"
    _, sample = build_store(source, scheme)
    loaded = DefaultSampleSet().load(source, storage_scheme=scheme)
    if module_api:
        from dyntool.storage import save_sample_set

        save_sample_set(loaded, tmp_path / "target", scheme=scheme, categories=["accel"])
    else:
        loaded.save(tmp_path / "target", storage_scheme=scheme, categories=["accel"])
    assert not loaded[sample.uid].is_loaded("vel")
    copied = DefaultSampleSet().load(tmp_path / "target", storage_scheme=scheme, load_mode=SampleLoadMode.EAGER)
    assert copied[sample.uid].accel is not None
    assert copied[sample.uid].vel is None


@pytest.mark.parametrize("scheme", list(StorageScheme))
def test_marker_cleanup_failure_reports_committed_sample(tmp_path: Path, monkeypatch, scheme: StorageScheme) -> None:
    """提交后的标记清理失败停止批次，但成功计数与磁盘新值一致。"""
    from dyntool.infrastructure._storage_commit import _WriteMarker, _StorageConsistencyError

    path = tmp_path / "store"
    samples, sample = build_store(path, scheme)
    sample.update(accel=AccelSeries.from_data([7, 8, 9], dt=0.01))

    def fail_cleanup(self):
        # 属性表模型文件有各自的暂存目录，只在仓库最终标记处注入故障。
        if self.path.parent == path:
            raise OSError("注入标记清理失败")
        self.path.unlink()

    monkeypatch.setattr(_WriteMarker, "finish", fail_cleanup)
    with pytest.raises(_StorageConsistencyError):
        samples.save_all(strict=False, workers=3, show_progress=False)
    assert samples.last_operation_report.stats.succeeded == 1
    assert samples.last_operation_report.stats.failed == 0
    assert list(path.glob(_WriteMarker.pattern))
    report = inspect_storage_repository(path, storage_scheme=scheme, level="deep")
    assert all("标记" in issue for issue in report.issues)


def test_set_h5_group_switch_failure_restores_previous_sample(tmp_path: Path, monkeypatch) -> None:
    """旧 group 已移走后发布失败，恢复旧 group 并释放句柄。"""
    import h5py

    path = tmp_path / "store"
    samples, sample = build_store(path, StorageScheme.SET_H5)
    sample.update(accel=AccelSeries.from_data([7, 8, 9], dt=0.01))
    original = h5py.Group.move

    def fail_publish(group, source, target):
        if source.startswith(".dyntool-stage-"):
            raise ValueError("注入 group 发布失败")
        return original(group, source, target)

    monkeypatch.setattr(h5py.Group, "move", fail_publish)
    assert sample.uid in samples.storage.save_all(strict=False, show_progress=False)
    loaded = DefaultSampleSet().load(path, load_mode=SampleLoadMode.EAGER)
    np.testing.assert_array_equal(loaded[sample.uid].accel.get_value(), [1, 2, 3])
    assert not list(path.glob(".dyntool-write-*.json"))


def test_summary_comparison_does_not_read_arrays(tmp_path: Path, monkeypatch) -> None:
    """已有摘要和存在性索引足以完成比较，不触发懒数组读取。"""
    path = tmp_path / "store"
    build_store(path, StorageScheme.SET_SQLITE_H5)
    left = DefaultSampleSet().load(path)
    right = DefaultSampleSet().load(path)

    def fail_load(*args, **kwargs):
        raise AssertionError("比较不应加载 payload")

    monkeypatch.setattr(left.storage, "load_fields", fail_load)
    monkeypatch.setattr(right.storage, "load_fields", fail_load)
    report = left.compare_with(right, features=["pga"])
    assert report.scalar_diff.empty
    assert report.presence_diff.empty


def test_summary_matches_rounded_payload(tmp_path: Path) -> None:
    """存储精度选项作用于 payload 和其摘要的同一个版本。"""
    path = tmp_path / "store"
    sample = DefaultSample(metadata=Metadata(), accel=AccelSeries.from_data([0.123456, 1.987654, 0.654321], dt=0.01))
    samples = DefaultSampleSet({sample.uid: sample})
    samples.save(path, storage_scheme=StorageScheme.SET_SQLITE_H5, data_options={"decimal_round": 2})
    assert inspect_storage_repository(path, level="deep").is_valid


@pytest.mark.parametrize("defect", ["summary", "payload"])
def test_deep_inspection_detects_missing_data(tmp_path: Path, defect: str) -> None:
    """缺失摘要与缺失载荷均被深检查定位。"""
    import h5py

    path = tmp_path / "store"
    _, sample = build_store(path, StorageScheme.SET_SQLITE_H5)
    if defect == "summary":
        with sqlite3.connect(path / "index.sqlite") as conn:
            conn.execute("DELETE FROM sample_summary_projection WHERE key = 'pga'")
    else:
        with h5py.File(path / "payload.h5", "a") as file:
            del file[f"samples/{sample._storage_payload_id}"]
    assert not inspect_storage_repository(path, level="deep").is_valid


def test_single_sample_lazy_copy_preserves_selected_payload(tmp_path: Path) -> None:
    """独立模块保存入口同样先补载所选数据，再切换目标。"""
    from dyntool.storage import save_sample

    path = tmp_path / "source"
    _, sample = build_store(path, StorageScheme.SAMPLE_H5)
    lazy = DefaultSampleSet().load(path)[sample.uid]
    save_sample(lazy, tmp_path / "target", io_options={"categories": ["accel"]})
    loaded = DefaultSampleSet().load(tmp_path / "target", load_mode=SampleLoadMode.EAGER)
    np.testing.assert_array_equal(loaded[sample.uid].accel.get_value(), [1, 2, 3])
    assert loaded[sample.uid].vel is None


@pytest.mark.parametrize("scheme", list(StorageScheme))
def test_repository_error_stops_pending_workers(tmp_path: Path, monkeypatch, scheme: StorageScheme) -> None:
    """非严格并发请求遇到仓库级错误后，不再尝试队列中的其他样本。"""
    samples, _ = build_store(tmp_path / "store", scheme)
    for index in range(3):
        sample = DefaultSample(
            metadata=Metadata(extra={"index": index}), accel=AccelSeries.from_data([1, 2, 3], dt=0.01)
        )
        samples[sample.uid] = sample
    attempts = []

    def fail(data):
        attempts.append(data)
        raise OSError("注入仓库级错误")

    monkeypatch.setattr(samples.storage._sample_storage.ctx, "serialize_container", fail)
    with pytest.raises(OSError, match="仓库级"):
        samples.save_all(strict=False, workers=3, show_progress=False)
    assert len(attempts) == 1
    assert samples.last_operation_report.stats.failed == 1
    assert samples.last_operation_report.stats.succeeded == 0


def test_comparison_distinguishes_equal_numbers_in_different_units() -> None:
    """数值相同但量纲尺度不同必须报告规范 SI 差异。"""
    metadata = Metadata()
    left_sample = DefaultSample(metadata=metadata, accel=AccelSeries.from_data([1, 2, 3], dt=0.01))
    right_sample = DefaultSample(
        metadata=metadata.model_copy(), accel=AccelSeries.from_data([1, 2, 3], dt=0.01, data_unit="cm/s**2")
    )
    report = DefaultSampleSet({left_sample.uid: left_sample}).compare_with(
        DefaultSampleSet({right_sample.uid: right_sample}), features=["pga"]
    )
    assert len(report.scalar_diff) == 1
    assert report.scalar_diff.iloc[0]["left"] == pytest.approx(3)
    assert report.scalar_diff.iloc[0]["right"] == pytest.approx(0.03)


def test_sqlite_session_cleanup_preserves_original_error_and_closes_connection(tmp_path: Path, monkeypatch) -> None:
    """退出期间 rollback 也失败时仍关闭连接，且原始异常保持可追溯。"""
    samples, _ = build_store(tmp_path / "store", StorageScheme.SET_SQLITE_H5)
    strategy = samples.storage._sample_storage.strategy
    original_connect = strategy._connect
    connections = []

    class FailingRollback:
        """仅在资源收尾处模拟驱动异常。"""

        def __init__(self, conn):
            self.conn = conn

        def __getattr__(self, name):
            return getattr(self.conn, name)

        def rollback(self):
            raise OSError("注入 rollback 收尾失败")

    def connect(**kwargs):
        conn = original_connect(**kwargs)
        connections.append(conn)
        return FailingRollback(conn)

    monkeypatch.setattr(strategy, "_connect", connect)
    original_error = ValueError("原始操作失败")
    with pytest.raises(ValueError) as caught:
        with strategy.write_session():
            raise original_error
    assert caught.value is original_error
    assert any("rollback" in note for note in caught.value.__notes__)
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        connections[0].execute("SELECT 1")


def test_sqlite_schema_work_precedes_data_transaction(tmp_path: Path, monkeypatch) -> None:
    """schema 校验仅在数据事务前执行，flush 不能隐式提交事务。"""
    samples, _ = build_store(tmp_path / "store", StorageScheme.SET_SQLITE_H5)
    strategy = samples.storage._sample_storage.strategy
    ensure_schema = strategy._ensure_schema

    def check(conn):
        assert not conn.in_transaction
        return ensure_schema(conn)

    monkeypatch.setattr(strategy, "_ensure_schema", check)
    samples.save_all(show_progress=False)


@pytest.mark.parametrize("scheme", [StorageScheme.SAMPLE_H5, StorageScheme.SAMPLE_JSON])
def test_backup_cleanup_failure_does_not_change_commit(tmp_path: Path, monkeypatch, scheme: StorageScheme) -> None:
    """无引用备份清理失败只报警，索引忽略备份并继续读取新版本。"""
    path = tmp_path / "store"
    samples, sample = build_store(path, scheme)
    sample.update(accel=AccelSeries.from_data([7, 8, 9], dt=0.01))
    unlink = Path.unlink

    def fail_backup(file, *args, **kwargs):
        if file.name.startswith(".dyntool-backup-"):
            raise OSError("注入备份清理失败")
        return unlink(file, *args, **kwargs)

    with monkeypatch.context() as context:
        context.setattr(Path, "unlink", fail_backup)
        with pytest.warns(RuntimeWarning, match="清理失败"):
            report = samples.save_all(show_progress=False)
    assert report.stats.succeeded == 1
    restored = DefaultSampleSet().load(path, load_mode=SampleLoadMode.EAGER)
    np.testing.assert_array_equal(restored[sample.uid].accel.get_value(), [7, 8, 9])


@pytest.mark.parametrize("stage", ["_write_payload", "_sync_presence_artifacts"])
def test_sqlite_partial_write_failure_keeps_old_version(tmp_path: Path, monkeypatch, stage: str) -> None:
    """payload 或槽位索引已部分写入后报错，旧版本仍完整且可重试。"""
    path = tmp_path / "store"
    samples, sample = build_store(path, StorageScheme.SET_SQLITE_H5)
    strategy = samples.storage._sample_storage.strategy
    old_id = sample._storage_payload_id
    sample.update(accel=AccelSeries.from_data([7, 8, 9], dt=0.01))
    original = getattr(strategy, stage)

    def fail_after_write(*args, **kwargs):
        original(*args, **kwargs)
        raise ValueError("注入部分写入失败")

    with monkeypatch.context() as context:
        context.setattr(strategy, stage, fail_after_write)
        errors = samples.storage.save_all(strict=False, show_progress=False)
    assert sample.uid in errors
    assert sample._storage_payload_id == old_id
    restored = DefaultSampleSet().load(path, load_mode=SampleLoadMode.EAGER)
    np.testing.assert_array_equal(restored[sample.uid].accel.get_value(), [1, 2, 3])
    assert inspect_storage_repository(path, level="deep").is_valid
    samples.save_all(show_progress=False)
    assert inspect_storage_repository(path, level="deep").is_valid


@pytest.mark.parametrize("persist", [False, True])
def test_missing_scalar_features_follow_same_comparison_rules(tmp_path: Path, persist: bool) -> None:
    """单方缺失特征报告差异，双方均缺失视为相同。"""
    metadata = Metadata()
    left_sample = DefaultSample(metadata=metadata)
    right_sample = DefaultSample(
        metadata=metadata.model_copy(), vel=VelSeries.from_data([10, 20, 30], dt=0.01, data_unit="cm/s")
    )
    left = DefaultSampleSet({left_sample.uid: left_sample})
    right = DefaultSampleSet({right_sample.uid: right_sample})
    if persist:
        left.save(tmp_path / "left", storage_scheme=StorageScheme.SET_SQLITE_H5)
        right.save(tmp_path / "right", storage_scheme=StorageScheme.SET_SQLITE_H5)
        left = DefaultSampleSet().load(tmp_path / "left")
        right = DefaultSampleSet().load(tmp_path / "right")
    report = left.compare_with(right, features=["pga", "pgv"])
    assert len(report.scalar_diff) == 1
    assert report.scalar_diff.iloc[0]["right"] == pytest.approx(0.3)
