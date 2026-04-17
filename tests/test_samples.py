"""样本与样本集基本行为测试。"""

import json
import os
import sqlite3
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import h5py
import numpy as np
import pytest

import dyntool.logging as dt_logging
import dyntool.storage as dt_storage
from dyntool.domain.constants import DataCategory
from dyntool.domain.metadata import (
    Metadata,
    VibrationTestMetadata,
)
from dyntool.domain.models import AccelSeries, FreqSpec, RespSpec, ZVLEval
from dyntool.domain.samples import _sample_set_compare as sample_set_compare_module
from dyntool.domain.samples import default as default_samples_module
from dyntool.domain.samples import sets as sample_sets_module
from dyntool.domain.samples import vibration_test as vibration_samples_module
from dyntool.domain.samples.types import SampleSetComparisonReport
from dyntool.domain.samples import (
    OperationResult,
    Sample,
    SampleLoadMode,
    SampleSet,
    VibrationTestSample,
    VibrationTestSampleSet,
)
from dyntool.domain.samples.batch import BatchOperationReport
from dyntool.domain.samples.factories import build_metadata
from dyntool.infrastructure.persistence import RecoverableIOError
from dyntool.infrastructure import sample_set_storage as sample_set_storage_module
from dyntool.infrastructure import sample_storage_sqlite_h5 as sqlite_strategy_module
from dyntool.infrastructure import sample_storage_sqlite_h5_types as sqlite_strategy_types_module
from dyntool.infrastructure import sample_storage_strategy_impl as strategy_impl_module
from dyntool.storage.types import AttrDataFormat, StorageMode, StorageScheme


def _make_vib_meta() -> VibrationTestMetadata:
    return VibrationTestMetadata(
        case="c1",
        point="pt1",
        instr="instr1",
        dir="Z",
        record="r1",
        timestamp=datetime(2025, 1, 1, 12, 0, 0),
    )


def _spawn_sqlite_h5_writer_holder(
    *,
    store_dir: Path,
    ready_path: Path,
    sleep_seconds: float,
) -> subprocess.Popen[str]:
    repo_root = Path(__file__).resolve().parents[1]
    code = """
from pathlib import Path
import os
import time

from dyntool.domain.samples import SampleLoadMode, SampleSet
from dyntool.storage.types import StorageScheme

store_dir = Path(os.environ["DYNSQL_STORE_DIR"])
ready_path = Path(os.environ["DYNSQL_READY_PATH"])
sleep_seconds = float(os.environ["DYNSQL_SLEEP_SECONDS"])

loaded = SampleSet.from_storage(
    store_dir,
    storage_scheme=StorageScheme.SET_SQLITE_H5,
    load_mode=SampleLoadMode.METADATA_ONLY,
)
strategy = loaded.storage._sample_storage.strategy
with strategy.write_session():
    ready_path.write_text("ready", encoding="utf-8")
    time.sleep(sleep_seconds)
"""
    env = dict(os.environ)
    existing_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(repo_root / "src") + (os.pathsep + existing_pythonpath if existing_pythonpath else "")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["DYNSQL_STORE_DIR"] = str(store_dir)
    env["DYNSQL_READY_PATH"] = str(ready_path)
    env["DYNSQL_SLEEP_SECONDS"] = str(sleep_seconds)
    return subprocess.Popen(
        [sys.executable, "-B", "-c", code],
        cwd=repo_root,
        env=env,
        text=True,
    )


def _spawn_sqlite_h5_reader_holder(
    *,
    store_dir: Path,
    ready_path: Path,
    sleep_seconds: float,
) -> subprocess.Popen[str]:
    repo_root = Path(__file__).resolve().parents[1]
    code = """
from pathlib import Path
import os
import time

from dyntool.domain.samples import SampleLoadMode, SampleSet
from dyntool.storage.types import StorageScheme

store_dir = Path(os.environ["DYNSQL_STORE_DIR"])
ready_path = Path(os.environ["DYNSQL_READY_PATH"])
sleep_seconds = float(os.environ["DYNSQL_SLEEP_SECONDS"])

loaded = SampleSet.from_storage(
    store_dir,
    storage_scheme=StorageScheme.SET_SQLITE_H5,
    load_mode=SampleLoadMode.METADATA_ONLY,
)
strategy = loaded.storage._sample_storage.strategy
with strategy.read_session():
    ready_path.write_text("ready", encoding="utf-8")
    time.sleep(sleep_seconds)
"""
    env = dict(os.environ)
    existing_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(repo_root / "src") + (os.pathsep + existing_pythonpath if existing_pythonpath else "")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["DYNSQL_STORE_DIR"] = str(store_dir)
    env["DYNSQL_READY_PATH"] = str(ready_path)
    env["DYNSQL_SLEEP_SECONDS"] = str(sleep_seconds)
    return subprocess.Popen(
        [sys.executable, "-B", "-c", code],
        cwd=repo_root,
        env=env,
        text=True,
    )


class TestVibrationTestSample:
    """VibrationTestSample 单样本评价。"""

    def test_eval_zvl_on_sample(self) -> None:
        """单样本有 accel 时 eval_zvl 成功并写回 zvl。"""
        meta = _make_vib_meta()
        accel = AccelSeries.from_data(np.random.randn(1000) * 0.01, dt=0.002)
        sample = VibrationTestSample(metadata=meta, accel=accel)
        result = sample.evaluation.zvl(overwrite=True, freq_range=(2.0, 60.0))
        assert isinstance(result, OperationResult)
        assert result.success is True
        assert result.value is sample
        assert sample.zvl is not None

    def test_eval_zvl_skip_when_exists(self) -> None:
        """已有 zvl 时 eval_zvl(overwrite=False) 跳过。"""
        meta = _make_vib_meta()
        accel = AccelSeries.from_data(np.random.randn(500) * 0.01, dt=0.002)
        sample = VibrationTestSample(metadata=meta, accel=accel)
        sample.evaluation.zvl(overwrite=True)
        result2 = sample.evaluation.zvl(overwrite=False)
        assert isinstance(result2, OperationResult)
        assert result2.success is False
        assert "已存在" in result2.message or "跳过" in result2.message

    def test_calc_vel_calc_disp(self) -> None:
        """振动样本共享基类会写回 vel / disp。"""
        meta = _make_vib_meta()
        accel = AccelSeries.from_data(np.random.randn(500) * 0.01, dt=0.002)
        sample = VibrationTestSample(metadata=meta, accel=accel)
        vel_result = sample.calc_vel(overwrite=True)
        disp_result = sample.calc_disp(overwrite=True)
        assert vel_result.success is True and sample.vel is not None
        assert disp_result.success is True and sample.disp is not None

    def test_calc_freqspec(self) -> None:
        """振动样本共享基类会写回幅频与相频。"""
        meta = _make_vib_meta()
        accel = AccelSeries.from_data(np.random.randn(512) * 0.01, dt=0.002)
        sample = VibrationTestSample(metadata=meta, accel=accel)
        result = sample.calc_freqspec(overwrite=True)
        assert result.success is True
        assert sample.freqspec is not None
        assert not hasattr(sample, "freq_amp")
        assert not hasattr(sample, "freq_pha")

    def test_calc_respspec(self) -> None:
        """振动样本共享基类会写回 sa/sv/sd/psa/psv。"""
        meta = _make_vib_meta()
        accel = AccelSeries.from_data(np.random.randn(500) * 0.01, dt=0.002)
        sample = VibrationTestSample(metadata=meta, accel=accel)
        result = sample.calc_respspec(overwrite=True)
        assert result.success is True
        assert sample.respspec is not None
        assert not hasattr(sample, "respspec_sa")
        assert not hasattr(sample, "respspec_sv")
        assert not hasattr(sample, "respspec_sd")
        assert not hasattr(sample, "respspec_psa")
        assert not hasattr(sample, "respspec_psv")

    def test_single_sample_save_load_persists_freqspec_and_respspec(self, tmp_path: Path) -> None:
        sample = VibrationTestSample(
            metadata=_make_vib_meta(),
            accel=AccelSeries.from_data(np.random.randn(512) * 0.01, dt=0.002),
        )
        sample.calc_freqspec(overwrite=True)
        sample.calc_respspec(overwrite=True)
        store_path = tmp_path / "single_sample.h5"

        sample.save(store_path, storage_scheme=StorageScheme.SAMPLE_H5)

        loaded = VibrationTestSample(metadata=_make_vib_meta())
        loaded.load(store_path, storage_scheme=StorageScheme.SAMPLE_H5)

        assert isinstance(loaded.freqspec, FreqSpec)
        assert isinstance(loaded.respspec, RespSpec)


class TestVibrationTestSampleSet:
    """VibrationTestSampleSet 集合与批量评价。"""

    def test_add_and_eval_all(self) -> None:
        """样本集添加样本后 eval_zvl 可批量运行。"""
        meta = _make_vib_meta()
        accel = AccelSeries.from_data(np.random.randn(800) * 0.01, dt=0.002)
        sample = VibrationTestSample(metadata=meta, accel=accel)
        sample_set = VibrationTestSampleSet()
        sample_set[sample.uid] = sample
        sample_set.evaluation.zvl(overwrite=True, freq_range=(2.0, 60.0))
        assert sample.zvl is not None

    def test_eval_overwrite_param(self) -> None:
        """新的 overwrite 参数可覆盖旧结果（兼容 mode 语义）。"""
        meta = _make_vib_meta()
        accel = AccelSeries.from_data(np.random.randn(800) * 0.01, dt=0.002)
        sample = VibrationTestSample(metadata=meta, accel=accel)
        sample_set = VibrationTestSampleSet({sample.uid: sample})
        sample_set.evaluation.zvl(overwrite=True, freq_range=(2.0, 60.0))
        assert sample.zvl is not None

    def test_calc_freqspec_batch_writes_back_and_returns_report(self) -> None:
        sample_a = VibrationTestSample(
            metadata=_make_vib_meta(),
            accel=AccelSeries.from_data(np.random.randn(512) * 0.01, dt=0.002),
        )
        sample_b = VibrationTestSample(
            metadata=VibrationTestMetadata(
                case="c2",
                point="pt2",
                instr="instr2",
                dir="X",
                record="r2",
                timestamp=datetime(2025, 1, 1, 12, 30, 0),
            ),
            accel=AccelSeries.from_data(np.random.randn(512) * 0.01, dt=0.002),
        )
        sample_set = VibrationTestSampleSet({sample_a.uid: sample_a, sample_b.uid: sample_b})

        report = sample_set.calc_freqspec(overwrite=True)

        assert isinstance(report, BatchOperationReport)
        assert set(report.results) == {sample_a.uid, sample_b.uid}
        assert all(item.success is True for item in report.results.values())
        assert isinstance(sample_a.freqspec, FreqSpec)
        assert isinstance(sample_b.freqspec, FreqSpec)

    def test_calc_freqspec_batch_supports_uid_filter_skip_and_missing_accel(self) -> None:
        sample_a = VibrationTestSample(
            metadata=_make_vib_meta(),
            accel=AccelSeries.from_data(np.random.randn(512) * 0.01, dt=0.002),
        )
        sample_b = VibrationTestSample(
            metadata=VibrationTestMetadata(
                case="c2",
                point="pt2",
                instr="instr2",
                dir="X",
                record="r2",
                timestamp=datetime(2025, 1, 1, 12, 30, 0),
            ),
            accel=AccelSeries.from_data(np.random.randn(512) * 0.01, dt=0.002),
        )
        sample_c = VibrationTestSample(
            metadata=VibrationTestMetadata(
                case="c3",
                point="pt3",
                instr="instr3",
                dir="Y",
                record="r3",
                timestamp=datetime(2025, 1, 1, 13, 0, 0),
            ),
        )
        sample_set = VibrationTestSampleSet({sample_a.uid: sample_a, sample_b.uid: sample_b, sample_c.uid: sample_c})

        sample_set.calc_freqspec(uid=sample_a.uid, overwrite=True)
        single_result = sample_set.calc_freqspec(uid=sample_a.uid, overwrite=False, strict=False)
        filtered_results = sample_set.calc_freqspec(
            overwrite=True,
            strict=False,
            filter=lambda sample: sample.metadata.point in {"pt2", "pt3"},
        )

        assert isinstance(single_result, BatchOperationReport)
        assert single_result.results[sample_a.uid].success is False
        assert (
            "已存在" in single_result.results[sample_a.uid].message
            or "跳过" in single_result.results[sample_a.uid].message
        )
        assert set(filtered_results.results) == {sample_b.uid, sample_c.uid}
        assert filtered_results.results[sample_b.uid].success is True
        assert filtered_results.results[sample_c.uid].success is False
        assert "无加速度数据" in filtered_results.results[sample_c.uid].message
        assert isinstance(sample_b.freqspec, FreqSpec)
        assert sample_c.freqspec is None

    def test_calc_freqspec_batch_strict_mode_raises_and_non_strict_collects_report(self) -> None:
        sample_ok = VibrationTestSample(
            metadata=_make_vib_meta(),
            accel=AccelSeries.from_data(np.random.randn(512) * 0.01, dt=0.002),
        )
        sample_missing = VibrationTestSample(
            metadata=VibrationTestMetadata(
                case="c2",
                point="pt2",
                instr="instr2",
                dir="X",
                record="r2",
                timestamp=datetime(2025, 1, 1, 12, 30, 0),
            ),
        )
        sample_set = VibrationTestSampleSet({sample_ok.uid: sample_ok, sample_missing.uid: sample_missing})

        with pytest.raises(RecoverableIOError, match="批处理失败"):
            sample_set.calc_freqspec(overwrite=True)

        results = sample_set.calc_freqspec(overwrite=True, strict=False)

        report = sample_set.last_operation_report
        assert report is not None
        assert report.stats.total == 2
        assert report.stats.valid_samples == 1
        assert report.stats.succeeded == 1
        assert report.stats.failed == 1
        assert report.results[sample_missing.uid].status == "failed"
        assert isinstance(results, BatchOperationReport)
        assert results.results[sample_missing.uid].success is False

    def test_update_data_supports_strict_and_non_strict_modes(self) -> None:
        sample = VibrationTestSample(
            metadata=_make_vib_meta(),
            accel=AccelSeries.from_data(np.random.randn(64) * 0.01, dt=0.002),
        )
        sample_set = VibrationTestSampleSet({sample.uid: sample})
        new_vel = sample.accel.calc_vel()  # type: ignore[union-attr]

        assert sample_set.update_data(sample.uid, new_vel) is True

        with pytest.raises(KeyError, match="missing"):
            sample_set.update_data("missing", new_vel)

        ok = sample_set.update_data("missing", new_vel, strict=False)
        assert ok is False

    def test_calc_respspec_batch_processing_namespace_matches_direct_call(self) -> None:
        sample = VibrationTestSample(
            metadata=_make_vib_meta(),
            accel=AccelSeries.from_data(np.random.randn(512) * 0.01, dt=0.002),
        )
        sample_set = VibrationTestSampleSet({sample.uid: sample})

        direct = sample_set.calc_respspec(uid=sample.uid, overwrite=True)
        via_namespace = sample_set.processing.calc_respspec(uid=sample.uid, overwrite=True)

        assert direct.results[sample.uid].success is True
        assert via_namespace.results[sample.uid].success is True
        assert isinstance(sample.respspec, RespSpec)

    def test_save_all_load_all_persists_freqspec_and_respspec(self, tmp_path: Path) -> None:
        sample_a = VibrationTestSample(
            metadata=_make_vib_meta(),
            accel=AccelSeries.from_data(np.random.randn(512) * 0.01, dt=0.002),
        )
        sample_b = VibrationTestSample(
            metadata=VibrationTestMetadata(
                case="c2",
                point="pt2",
                instr="instr2",
                dir="X",
                record="r2",
                timestamp=datetime(2025, 1, 1, 12, 30, 0),
            ),
            accel=AccelSeries.from_data(np.random.randn(512) * 0.01, dt=0.002),
        )
        source = VibrationTestSampleSet({sample_a.uid: sample_a, sample_b.uid: sample_b})
        source.calc_freqspec(overwrite=True)
        source.calc_respspec(overwrite=True)

        base_dir = tmp_path / "spectra_store"
        source.connect_storage(base_dir, mode=StorageMode.CREATE, storage_scheme=StorageScheme.SET_DIR)
        save_report = source.save_all()

        loaded = VibrationTestSampleSet()
        loaded.connect_storage(base_dir, mode=StorageMode.OPEN, storage_scheme=StorageScheme.SET_DIR)
        load_report = loaded.load_all(load_mode=SampleLoadMode.EAGER)

        assert isinstance(save_report, BatchOperationReport)
        assert save_report.stats.failed == 0
        assert isinstance(load_report, BatchOperationReport)
        assert load_report.stats.failed == 0
        assert isinstance(loaded[sample_a.uid].freqspec, FreqSpec)
        assert isinstance(loaded[sample_a.uid].respspec, RespSpec)
        assert isinstance(loaded[sample_b.uid].freqspec, FreqSpec)
        assert isinstance(loaded[sample_b.uid].respspec, RespSpec)

    def test_vibration_test_metadata_alias_is_generated_with_canonical_pattern(self) -> None:
        metadata = VibrationTestMetadata(
            case="A1",
            record="1",
            point="A1",
            instr="164",
            dir="001",
            timestamp=datetime(2026, 1, 25, 5, 7, 44),
        )

        assert metadata.alias == "C-A1_R-1_P-A1_I-164_T-20260125050744_D-001"

    def test_sampleset_reindexes_uid_after_metadata_attribute_assignment(self) -> None:
        sample = VibrationTestSample(
            metadata=_make_vib_meta(),
            accel=AccelSeries.from_data(np.random.randn(64) * 0.01, dt=0.002),
        )
        sample_set = VibrationTestSampleSet({sample.uid: sample})
        old_uid = sample.uid

        sample.metadata.point = "pt9"

        assert sample.uid != old_uid
        assert old_uid not in sample_set
        assert sample.uid in sample_set
        assert sample_set[sample.uid] is sample

    def test_sampleset_metadata_reindex_marks_storage_dirty_but_does_not_persist_automatically(
        self, tmp_path: Path
    ) -> None:
        sample = VibrationTestSample(
            metadata=_make_vib_meta(),
            accel=AccelSeries.from_data(np.random.randn(64) * 0.01, dt=0.002),
        )
        sample_set = VibrationTestSampleSet({sample.uid: sample})
        store_dir = tmp_path / "uid_reindex_store"
        sample_set.save(store_dir, storage_scheme=StorageScheme.SET_DIR)
        old_uid = sample.uid

        sample.metadata.point = "pt-updated"

        assert sample_set.storage is not None
        assert getattr(sample_set, "storage_dirty", False) is True

        loaded_before_cleanup = VibrationTestSampleSet.from_storage(
            store_dir,
            storage_scheme=StorageScheme.SET_DIR,
        )
        assert old_uid in loaded_before_cleanup

        sample_set.save_all()
        sample_set.organize_storage()

        loaded_after_cleanup = VibrationTestSampleSet.from_storage(
            store_dir,
            storage_scheme=StorageScheme.SET_DIR,
        )
        assert old_uid not in loaded_after_cleanup
        assert sample.uid in loaded_after_cleanup

    def test_shortcut_io_delegates_without_storage_types_import(self, tmp_path: Path) -> None:
        meta = _make_vib_meta()
        accel = AccelSeries.from_data(np.random.randn(256) * 0.01, dt=0.002)
        sample = VibrationTestSample(metadata=meta, accel=accel)
        source = VibrationTestSampleSet({sample.uid: sample})
        assert not hasattr(vibration_samples_module, "importlib")

        csv_dir = tmp_path / "vibration_csv"
        h5_path = tmp_path / "vibration.h5"
        source.save(csv_dir, storage_scheme=StorageScheme.SET_DIR)
        source.save(h5_path, storage_scheme=StorageScheme.SET_H5)

        from_csv = VibrationTestSampleSet.from_storage(
            csv_dir,
            storage_scheme=StorageScheme.SET_DIR,
        )
        from_h5 = VibrationTestSampleSet.from_storage(
            h5_path,
            storage_scheme=StorageScheme.SET_H5,
        )
        assert sample.uid in from_csv
        assert sample.uid in from_h5

    def test_get_samples_is_inherited_from_sample_set_base(self) -> None:
        assert VibrationTestSampleSet.get_samples is sample_sets_module.SampleSetBase.get_samples

        sample_a = VibrationTestSample(
            metadata=_make_vib_meta(),
            accel=AccelSeries.from_data(np.random.randn(64) * 0.01, dt=0.002),
        )
        sample_b = VibrationTestSample(
            metadata=VibrationTestMetadata(
                case="c2",
                point="pt2",
                instr="instr2",
                dir="X",
                record="r2",
                timestamp=datetime(2025, 1, 1, 12, 30, 0),
            ),
            accel=AccelSeries.from_data(np.random.randn(64) * 0.01, dt=0.002),
        )
        sample_set = VibrationTestSampleSet({sample_a.uid: sample_a, sample_b.uid: sample_b})

        filtered = sample_set.get_samples(lambda sample: sample.metadata.point == "pt2")

        assert isinstance(filtered, VibrationTestSampleSet)
        assert list(filtered) == [sample_b.uid]
        assert list(sample_set) == [sample_a.uid, sample_b.uid]

    def test_filter_is_inherited_from_sample_set_base(self) -> None:
        assert VibrationTestSampleSet.filter is sample_sets_module.SampleSetBase.filter

        sample_a = VibrationTestSample(
            metadata=_make_vib_meta(),
            accel=AccelSeries.from_data(np.random.randn(64) * 0.01, dt=0.002),
        )
        sample_b = VibrationTestSample(
            metadata=VibrationTestMetadata(
                case="c2",
                point="pt2",
                instr="instr2",
                dir="X",
                record="r2",
                timestamp=datetime(2025, 1, 1, 12, 30, 0),
            ),
            accel=AccelSeries.from_data(np.random.randn(64) * 0.01, dt=0.002),
        )
        sample_set = VibrationTestSampleSet({sample_a.uid: sample_a, sample_b.uid: sample_b})

        returned = sample_set.filter(lambda sample: sample.metadata.point == "pt2")

        assert returned is sample_set
        assert list(sample_set) == [sample_b.uid]

    def test_get_sample_returns_none_or_single_sample(self) -> None:
        sample_a = VibrationTestSample(
            metadata=_make_vib_meta(),
            accel=AccelSeries.from_data(np.random.randn(64) * 0.01, dt=0.002),
        )
        sample_b = VibrationTestSample(
            metadata=VibrationTestMetadata(
                case="c2",
                point="pt2",
                instr="instr2",
                dir="X",
                record="r2",
                timestamp=datetime(2025, 1, 1, 12, 30, 0),
            ),
            accel=AccelSeries.from_data(np.random.randn(64) * 0.01, dt=0.002),
        )
        sample_set = VibrationTestSampleSet({sample_a.uid: sample_a, sample_b.uid: sample_b})

        assert sample_set.get_sample(lambda sample: sample.metadata.point == "missing", strict=False) is None
        assert sample_set.get_sample(lambda sample: sample.metadata.point == "pt2") is sample_b

    def test_get_sample_raises_when_multiple_samples_match(self) -> None:
        sample_a = VibrationTestSample(
            metadata=_make_vib_meta(),
            accel=AccelSeries.from_data(np.random.randn(64) * 0.01, dt=0.002),
        )
        sample_b = VibrationTestSample(
            metadata=VibrationTestMetadata(
                case="c2",
                point="pt2",
                instr="instr2",
                dir="X",
                record="r2",
                timestamp=datetime(2025, 1, 1, 12, 30, 0),
            ),
            accel=AccelSeries.from_data(np.random.randn(64) * 0.01, dt=0.002),
        )
        sample_set = VibrationTestSampleSet({sample_a.uid: sample_a, sample_b.uid: sample_b})

        with pytest.raises(ValueError, match="expected exactly one matched sample"):
            sample_set.get_sample()


class TestDefaultSampleSet:
    """通用 Sample/SampleSet（default 域）生产能力。"""

    def test_default_metadata_uid_stable_and_unique(self) -> None:
        """default metadata 的 UID 应随 extra 变化。"""
        m1 = Metadata(extra={"line": "A", "ch": 1})
        m2 = Metadata(extra={"line": "A", "ch": 2})
        assert m1.uid != m2.uid

    def test_default_set_storage_roundtrip(self, tmp_path: Path) -> None:
        """default SampleSet 支持 CSV/H5 往返。"""
        meta = Metadata(extra={"source": "sensor-A"})
        accel = AccelSeries.from_data(np.random.randn(256) * 0.01, dt=0.002)
        sample = Sample(metadata=meta, accel=accel)
        sample_set = SampleSet({sample.uid: sample})

        csv_dir = tmp_path / "default_csv"
        h5_path = tmp_path / "default.h5"
        sample_set.save(csv_dir, storage_scheme=StorageScheme.SET_DIR)
        sample_set.save(h5_path, storage_scheme=StorageScheme.SET_H5)

        from_csv_set = SampleSet.from_storage(
            csv_dir,
            storage_scheme=StorageScheme.SET_DIR,
        )
        from_h5_set = SampleSet.from_storage(
            h5_path,
            storage_scheme=StorageScheme.SET_H5,
        )
        assert len(from_csv_set) == 1
        assert len(from_h5_set) == 1
        uid = sample.uid
        assert uid in from_csv_set
        assert uid in from_h5_set
        assert from_csv_set[uid].accel is not None
        assert from_h5_set[uid].accel is not None

    def test_default_sample_supports_freqspec_and_respspec_slots(self) -> None:
        meta = Metadata(attributes={"source": "sensor-A"})
        accel = AccelSeries.from_data(np.random.randn(256) * 0.01, dt=0.002)
        freqspec = accel.calc_freqspec()
        respspec = accel.calc_respspec_bundle()

        sample = Sample(
            metadata=meta,
            accel=accel,
            freqspec=freqspec,
            respspec=respspec,
        )

        assert isinstance(sample.freqspec, FreqSpec)
        assert isinstance(sample.respspec, RespSpec)

    def test_public_data_model_slots_are_storable_by_default(self) -> None:
        for schema in (Sample.sample_schema, VibrationTestSample.sample_schema):
            assert schema.slot("freqspec").include_in_storage is True
            assert schema.slot("respspec").include_in_storage is True

    def test_default_sample_set_calc_freqspec_rejects_unsupported_sample_type(self) -> None:
        sample = self._make_default_sample("unsupported-freqspec")
        sample_set = SampleSet({sample.uid: sample})

        with pytest.raises(TypeError, match="calc_freqspec"):
            sample_set.calc_freqspec(overwrite=True)

    def test_default_sample_set_calc_respspec_rejects_unsupported_sample_type(self) -> None:
        sample = self._make_default_sample("unsupported-respspec")
        sample_set = SampleSet({sample.uid: sample})

        with pytest.raises(TypeError, match="calc_respspec"):
            sample_set.processing.calc_respspec(overwrite=True)

    def test_force_parameter_is_removed_from_processing_entrypoints(self) -> None:
        sample = VibrationTestSample(
            metadata=_make_vib_meta(),
            accel=AccelSeries.from_data(np.random.randn(256) * 0.01, dt=0.002),
        )
        sample_set = VibrationTestSampleSet({sample.uid: sample})

        with pytest.raises(TypeError):
            sample.calc_freqspec(force=True)  # type: ignore[call-arg]
        with pytest.raises(TypeError):
            sample.evaluation.zvl(force=True)  # type: ignore[call-arg]
        with pytest.raises(TypeError):
            sample_set.calc_freqspec(force=True)  # type: ignore[call-arg]
        with pytest.raises(TypeError):
            sample_set.evaluation.zvl(force=True)  # type: ignore[call-arg]

    def test_shortcut_io_delegates_without_storage_types_import(self, tmp_path: Path) -> None:
        sample = self._make_default_sample("guarded")
        source = SampleSet({sample.uid: sample})
        assert not hasattr(default_samples_module, "importlib")

        csv_dir = tmp_path / "default_guarded_csv"
        h5_path = tmp_path / "default_guarded.h5"
        source.save(csv_dir, storage_scheme=StorageScheme.SET_DIR)
        source.save(h5_path, storage_scheme=StorageScheme.SET_H5)

        from_csv = SampleSet.from_storage(
            csv_dir,
            storage_scheme=StorageScheme.SET_DIR,
        )
        from_h5 = SampleSet.from_storage(
            h5_path,
            storage_scheme=StorageScheme.SET_H5,
        )
        assert sample.uid in from_csv
        assert sample.uid in from_h5

    def _make_default_sample(self, source: str) -> Sample:
        meta = Metadata(extra={"source": source})
        accel = AccelSeries.from_data(np.random.randn(256) * 0.01, dt=0.002)
        vel = accel.calc_vel()
        return Sample(metadata=meta, accel=accel, vel=vel)

    @pytest.mark.parametrize(
        "storage_scheme",
        [
            StorageScheme.SAMPLE_JSON,
            StorageScheme.SAMPLE_H5,
            StorageScheme.SET_H5,
            StorageScheme.SET_DIR,
        ],
    )
    def test_storage_roundtrip_for_storage_schemes(self, tmp_path: Path, storage_scheme: StorageScheme) -> None:
        source = SampleSet()
        s1 = self._make_default_sample("A")
        s2 = self._make_default_sample("B")
        source[s1.uid] = s1
        source[s2.uid] = s2

        base_dir = tmp_path / storage_scheme
        source.connect_storage(
            base_dir,
            mode=StorageMode.CREATE,
            storage_scheme=storage_scheme,
            set_filename="all_samples.h5",
        )
        source.save_all()

        loaded = SampleSet.from_storage(
            base_dir,
            storage_scheme=storage_scheme,
            set_filename="all_samples.h5",
        )

        assert len(loaded) == 2
        assert s1.uid in loaded and s2.uid in loaded
        assert loaded[s1.uid].accel is not None
        assert loaded[s2.uid].vel is not None

    @pytest.mark.parametrize("attr_data_format", [AttrDataFormat.CSV, AttrDataFormat.NPY])
    def test_storage_attr_table_roundtrip(self, tmp_path: Path, attr_data_format: AttrDataFormat) -> None:
        source = SampleSet()
        s1 = self._make_default_sample("csvnpy")
        source[s1.uid] = s1

        base_dir = tmp_path / f"attr_table_{attr_data_format}"
        source.connect_storage(
            base_dir,
            mode=StorageMode.CREATE,
            storage_scheme=StorageScheme.SET_ATTR_TABLE,
            data_options={"attr_data_format": attr_data_format.value},
        )
        source.save_all()

        loaded = SampleSet.from_storage(
            base_dir,
            storage_scheme=StorageScheme.SET_ATTR_TABLE,
            data_options={"attr_data_format": attr_data_format.value},
        )

        assert len(loaded) == 1
        assert s1.uid in loaded
        assert loaded[s1.uid].accel is not None
        assert loaded[s1.uid].vel is not None

    def test_storage_name_resolver_and_precision(self, tmp_path: Path) -> None:
        source = SampleSet()
        sample = self._make_default_sample("precision")
        source[sample.uid] = sample

        base_dir = tmp_path / "sample_dir_precision"

        def name_resolver(item: Sample, context: dict[str, object]) -> str:
            uid = str(context["uid"])
            return f"custom_{uid[:8]}"

        source.connect_storage(
            base_dir,
            mode=StorageMode.CREATE,
            storage_scheme=StorageScheme.SET_DIR,
            name_resolver=name_resolver,
            data_options={"decimal_round": 4, "float_dtype": "float32"},
        )
        assert source.storage is not None
        source.storage.save_all()

        custom_dir = base_dir / f"custom_{sample.uid[:8]}"
        assert custom_dir.exists()
        npz_path = custom_dir / "data.npz"
        assert npz_path.exists()
        with np.load(npz_path, allow_pickle=True) as npz:
            accel_payload = npz["accel"].item()
        accel_value = accel_payload["value"]
        assert isinstance(accel_value, np.ndarray)
        assert accel_value.dtype == np.float32

    def test_sample_h5_storage_uses_gzip_compression_by_default(self, tmp_path: Path) -> None:
        sample = self._make_default_sample("sample_h5_gzip")
        path = tmp_path / "single_sample.h5"

        sample.save(path, storage_scheme=StorageScheme.SAMPLE_H5)

        with h5py.File(path / f"{sample.uid}.h5", "r") as handle:
            dataset = handle["accel"]["value"]
            assert dataset.compression == "gzip"
            assert dataset.compression_opts == 4

    def test_set_h5_storage_uses_gzip_compression_by_default(self, tmp_path: Path) -> None:
        sample_set = SampleSet()
        sample = self._make_default_sample("set_h5_gzip")
        sample_set[sample.uid] = sample
        path = tmp_path / "sample_set.h5"

        sample_set.save(path, storage_scheme=StorageScheme.SET_H5)

        with h5py.File(path, "r") as handle:
            dataset = handle[sample.uid]["accel"]["value"]
            assert dataset.compression == "gzip"
            assert dataset.compression_opts == 4

    def test_sample_h5_storage_allows_explicit_compression_override(self, tmp_path: Path) -> None:
        sample = self._make_default_sample("sample_h5_lzf")
        path = tmp_path / "single_sample_lzf.h5"

        sample.save(
            path,
            storage_scheme=StorageScheme.SAMPLE_H5,
            data_options={"h5_compression": "lzf"},
        )

        with h5py.File(path / f"{sample.uid}.h5", "r") as handle:
            dataset = handle["accel"]["value"]
            assert dataset.compression == "lzf"
            assert dataset.compression_opts is None

    def test_connect_storage_rejects_removed_data_format(self, tmp_path: Path) -> None:
        sample_set = SampleSet()
        with pytest.raises(TypeError):
            sample_set.connect_storage(
                tmp_path / "legacy",
                mode=StorageMode.CREATE,
                data_format="csv",  # type: ignore[call-arg]
            )

    def test_storage_save_all_supports_strict_mode(self, tmp_path: Path) -> None:
        source = SampleSet()
        sample = self._make_default_sample("strict")
        source[sample.uid] = sample
        source.connect_storage(
            tmp_path / "strict_store",
            mode=StorageMode.CREATE,
            storage_scheme=StorageScheme.SET_DIR,
        )

        def _raise_save(*args: object, **kwargs: object) -> None:
            raise RuntimeError("save failed")

        source.storage.save_sample = _raise_save  # type: ignore[method-assign]
        with pytest.raises(RecoverableIOError):
            source.storage.save_all(strict=True)
        errs = source.storage.save_all(strict=False)
        assert sample.uid in errs

    def test_batch_strict_does_not_depend_on_persistence_import(self) -> None:
        sample = self._make_default_sample("batch-strict")
        sample_set = SampleSet({sample.uid: sample})

        assert not hasattr(sample_sets_module, "importlib")

        def _raise(_sample: Sample) -> None:
            raise RuntimeError("boom")

        with pytest.raises(RecoverableIOError):
            sample_set.batch(_raise, strict=True)

    def test_storage_save_load_supports_workers(self, tmp_path: Path) -> None:
        source = SampleSet()
        s1 = self._make_default_sample("W1")
        s2 = self._make_default_sample("W2")
        source[s1.uid] = s1
        source[s2.uid] = s2
        base_dir = tmp_path / "workers"
        source.connect_storage(base_dir, mode=StorageMode.CREATE, storage_scheme=StorageScheme.SET_DIR)
        save_errors = source.save_all(strict=True, workers=2, chunk_size=1)
        assert isinstance(save_errors, BatchOperationReport)
        assert save_errors.stats.failed == 0

        loaded = SampleSet()
        loaded.connect_storage(base_dir, mode=StorageMode.OPEN, storage_scheme=StorageScheme.SET_DIR)
        load_errors = loaded.load_all(strict=True, workers=2, chunk_size=1)
        assert isinstance(load_errors, BatchOperationReport)
        assert load_errors.stats.failed == 0
        assert len(loaded) == 2

    def test_storage_rejects_invalid_chunk_size(self, tmp_path: Path) -> None:
        source = SampleSet()
        sample = self._make_default_sample("chunk")
        source[sample.uid] = sample
        source.connect_storage(
            tmp_path / "chunk_store",
            mode=StorageMode.CREATE,
            storage_scheme=StorageScheme.SET_DIR,
        )
        with pytest.raises(ValueError, match="chunk_size"):
            source.save_all(strict=True, workers=2, chunk_size=0)

    def test_from_storage_supports_workers_on_class_entry(self, tmp_path: Path) -> None:
        source = SampleSet()
        sample = self._make_default_sample("class-entry")
        source[sample.uid] = sample
        base_dir = tmp_path / "class_entry_workers"

        source.save(base_dir, storage_scheme=StorageScheme.SET_DIR, workers=2, chunk_size=1)
        loaded = SampleSet.from_storage(
            base_dir,
            storage_scheme=StorageScheme.SET_DIR,
            workers=2,
            chunk_size=1,
        )

        assert sample.uid in loaded

    def test_load_preserves_existing_samples_when_filter_is_provided(self, tmp_path: Path) -> None:
        source = SampleSet()
        sample_a = self._make_default_sample("A")
        sample_b = self._make_default_sample("B")
        source[sample_a.uid] = sample_a
        source[sample_b.uid] = sample_b
        base_dir = tmp_path / "filtered_load"
        source.save(base_dir, storage_scheme=StorageScheme.SET_DIR)

        existing = self._make_default_sample("existing")
        loaded = SampleSet({existing.uid: existing})

        loaded.load(
            base_dir,
            storage_scheme=StorageScheme.SET_DIR,
            filter=lambda sample: sample.metadata.extra == {"source": "A"},
        )

        assert existing.uid in loaded
        assert sample_a.uid in loaded
        assert sample_b.uid not in loaded

    def test_load_all_uses_instance_strict_by_default_for_uid_conflict(self, tmp_path: Path) -> None:
        source = SampleSet()
        sample = self._make_default_sample("conflict")
        source[sample.uid] = sample
        base_dir = tmp_path / "strict_conflict"
        source.save(base_dir, storage_scheme=StorageScheme.SET_DIR)

        loaded = SampleSet({sample.uid: sample})
        loaded.connect_storage(base_dir, mode=StorageMode.OPEN, storage_scheme=StorageScheme.SET_DIR)

        with pytest.raises(RecoverableIOError, match=sample.uid):
            loaded.load_all()

    def test_load_all_allows_instance_strict_override_for_uid_conflict(self, tmp_path: Path) -> None:
        source = SampleSet()
        sample = self._make_default_sample("conflict-override")
        source[sample.uid] = sample
        base_dir = tmp_path / "strict_conflict_override"
        source.save(base_dir, storage_scheme=StorageScheme.SET_DIR)

        loaded = SampleSet({sample.uid: sample})
        loaded.strict = False
        loaded.connect_storage(base_dir, mode=StorageMode.OPEN, storage_scheme=StorageScheme.SET_DIR)

        errors = loaded.load_all()

        assert sample.uid in errors
        assert loaded[sample.uid] is sample

    def test_get_data_and_get_data_dict_accept_data_category(self) -> None:
        sample_set = SampleSet()
        sample = self._make_default_sample("by-category")
        sample_set[sample.uid] = sample

        accel = sample_set.get_data(sample.uid, DataCategory.TS_ACCEL)
        vel_dict = sample_set.get_data_dict(DataCategory.TS_VEL)

        assert accel is sample.accel
        assert vel_dict == {sample.uid: sample.vel}

    def test_get_data_and_get_data_dict_reject_unknown_slot(self) -> None:
        sample_set = SampleSet()
        sample = self._make_default_sample("unknown-slot")
        sample_set[sample.uid] = sample

        with pytest.raises(KeyError, match="未知样本槽位"):
            sample_set.get_data(sample.uid, "not_a_slot")
        with pytest.raises(KeyError, match="未知样本槽位"):
            sample_set.get_data_dict("not_a_slot")

    def test_update_data_replaces_slot_by_model_category(self) -> None:
        sample_set = SampleSet()
        sample = self._make_default_sample("update-slot")
        sample_set[sample.uid] = sample

        new_vel = sample.accel.calc_vel()  # type: ignore[union-attr]
        sample_set.update_data(sample.uid, new_vel)

        assert sample_set[sample.uid].vel is new_vel

    def test_get_samples_is_inherited_from_sample_set_base(self) -> None:
        assert SampleSet.get_samples is sample_sets_module.SampleSetBase.get_samples

        sample_a = self._make_default_sample("A")
        sample_b = self._make_default_sample("B")
        sample_set = SampleSet({sample_a.uid: sample_a, sample_b.uid: sample_b})

        filtered = sample_set.get_samples(lambda sample: sample.metadata.extra == {"source": "B"})

        assert isinstance(filtered, SampleSet)
        assert list(filtered) == [sample_b.uid]
        assert list(sample_set) == [sample_a.uid, sample_b.uid]

    def test_filter_is_inherited_from_sample_set_base(self) -> None:
        assert SampleSet.filter is sample_sets_module.SampleSetBase.filter

        sample_a = self._make_default_sample("A")
        sample_b = self._make_default_sample("B")
        sample_set = SampleSet({sample_a.uid: sample_a, sample_b.uid: sample_b})

        returned = sample_set.filter(lambda sample: sample.metadata.extra == {"source": "B"})

        assert returned is sample_set
        assert list(sample_set) == [sample_b.uid]


class TestBuildMetadata:
    """build_metadata 通用构建行为。"""

    def test_build_metadata_for_default_metadata(self) -> None:
        metadata = build_metadata(
            Metadata,
            identity={"line": "A"},
            attributes={"sensor": "S1"},
            extra={"note": "demo"},
        )

        assert isinstance(metadata, Metadata)
        assert metadata.identity == {"line": "A"}
        assert metadata.attributes == {"sensor": "S1"}
        assert metadata.extra == {"note": "demo"}

    def test_build_metadata_for_vibration_metadata(self) -> None:
        metadata = build_metadata(
            VibrationTestMetadata,
            case="c1",
            point="pt1",
            instr="instr1",
            dir="Z",
            record="r1",
            timestamp=datetime(2025, 1, 1, 12, 0, 0),
            extra={"note": "demo"},
        )

        assert isinstance(metadata, VibrationTestMetadata)
        assert metadata.case == "c1"
        assert metadata.extra == {"note": "demo"}

    def test_build_metadata_uses_metadata_type_validation(self) -> None:
        with pytest.raises((TypeError, ValueError)):
            build_metadata(VibrationTestMetadata, case="c1")


class TestMetadataMigration:
    """Metadata legacy payload 迁移行为。"""

    def test_generic_metadata_migrates_legacy_payload_to_attributes_first(self) -> None:
        metadata = Metadata(
            line="A",
            channel=1,
            extra={"note": "legacy"},
            schema_name="legacy",
            schema_version=99,
        )

        assert metadata.identity == {}
        assert metadata.attributes == {"line": "A", "channel": 1}
        assert metadata.extra == {"note": "legacy"}

    def test_generic_metadata_preserves_explicit_attributes_when_migrating(self) -> None:
        metadata = Metadata(
            attributes={"sensor": "S1"},
            line="A",
            channel=1,
        )

        assert metadata.attributes == {
            "sensor": "S1",
            "line": "A",
            "channel": 1,
        }


class TestMetadataAliasContracts:
    """Metadata alias 契约。"""

    def test_generic_metadata_alias_defaults_to_uid(self) -> None:
        metadata = Metadata(attributes={"line": "A"})

        assert metadata.alias == metadata.uid

    def test_generic_metadata_from_alias_is_not_supported(self) -> None:
        with pytest.raises(NotImplementedError, match="alias"):
            Metadata.from_alias("demo-alias")

    def test_vibration_test_metadata_can_roundtrip_from_alias(self) -> None:
        alias = "C-A1_R-1_P-A1_I-164_T-20260125050744_D-001"

        metadata = VibrationTestMetadata.from_alias(alias)

        assert metadata.case == "A1"
        assert metadata.record == "1"
        assert metadata.point == "A1"
        assert metadata.instr == "164"
        assert metadata.timestamp == datetime(2026, 1, 25, 5, 7, 44)
        assert metadata.dir == "001"
        assert metadata.alias == alias

    def test_vibration_test_metadata_field_descriptions_are_detailed(self) -> None:
        descriptions = {
            name: VibrationTestMetadata.model_fields[name].description or ""
            for name in ("case", "point", "instr", "dir", "record", "timestamp", "extra")
        }

        assert "工况编号" in descriptions["case"]
        assert "测点编号" in descriptions["point"]
        assert "仪器编号" in descriptions["instr"]
        assert "方向编号" in descriptions["dir"]
        assert "记录编号" in descriptions["record"]
        assert "时间戳" in descriptions["timestamp"]
        assert "附加业务信息" in descriptions["extra"]


class TestSampleIdentityContracts:
    """Sample identity 与 alias 收口行为。"""

    def test_sample_rejects_direct_slot_assignment(self) -> None:
        sample = VibrationTestSample(metadata=_make_vib_meta())
        accel = AccelSeries.from_data(np.random.randn(128) * 0.01, dt=0.002)

        with pytest.raises(AttributeError, match="update_data"):
            sample.accel = accel

    def test_sample_rejects_direct_metadata_assignment(self) -> None:
        sample = VibrationTestSample(metadata=_make_vib_meta())
        replacement = VibrationTestMetadata(
            case="c2",
            point="pt2",
            instr="instr2",
            dir="X",
            record="r2",
            timestamp=datetime(2025, 1, 2, 12, 0, 0),
        )

        with pytest.raises(AttributeError, match="replace_metadata"):
            sample.metadata = replacement

    def test_sample_alias_override_and_force_refresh(self) -> None:
        sample = VibrationTestSample(metadata=_make_vib_meta())
        auto_alias = sample.alias

        sample.set_alias("manual-alias")
        sample.update_metadata(point="pt9")

        assert sample.alias == "manual-alias"

        sample.refresh_alias(force=False)
        assert sample.alias == "manual-alias"

        sample.refresh_alias(force=True)
        assert sample.alias != "manual-alias"
        assert sample.alias != auto_alias
        assert sample.alias == sample.metadata.alias


class TestSampleSetLoadContracts:
    """SampleSet load_mode 与 alias 查询契约。"""

    def test_find_by_alias_and_refresh_aliases_respect_manual_override(self) -> None:
        sample = VibrationTestSample(metadata=_make_vib_meta())
        sample.set_alias("manual-alias")
        sample_set = VibrationTestSampleSet({sample.uid: sample})

        assert sample_set.find_by_alias("manual-alias") is sample
        assert sample_set.get_uid_by_alias("manual-alias") == sample.uid

        sample_set.refresh_aliases(force=False)
        assert sample.alias == "manual-alias"

        sample_set.refresh_aliases(force=True)
        assert sample.alias == sample.metadata.alias

    def test_from_storage_lazy_loads_slot_on_demand(self, tmp_path: Path) -> None:
        sample = Sample(
            metadata=Metadata(extra={"source": "lazy"}),
            accel=AccelSeries.from_data(np.random.randn(128) * 0.01, dt=0.002),
        )
        sample_set = SampleSet({sample.uid: sample})
        base_dir = tmp_path / "lazy_store"
        sample_set.save(base_dir, storage_scheme=StorageScheme.SET_DIR)

        loaded = SampleSet.from_storage(
            base_dir,
            storage_scheme=StorageScheme.SET_DIR,
            load_mode=SampleLoadMode.LAZY,
        )
        lazy_sample = loaded[sample.uid]

        assert lazy_sample.is_loaded("accel") is False
        assert lazy_sample.accel is not None
        assert lazy_sample.is_loaded("accel") is True

    def test_from_storage_metadata_only_requires_explicit_load(self, tmp_path: Path) -> None:
        sample = Sample(
            metadata=Metadata(extra={"source": "metadata-only"}),
            accel=AccelSeries.from_data(np.random.randn(128) * 0.01, dt=0.002),
        )
        sample_set = SampleSet({sample.uid: sample})
        base_dir = tmp_path / "metadata_only_store"
        sample_set.save(base_dir, storage_scheme=StorageScheme.SET_DIR)

        loaded = SampleSet.from_storage(
            base_dir,
            storage_scheme=StorageScheme.SET_DIR,
            load_mode=SampleLoadMode.METADATA_ONLY,
        )
        metadata_only_sample = loaded[sample.uid]

        assert metadata_only_sample.is_loaded("accel") is False
        with pytest.raises(RuntimeError, match="metadata-only"):
            _ = metadata_only_sample.accel

        metadata_only_sample.ensure_loaded(categories=[DataCategory.TS_ACCEL])
        assert metadata_only_sample.accel is not None

    def test_from_storage_uses_categories_as_public_selector(self, tmp_path: Path) -> None:
        sample = Sample(
            metadata=Metadata(extra={"source": "selector"}),
            accel=AccelSeries.from_data(np.random.randn(128) * 0.01, dt=0.002),
        )
        sample_set = SampleSet({sample.uid: sample})
        base_dir = tmp_path / "selector_store"
        sample_set.save(base_dir, storage_scheme=StorageScheme.SET_DIR)

        loaded = SampleSet.from_storage(
            base_dir,
            storage_scheme=StorageScheme.SET_DIR,
            load_mode=SampleLoadMode.EAGER,
            categories=[DataCategory.TS_ACCEL],
        )

        assert loaded[sample.uid].is_loaded("accel") is True

        with pytest.raises(ValueError, match="DataCategory"):
            SampleSet.from_storage(
                base_dir,
                storage_scheme=StorageScheme.SET_DIR,
                load_mode=SampleLoadMode.LAZY,
                categories=[DataCategory.FS_AMP],
            )

        with pytest.raises(TypeError, match="slots"):
            SampleSet.from_storage(  # type: ignore[call-arg]
                base_dir,
                storage_scheme=StorageScheme.SET_DIR,
                load_mode=SampleLoadMode.LAZY,
                slots=["accel"],
            )

        with pytest.raises(TypeError, match="data_categories"):
            SampleSet.from_storage(  # type: ignore[call-arg]
                base_dir,
                storage_scheme=StorageScheme.SET_DIR,
                load_mode=SampleLoadMode.LAZY,
                data_categories=[DataCategory.TS_ACCEL],
            )

        with pytest.raises(ValueError, match="not_a_selector"):
            SampleSet.from_storage(
                base_dir,
                storage_scheme=StorageScheme.SET_DIR,
                load_mode=SampleLoadMode.LAZY,
                categories=["not_a_selector"],
            )

    @pytest.mark.parametrize(
        ("categories", "attr_name"),
        [
            ([DataCategory.FS_SPEC], "freqspec"),
            ([DataCategory.RS_SPEC], "respspec"),
            (["freqspec"], "freqspec"),
            (["respspec"], "respspec"),
        ],
    )
    def test_storage_categories_support_freqspec_and_respspec(
        self,
        tmp_path: Path,
        categories: list[str | DataCategory],
        attr_name: str,
    ) -> None:
        sample = VibrationTestSample(
            metadata=_make_vib_meta(),
            accel=AccelSeries.from_data(np.random.randn(512) * 0.01, dt=0.002),
        )
        sample.calc_freqspec(overwrite=True)
        sample.calc_respspec(overwrite=True)
        source = VibrationTestSampleSet({sample.uid: sample})
        base_dir = tmp_path / f"selector_{attr_name}"

        source.save(base_dir, storage_scheme=StorageScheme.SET_DIR, categories=categories)

        loaded = VibrationTestSampleSet.from_storage(
            base_dir,
            storage_scheme=StorageScheme.SET_DIR,
            load_mode=SampleLoadMode.EAGER,
            categories=categories,
        )

        assert getattr(loaded[sample.uid], attr_name) is not None

    def test_loading_storage_without_saved_spectra_keeps_slots_none(self, tmp_path: Path) -> None:
        sample = VibrationTestSample(
            metadata=_make_vib_meta(),
            accel=AccelSeries.from_data(np.random.randn(256) * 0.01, dt=0.002),
        )
        source = VibrationTestSampleSet({sample.uid: sample})
        base_dir = tmp_path / "no_saved_spectra"
        source.save(base_dir, storage_scheme=StorageScheme.SET_DIR)

        loaded = VibrationTestSampleSet.from_storage(
            base_dir,
            storage_scheme=StorageScheme.SET_DIR,
            load_mode=SampleLoadMode.EAGER,
            categories=[DataCategory.FS_SPEC, DataCategory.RS_SPEC],
        )

        assert loaded[sample.uid].freqspec is None
        assert loaded[sample.uid].respspec is None

    def test_load_all_hydrates_storage_stubs_without_duplicate_uid_error(self, tmp_path: Path) -> None:
        sample = VibrationTestSample(
            metadata=_make_vib_meta(),
            accel=AccelSeries.from_data(np.random.randn(1024) * 0.01, dt=0.002),
        )
        source = VibrationTestSampleSet({sample.uid: sample})
        source.eval_otovl(overwrite=True)
        store_dir = tmp_path / "otovl_store"
        source.save(store_dir, storage_scheme=StorageScheme.SET_DIR)

        loaded = VibrationTestSampleSet.from_storage(
            store_dir,
            storage_scheme=StorageScheme.SET_DIR,
            load_mode=SampleLoadMode.LAZY,
        )

        assert loaded[sample.uid].is_loaded("otovl") is False

        report = loaded.load_all(categories=[DataCategory.OTOVL_EVAL], load_mode=SampleLoadMode.EAGER)

        assert isinstance(report, BatchOperationReport)
        assert report.stats.failed == 0
        assert loaded[sample.uid].otovl is not None


class TestSetSqliteH5Storage:
    def test_set_sqlite_h5_round_trip_lazy_and_metadata_frame(self, tmp_path: Path) -> None:
        sample_a = Sample(
            metadata=Metadata(
                attributes={"line": "A"},
                extra={"source": "sqlite", "batch": "g1"},
            ),
            accel=AccelSeries.from_data(np.random.randn(128) * 0.01, dt=0.002),
        )
        sample_b = Sample(
            metadata=Metadata(
                attributes={"line": "B"},
                extra={"source": "sqlite", "batch": "g2"},
            ),
            accel=AccelSeries.from_data(np.random.randn(96) * 0.01, dt=0.002),
        )
        source = SampleSet({sample_a.uid: sample_a, sample_b.uid: sample_b})
        store_dir = tmp_path / "sqlite_h5_store"

        source.save(store_dir, storage_scheme=StorageScheme.SET_SQLITE_H5)

        assert (store_dir / "index.sqlite").exists()
        assert (store_dir / "payload.h5").exists()

        loaded = SampleSet.from_storage(
            store_dir,
            storage_scheme=StorageScheme.SET_SQLITE_H5,
            load_mode=SampleLoadMode.LAZY,
        )
        lazy_sample = loaded[sample_a.uid]

        assert lazy_sample.is_loaded("accel") is False

        metadata_frame = loaded.get_metadatadf()
        assert set(metadata_frame["attributes@line"]) == {"A", "B"}
        assert set(metadata_frame["extra@source"]) == {"sqlite"}
        assert set(metadata_frame["extra@batch"]) == {"g1", "g2"}

        assert lazy_sample.accel is not None
        assert lazy_sample.is_loaded("accel") is True

    def test_set_sqlite_h5_persists_index_tables(self, tmp_path: Path) -> None:
        sample = Sample(
            metadata=Metadata(
                attributes={"line": "L1"},
                extra={"source": "sqlite-index"},
            ),
            accel=AccelSeries.from_data(np.random.randn(64) * 0.01, dt=0.002),
        )
        source = SampleSet({sample.uid: sample})
        store_dir = tmp_path / "sqlite_index_store"

        source.save(store_dir, storage_scheme=StorageScheme.SET_SQLITE_H5)

        conn = sqlite3.connect(store_dir / "index.sqlite")
        try:
            user_version = conn.execute("PRAGMA user_version").fetchone()[0]
            sample_rows = conn.execute("SELECT uid, alias, payload_id FROM sample").fetchall()
            table_names = {
                str(row[0])
                for row in conn.execute(
                    """
                    SELECT name
                    FROM sqlite_master
                    WHERE type = 'table'
                    """
                ).fetchall()
            }
            metadata_json = conn.execute(
                "SELECT metadata_json FROM sample",
            ).fetchone()[0]
            presence_rows = conn.execute(
                "SELECT slot_name, exists_flag, h5_path FROM sample_slot_presence",
            ).fetchall()
        finally:
            conn.close()

        assert user_version == 2
        assert len(sample_rows) == 1
        assert sample_rows[0][0] == sample.uid
        assert sample_rows[0][1] == sample.alias
        assert "sample_metadata_flat" not in table_names
        assert json.loads(str(metadata_json))["attributes"]["line"] == "L1"
        assert json.loads(str(metadata_json))["extra"]["source"] == "sqlite-index"
        assert presence_rows == [("accel", 1, f"/samples/{sample_rows[0][2]}/slots/accel")]

    def test_set_sqlite_h5_auto_migrates_v1_store_on_open(self, tmp_path: Path) -> None:
        sample = Sample(
            metadata=Metadata(
                attributes={"line": "legacy"},
                extra={"source": "v1"},
            ),
            accel=AccelSeries.from_data(np.random.randn(64) * 0.01, dt=0.002),
        )
        store_dir = tmp_path / "legacy_sqlite_h5"

        sqlite_strategy_module._save_sample_set_legacy_v1(
            SampleSet({sample.uid: sample}),
            store_dir,
            categories=["accel"],
        )

        conn = sqlite3.connect(store_dir / "index.sqlite")
        try:
            table_names_before = {
                str(row[0])
                for row in conn.execute(
                    """
                    SELECT name
                    FROM sqlite_master
                    WHERE type = 'table'
                    """
                ).fetchall()
            }
        finally:
            conn.close()

        assert "sample_metadata_flat" in table_names_before

        loaded = SampleSet.from_storage(
            store_dir,
            storage_scheme=StorageScheme.SET_SQLITE_H5,
            load_mode=SampleLoadMode.LAZY,
        )

        metadata_frame = loaded.metadata_frame()
        assert metadata_frame.loc[0, "attributes@line"] == "legacy"
        assert metadata_frame.loc[0, "extra@source"] == "v1"
        assert loaded[sample.uid].accel is not None

        conn = sqlite3.connect(store_dir / "index.sqlite")
        try:
            user_version = conn.execute("PRAGMA user_version").fetchone()[0]
            table_names_after = {
                str(row[0])
                for row in conn.execute(
                    """
                    SELECT name
                    FROM sqlite_master
                    WHERE type = 'table'
                    """
                ).fetchall()
            }
        finally:
            conn.close()

        assert user_version == 2
        assert "sample_metadata_flat" not in table_names_after

    def test_set_sqlite_h5_keeps_payload_id_stable_after_uid_change(self, tmp_path: Path) -> None:
        sample = Sample(
            metadata=Metadata(
                attributes={"line": "L1"},
                extra={"source": "before"},
            ),
            accel=AccelSeries.from_data(np.random.randn(64) * 0.01, dt=0.002),
        )
        store_dir = tmp_path / "sqlite_uid_change"
        SampleSet({sample.uid: sample}).save(store_dir, storage_scheme=StorageScheme.SET_SQLITE_H5)

        conn = sqlite3.connect(store_dir / "index.sqlite")
        try:
            before_uid, before_payload_id = conn.execute(
                "SELECT uid, payload_id FROM sample",
            ).fetchone()
        finally:
            conn.close()

        loaded = SampleSet.from_storage(
            store_dir,
            storage_scheme=StorageScheme.SET_SQLITE_H5,
            load_mode=SampleLoadMode.METADATA_ONLY,
        )
        loaded_sample = loaded[before_uid]
        loaded_sample.update_metadata(
            attributes={"line": "L2"},
            extra={"source": "after"},
        )
        after_uid = loaded_sample.uid

        loaded.save(store_dir, storage_scheme=StorageScheme.SET_SQLITE_H5)

        conn = sqlite3.connect(store_dir / "index.sqlite")
        try:
            rows = conn.execute("SELECT uid, payload_id FROM sample").fetchall()
        finally:
            conn.close()

        with h5py.File(store_dir / "payload.h5", "r") as h5_file:
            payload_keys = list(h5_file["samples"].keys())

        assert before_uid != after_uid
        assert rows == [(after_uid, before_payload_id)]
        assert payload_keys == [before_payload_id]

    def test_from_storage_infers_set_sqlite_h5_scheme(self, tmp_path: Path) -> None:
        sample = Sample(
            metadata=Metadata(extra={"source": "infer"}),
            accel=AccelSeries.from_data(np.random.randn(32) * 0.01, dt=0.002),
        )
        store_dir = tmp_path / "infer_sqlite_h5"
        SampleSet({sample.uid: sample}).save(store_dir, storage_scheme=StorageScheme.SET_SQLITE_H5)

        loaded = SampleSet.from_storage(
            store_dir,
            load_mode=SampleLoadMode.LAZY,
        )

        assert loaded[sample.uid].metadata.extra["source"] == "infer"

    def test_set_sqlite_h5_scalar_frame_uses_summary_projection_without_payload_reads(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        sample = VibrationTestSample(
            metadata=_make_vib_meta(),
            accel=AccelSeries.from_data(np.random.randn(64) * 0.01, dt=0.002),
            zvl=ZVLEval.from_data(zvl=65.0, aw=0.001),
        )
        store_dir = tmp_path / "sqlite_h5_summary_store"
        VibrationTestSampleSet({sample.uid: sample}).save(store_dir, storage_scheme=StorageScheme.SET_SQLITE_H5)

        loaded = VibrationTestSampleSet.from_storage(
            store_dir,
            storage_scheme=StorageScheme.SET_SQLITE_H5,
            load_mode=SampleLoadMode.LAZY,
        )
        strategy = loaded.storage._sample_storage.strategy

        def _unexpected(*args: object, **kwargs: object) -> object:
            del args, kwargs
            raise AssertionError("摘要层快路径不应触发 payload 读取")

        monkeypatch.setattr(strategy, "load_sample", _unexpected)
        monkeypatch.setattr(strategy, "load_sample_fields", _unexpected)
        monkeypatch.setattr(strategy, "load_many_sample_fields", _unexpected)

        frame = loaded.scalar_frame(
            metadata_fields=["case"],
            data_vars=["zvl"],
            features=["pga"],
        )

        assert frame.loc[0, "case"] == sample.metadata.case
        assert frame.loc[0, "zvl.zvl"] == pytest.approx(65.0)
        assert frame.loc[0, "zvl.aw"] == pytest.approx(0.001)
        assert frame.loc[0, "pga"] == pytest.approx(sample.pga())

    def test_set_sqlite_h5_load_all_reuses_single_payload_open(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        sample_a = Sample(
            metadata=Metadata(extra={"source": "single-open-a"}),
            accel=AccelSeries.from_data(np.random.randn(64) * 0.01, dt=0.002),
        )
        sample_b = Sample(
            metadata=Metadata(extra={"source": "single-open-b"}),
            accel=AccelSeries.from_data(np.random.randn(64) * 0.01, dt=0.002),
        )
        store_dir = tmp_path / "sqlite_h5_single_open"
        SampleSet({sample_a.uid: sample_a, sample_b.uid: sample_b}).save(
            store_dir,
            storage_scheme=StorageScheme.SET_SQLITE_H5,
        )

        opened_modes: list[str] = []
        original_h5_file = sqlite_strategy_module.h5py.File

        def _tracked_h5_file(*args: object, **kwargs: object) -> h5py.File:
            if len(args) >= 2 and isinstance(args[1], str):
                opened_modes.append(args[1])
            elif "mode" in kwargs and isinstance(kwargs["mode"], str):
                opened_modes.append(kwargs["mode"])
            return original_h5_file(*args, **kwargs)

        monkeypatch.setattr(sqlite_strategy_module.h5py, "File", _tracked_h5_file)

        loaded = SampleSet.from_storage(
            store_dir,
            storage_scheme=StorageScheme.SET_SQLITE_H5,
            load_mode=SampleLoadMode.EAGER,
            categories=[DataCategory.TS_ACCEL],
        )

        assert len(loaded) == 2
        assert opened_modes.count("r") == 1

    def test_set_sqlite_h5_writer_blocks_reader_until_write_session_finishes(
        self,
        tmp_path: Path,
    ) -> None:
        sample = Sample(
            metadata=Metadata(extra={"source": "lock-block"}),
            accel=AccelSeries.from_data(np.random.randn(64) * 0.01, dt=0.002),
        )
        store_dir = tmp_path / "sqlite_h5_locking"
        SampleSet({sample.uid: sample}).save(store_dir, storage_scheme=StorageScheme.SET_SQLITE_H5)

        ready_path = tmp_path / "writer_ready.txt"
        writer = _spawn_sqlite_h5_writer_holder(
            store_dir=store_dir,
            ready_path=ready_path,
            sleep_seconds=1.5,
        )
        try:
            deadline = time.perf_counter() + 10.0
            while not ready_path.exists() and time.perf_counter() < deadline:
                time.sleep(0.05)
            assert ready_path.exists(), "writer session 未按时启动"

            started = time.perf_counter()
            loaded = SampleSet.from_storage(
                store_dir,
                storage_scheme=StorageScheme.SET_SQLITE_H5,
                load_mode=SampleLoadMode.EAGER,
                categories=[DataCategory.TS_ACCEL],
            )
            elapsed = time.perf_counter() - started

            assert len(loaded) == 1
            assert elapsed >= 1.0
        finally:
            writer.wait(timeout=10)
            if writer.returncode not in {0, None}:
                raise AssertionError(f"writer holder 子进程失败，退出码={writer.returncode}")

    def test_set_sqlite_h5_reader_does_not_block_reader(
        self,
        tmp_path: Path,
    ) -> None:
        sample = Sample(
            metadata=Metadata(extra={"source": "reader-reader"}),
            accel=AccelSeries.from_data(np.random.randn(64) * 0.01, dt=0.002),
        )
        store_dir = tmp_path / "sqlite_h5_reader_locking"
        SampleSet({sample.uid: sample}).save(store_dir, storage_scheme=StorageScheme.SET_SQLITE_H5)

        ready_path = tmp_path / "reader_ready.txt"
        reader = _spawn_sqlite_h5_reader_holder(
            store_dir=store_dir,
            ready_path=ready_path,
            sleep_seconds=1.5,
        )
        try:
            deadline = time.perf_counter() + 10.0
            while not ready_path.exists() and time.perf_counter() < deadline:
                time.sleep(0.05)
            assert ready_path.exists(), "reader session 未按时启动"

            started = time.perf_counter()
            loaded = SampleSet.from_storage(
                store_dir,
                storage_scheme=StorageScheme.SET_SQLITE_H5,
                load_mode=SampleLoadMode.EAGER,
                categories=[DataCategory.TS_ACCEL],
            )
            elapsed = time.perf_counter() - started

            assert len(loaded) == 1
            assert elapsed < 1.0
        finally:
            reader.wait(timeout=10)
            if reader.returncode not in {0, None}:
                raise AssertionError(f"reader holder 子进程失败，退出码={reader.returncode}")

    def test_set_sqlite_h5_save_all_flushes_sqlite_rows_in_batches(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        sample_a = Sample(
            metadata=Metadata(extra={"source": "batch-a"}),
            accel=AccelSeries.from_data(np.random.randn(64) * 0.01, dt=0.002),
        )
        sample_b = Sample(
            metadata=Metadata(extra={"source": "batch-b"}),
            accel=AccelSeries.from_data(np.random.randn(64) * 0.01, dt=0.002),
        )
        sample_c = Sample(
            metadata=Metadata(extra={"source": "batch-c"}),
            accel=AccelSeries.from_data(np.random.randn(64) * 0.01, dt=0.002),
        )
        store_dir = tmp_path / "sqlite_h5_batch_flush"
        flush_sizes: list[int] = []
        original = sqlite_strategy_module._SetSqliteH5Strategy._flush_transfer_artifacts

        def _tracked(
            self: object,
            conn: sqlite3.Connection,
            artifacts: list[object],
        ) -> dict[str, float]:
            flush_sizes.append(len(artifacts))
            return original(self, conn, artifacts)

        monkeypatch.setattr(
            sqlite_strategy_types_module,
            "_SQLITE_H5_WRITE_FLUSH_BATCH_SIZE",
            2,
        )
        monkeypatch.setattr(
            sqlite_strategy_module._SetSqliteH5Strategy,
            "_flush_transfer_artifacts",
            _tracked,
        )

        SampleSet({sample_a.uid: sample_a, sample_b.uid: sample_b, sample_c.uid: sample_c}).save(
            store_dir,
            storage_scheme=StorageScheme.SET_SQLITE_H5,
        )

        assert flush_sizes == [2, 1]

    def test_set_sqlite_h5_experimental_v2_round_trip_metadata_and_summary(self, tmp_path: Path) -> None:
        sample_a = Sample(
            metadata=Metadata(
                attributes={"line": "A"},
                extra={"source": "sqlite-exp-a"},
            ),
            accel=AccelSeries.from_data(np.random.randn(128) * 0.01, dt=0.002),
        )
        sample_b = Sample(
            metadata=Metadata(
                attributes={"line": "B"},
                extra={"source": "sqlite-exp-b"},
            ),
            accel=AccelSeries.from_data(np.random.randn(96) * 0.01, dt=0.002),
        )
        source = SampleSet({sample_a.uid: sample_a, sample_b.uid: sample_b})
        store_dir = tmp_path / "sqlite_h5_v2_experimental"

        metrics = sqlite_strategy_module._save_sample_set_experimental_v2(
            source,
            store_dir,
            categories=["accel"],
        )
        validation = sqlite_strategy_module._validate_sample_set_experimental_v2(
            SampleSet,
            store_dir,
            categories=["accel"],
            metadata_fields=["attributes@line", "extra@source"],
            features=["pga"],
        )

        assert metrics.sample_count == 2
        assert validation["sample_count"] == 2
        assert set(validation["uids"]) == {sample_a.uid, sample_b.uid}

        metadata_frame = validation["metadata_frame"]
        assert set(metadata_frame["attributes@line"]) == {"A", "B"}
        assert set(metadata_frame["extra@source"]) == {"sqlite-exp-a", "sqlite-exp-b"}

        loaded_fields = validation["loaded_fields"]
        assert isinstance(loaded_fields[sample_a.uid]["accel"], AccelSeries)
        assert isinstance(loaded_fields[sample_b.uid]["accel"], AccelSeries)

        summary_frame = validation["summary_frame"].set_index("uid")
        assert summary_frame.loc[sample_a.uid, "attributes@line"] == "A"
        assert summary_frame.loc[sample_b.uid, "extra@source"] == "sqlite-exp-b"
        assert float(summary_frame.loc[sample_a.uid, "pga"]) == pytest.approx(sample_a.pga())
        assert float(summary_frame.loc[sample_b.uid, "pga"]) == pytest.approx(sample_b.pga())

    def test_set_sqlite_h5_experimental_v2_uses_json_metadata_only(self, tmp_path: Path) -> None:
        sample = Sample(
            metadata=Metadata(
                attributes={"line": "L1"},
                extra={"source": "lookup", "index": 3, "active": True},
            ),
            accel=AccelSeries.from_data(np.random.randn(64) * 0.01, dt=0.002),
        )
        store_dir = tmp_path / "sqlite_h5_v2_lookup"

        sqlite_strategy_module._save_sample_set_experimental_v2(
            SampleSet({sample.uid: sample}),
            store_dir,
            categories=["accel"],
        )

        conn = sqlite3.connect(store_dir / "index.sqlite")
        try:
            tables = {
                str(row[0])
                for row in conn.execute(
                    """
                    SELECT name
                    FROM sqlite_master
                    WHERE type = 'table'
                    """
                ).fetchall()
            }
        finally:
            conn.close()

        assert "sample_metadata_flat_v2" not in tables
        assert "sample_metadata_lookup_v2" not in tables

        validation = sqlite_strategy_module._validate_sample_set_experimental_v2(
            SampleSet,
            store_dir,
            categories=["accel"],
            metadata_fields=["attributes@line", "extra@source", "extra@active"],
            features=["pga"],
        )
        metadata_frame = validation["metadata_frame"]
        assert metadata_frame.loc[0, "attributes@line"] == "L1"
        assert metadata_frame.loc[0, "extra@source"] == "lookup"
        assert bool(metadata_frame.loc[0, "extra@active"]) is True


class TestStorageDetectionAndInspection:
    def _make_default_sample(self, source: str) -> Sample:
        return Sample(
            metadata=Metadata(attributes={"line": source}, extra={"source": source}),
            accel=AccelSeries.from_data(np.random.randn(64) * 0.01, dt=0.002),
        )

    def test_detect_storage_scheme_supports_formal_layouts(self, tmp_path: Path) -> None:
        sample = self._make_default_sample("detect")
        sample_json_path = tmp_path / "sample.json"
        sample_h5_path = tmp_path / "sample.h5"
        set_h5_path = tmp_path / "sample_set.h5"
        sqlite_dir = tmp_path / "sqlite_store"
        attr_table_dir = tmp_path / "attr_table_store"
        set_dir = tmp_path / "set_dir_store"

        sample.save(sample_json_path, storage_scheme=StorageScheme.SAMPLE_JSON)
        sample.save(sample_h5_path, storage_scheme=StorageScheme.SAMPLE_H5)
        SampleSet({sample.uid: sample}).save(set_h5_path, storage_scheme=StorageScheme.SET_H5)
        SampleSet({sample.uid: sample}).save(sqlite_dir, storage_scheme=StorageScheme.SET_SQLITE_H5)
        SampleSet({sample.uid: sample}).save(attr_table_dir, storage_scheme=StorageScheme.SET_ATTR_TABLE)
        SampleSet({sample.uid: sample}).save(set_dir, storage_scheme=StorageScheme.SET_DIR)

        assert dt_storage.detect_storage_scheme(sample_json_path, kind="sample") is StorageScheme.SAMPLE_JSON
        assert dt_storage.detect_storage_scheme(sample_h5_path, kind="sample") is StorageScheme.SAMPLE_H5
        assert dt_storage.detect_storage_scheme(set_h5_path, kind="sample_set") is StorageScheme.SET_H5
        assert dt_storage.detect_storage_scheme(sqlite_dir, kind="sample_set") is StorageScheme.SET_SQLITE_H5
        assert dt_storage.detect_storage_scheme(attr_table_dir, kind="sample_set") is StorageScheme.SET_ATTR_TABLE
        assert dt_storage.detect_storage_scheme(set_dir, kind="sample_set") is StorageScheme.SET_DIR

    def test_inspect_storage_repository_reports_quick_and_deep_validation(self, tmp_path: Path) -> None:
        sample_a = self._make_default_sample("quick")
        sample_b = self._make_default_sample("deep")
        store_dir = tmp_path / "inspect_sqlite_h5"
        SampleSet({sample_a.uid: sample_a, sample_b.uid: sample_b}).save(
            store_dir,
            storage_scheme=StorageScheme.SET_SQLITE_H5,
        )

        quick_report = dt_storage.inspect_storage_repository(store_dir, level="quick")
        deep_report = dt_storage.inspect_storage_repository(store_dir, level="deep")

        assert quick_report.is_valid is True
        assert quick_report.detected_scheme is StorageScheme.SET_SQLITE_H5
        assert quick_report.sample_count == 2
        assert quick_report.issues == ()
        assert deep_report.is_valid is True
        assert deep_report.detected_scheme is StorageScheme.SET_SQLITE_H5
        assert deep_report.sample_count == 2
        assert deep_report.issues == ()

    def test_inspect_storage_repository_reports_invalid_structure(self, tmp_path: Path) -> None:
        broken_dir = tmp_path / "broken_sqlite_h5"
        broken_dir.mkdir()
        sqlite3.connect(broken_dir / "index.sqlite").close()

        report = dt_storage.inspect_storage_repository(
            broken_dir,
            storage_scheme=StorageScheme.SET_SQLITE_H5,
            level="deep",
        )

        assert report.requested_scheme is StorageScheme.SET_SQLITE_H5
        assert report.is_valid is False
        assert report.issues

    def test_load_sample_set_auto_detects_scheme_when_omitted(self, tmp_path: Path) -> None:
        sample = self._make_default_sample("auto-detect")
        set_h5_path = tmp_path / "auto_detect.h5"
        SampleSet({sample.uid: sample}).save(set_h5_path, storage_scheme=StorageScheme.SET_H5)

        loaded = dt_storage.load_sample_set(set_h5_path, domain=dt_storage.SampleDomain.DEFAULT)

        assert isinstance(loaded, SampleSet)
        assert sample.uid in loaded

    def test_load_sample_set_rejects_explicit_scheme_mismatch(self, tmp_path: Path) -> None:
        sample = self._make_default_sample("mismatch")
        set_h5_path = tmp_path / "mismatch.h5"
        SampleSet({sample.uid: sample}).save(set_h5_path, storage_scheme=StorageScheme.SET_H5)

        with pytest.raises(ValueError, match="storage_scheme"):
            dt_storage.load_sample_set(
                set_h5_path,
                domain=dt_storage.SampleDomain.DEFAULT,
                scheme=StorageScheme.SET_DIR,
            )


class TestSampleSetCompare:
    def _make_sample(self, point: str, *, scale: float = 1.0) -> VibrationTestSample:
        accel = AccelSeries.from_data(np.array([0.0, 0.05, -0.03, 0.04]) * scale, dt=0.01)
        return VibrationTestSample(
            metadata=VibrationTestMetadata(
                case="case-a",
                point=point,
                instr=f"instr-{point}",
                dir="Z",
                record="r1",
                timestamp="2026-03-30 08:00:00",
            ),
            accel=accel,
            zvl=ZVLEval.from_data(zvl=65.0 * scale, aw=0.001 * scale),
        )

    def test_compare_with_reports_uid_metadata_and_scalar_diffs(self) -> None:
        left_a = self._make_sample("A", scale=1.0)
        left_b = self._make_sample("B", scale=1.0)
        right_a = self._make_sample("A", scale=1.1)
        right_a.update_metadata(extra={"tag": "changed"})
        right_c = self._make_sample("C", scale=1.0)

        left = VibrationTestSampleSet({left_a.uid: left_a, left_b.uid: left_b})
        right = VibrationTestSampleSet({right_a.uid: right_a, right_c.uid: right_c})

        report = left.compare_with(
            right,
            metadata_fields=["extra@tag"],
            data_vars=["zvl"],
            features=["pga"],
            atol=1e-9,
            rtol=1e-9,
        )

        assert report.same_sample_type is True
        assert report.left_only_uids == (left_b.uid,)
        assert report.right_only_uids == (right_c.uid,)
        assert report.common_uids == (left_a.uid,)
        assert not report.metadata_diff.empty
        assert not report.scalar_diff.empty
        assert report.presence_diff.empty

    def test_compare_with_respects_tolerance_and_missing_values(self) -> None:
        left_sample = self._make_sample("T", scale=1.0)
        right_sample = self._make_sample("T", scale=1.0)
        right_sample.update_data(zvl=ZVLEval.from_data(zvl=65.0 + 1e-8, aw=0.001 + 1e-8))

        left = VibrationTestSampleSet({left_sample.uid: left_sample})
        right = VibrationTestSampleSet({right_sample.uid: right_sample})

        report = left.compare_with(
            right,
            data_vars=["zvl"],
            rtol=1e-5,
            atol=1e-5,
        )
        assert report.scalar_diff.empty

        right_sample.update_data(zvl=None)
        report_missing = left.compare_with(right, data_vars=["zvl"])
        assert not report_missing.presence_diff.empty
        assert report_missing.scalar_diff.empty

    def test_compare_with_delegates_to_internal_compare_helper(self, monkeypatch: pytest.MonkeyPatch) -> None:
        left_sample = self._make_sample("L", scale=1.0)
        right_sample = self._make_sample("L", scale=1.1)
        left = VibrationTestSampleSet({left_sample.uid: left_sample})
        right = VibrationTestSampleSet({right_sample.uid: right_sample})

        def _delegated(*args: object, **kwargs: object) -> SampleSetComparisonReport:
            del args, kwargs
            raise RuntimeError("delegated-compare")

        monkeypatch.setattr(sample_sets_module, "compare_sample_sets", _delegated, raising=False)

        with pytest.raises(RuntimeError, match="delegated-compare"):
            left.compare_with(right, data_vars=["zvl"])

    def test_compare_private_helpers_only_exist_in_internal_module(self) -> None:
        helper_names = (
            "_compare_metadata_rows",
            "_sample_field_present",
            "_compare_presence_rows",
            "_compare_scalar_rows",
        )

        for helper_name in helper_names:
            assert helper_name not in sample_sets_module.SampleSetBase.__dict__

        exported_names = {
            "compare_metadata_rows",
            "sample_field_present",
            "compare_presence_rows",
            "compare_scalar_rows",
        }
        for helper_name in exported_names:
            assert hasattr(sample_set_compare_module, helper_name)


@pytest.mark.parametrize(
    ("method_name", "helper_name", "args", "kwargs"),
    [
        ("scalar_frame", "build_scalar_frame", (), {"data_vars": ["zvl"]}),
        ("series_frame", "build_series_frame", ("accel",), {}),
        ("peaks_frame", "build_peaks_frame", (), {}),
    ],
)
def test_sample_set_view_methods_delegate_to_internal_helpers(
    monkeypatch: pytest.MonkeyPatch,
    method_name: str,
    helper_name: str,
    args: tuple[object, ...],
    kwargs: dict[str, object],
) -> None:
    sample = VibrationTestSample(
        metadata=_make_vib_meta(),
        accel=AccelSeries.from_data(np.random.randn(64) * 0.01, dt=0.002),
        zvl=ZVLEval.from_data(zvl=65.0, aw=0.001),
    )
    sample_set = VibrationTestSampleSet({sample.uid: sample})

    def _delegated(*inner_args: object, **inner_kwargs: object) -> object:
        del inner_args, inner_kwargs
        raise RuntimeError(f"delegated-{method_name}")

    monkeypatch.setattr(sample_sets_module, helper_name, _delegated, raising=False)

    with pytest.raises(RuntimeError, match=f"delegated-{method_name}"):
        getattr(sample_set, method_name)(*args, **kwargs)


@pytest.mark.parametrize(
    ("storage_scheme", "target_name"),
    [
        (StorageScheme.SET_DIR, "lazy_fields_sample_dir"),
        (StorageScheme.SET_H5, "lazy_fields_set_h5.h5"),
        (StorageScheme.SET_SQLITE_H5, "lazy_fields_sqlite_h5"),
    ],
)
def test_lazy_slot_access_uses_field_level_loader(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    storage_scheme: StorageScheme,
    target_name: str,
) -> None:
    accel = AccelSeries.from_data(np.random.randn(128) * 0.01, dt=0.002)
    sample = Sample(
        metadata=Metadata(extra={"source": storage_scheme.value}),
        accel=accel,
        vel=accel.calc_vel(),
    )
    store_path = tmp_path / target_name
    SampleSet({sample.uid: sample}).save(store_path, storage_scheme=storage_scheme)

    loaded = SampleSet.from_storage(
        store_path,
        storage_scheme=storage_scheme,
        load_mode=SampleLoadMode.LAZY,
    )
    lazy_sample = loaded[sample.uid]
    strategy = loaded.storage._sample_storage.strategy

    def _unexpected(*args: object, **kwargs: object) -> object:
        del args, kwargs
        raise AssertionError("LAZY 单槽位补载不应回退到整样本重建")

    monkeypatch.setattr(strategy, "load_sample", _unexpected)

    assert lazy_sample.is_loaded("accel") is False
    assert lazy_sample.is_loaded("vel") is False
    assert lazy_sample.accel is not None
    assert lazy_sample.is_loaded("accel") is True
    assert lazy_sample.is_loaded("vel") is False


@pytest.mark.parametrize(
    ("storage_scheme", "target_name"),
    [
        (StorageScheme.SET_DIR, "metadata_fields_sample_dir"),
        (StorageScheme.SET_H5, "metadata_fields_set_h5.h5"),
        (StorageScheme.SET_SQLITE_H5, "metadata_fields_sqlite_h5"),
    ],
)
def test_metadata_only_ensure_loaded_uses_field_level_loader(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    storage_scheme: StorageScheme,
    target_name: str,
) -> None:
    accel = AccelSeries.from_data(np.random.randn(128) * 0.01, dt=0.002)
    sample = Sample(
        metadata=Metadata(extra={"source": storage_scheme.value}),
        accel=accel,
        vel=accel.calc_vel(),
    )
    store_path = tmp_path / target_name
    SampleSet({sample.uid: sample}).save(store_path, storage_scheme=storage_scheme)

    loaded = SampleSet.from_storage(
        store_path,
        storage_scheme=storage_scheme,
        load_mode=SampleLoadMode.METADATA_ONLY,
    )
    metadata_sample = loaded[sample.uid]
    strategy = loaded.storage._sample_storage.strategy

    def _unexpected(*args: object, **kwargs: object) -> object:
        del args, kwargs
        raise AssertionError("metadata-only 显式补载不应回退到整样本重建")

    monkeypatch.setattr(strategy, "load_sample", _unexpected)

    metadata_sample.ensure_loaded(categories=[DataCategory.TS_ACCEL])

    assert metadata_sample.accel is not None
    assert metadata_sample.is_loaded("accel") is True
    assert metadata_sample.is_loaded("vel") is False


def test_prefetch_uses_batch_field_loader_for_lazy_sample_set(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sample_a = Sample(
        metadata=Metadata(extra={"source": "batch-a"}),
        accel=AccelSeries.from_data(np.random.randn(64) * 0.01, dt=0.002),
    )
    sample_b = Sample(
        metadata=Metadata(extra={"source": "batch-b"}),
        accel=AccelSeries.from_data(np.random.randn(64) * 0.01, dt=0.002),
    )
    store_dir = tmp_path / "batch_prefetch_sqlite_h5"
    SampleSet({sample_a.uid: sample_a, sample_b.uid: sample_b}).save(
        store_dir,
        storage_scheme=StorageScheme.SET_SQLITE_H5,
    )

    loaded = SampleSet.from_storage(
        store_dir,
        storage_scheme=StorageScheme.SET_SQLITE_H5,
        load_mode=SampleLoadMode.LAZY,
    )
    original = loaded.storage.load_many_fields
    calls: list[tuple[tuple[str, ...], tuple[str, ...]]] = []

    def _tracked(uids: list[str], categories: list[str]) -> dict[str, dict[str, object]]:
        calls.append((tuple(uids), tuple(categories)))
        return original(uids, categories)

    monkeypatch.setattr(loaded.storage, "load_many_fields", _tracked)

    loaded.prefetch(categories=[DataCategory.TS_ACCEL])

    assert len(calls) == 1
    assert set(calls[0][0]) == {sample_a.uid, sample_b.uid}
    assert calls[0][1] == ("accel",)


class TestSampleSetConvertStorage:
    def _make_sample(self, source: str) -> Sample:
        accel = AccelSeries.from_data(np.random.randn(128) * 0.01, dt=0.002)
        return Sample(
            metadata=Metadata(
                attributes={"line": source},
                extra={"source": source},
            ),
            accel=accel,
            vel=accel.calc_vel(),
        )

    @staticmethod
    def _target_path(tmp_path: Path, scheme: StorageScheme) -> Path:
        if scheme is StorageScheme.SET_H5:
            return tmp_path / f"{scheme.value}.h5"
        return tmp_path / scheme.value

    @pytest.mark.parametrize(
        "target_scheme",
        [
            StorageScheme.SAMPLE_JSON,
            StorageScheme.SAMPLE_H5,
            StorageScheme.SET_H5,
            StorageScheme.SET_SQLITE_H5,
            StorageScheme.SET_ATTR_TABLE,
            StorageScheme.SET_DIR,
        ],
    )
    def test_convert_storage_supports_formal_sample_set_schemes(
        self,
        tmp_path: Path,
        target_scheme: StorageScheme,
    ) -> None:
        sample = self._make_sample("formal")
        source_dir = tmp_path / "source_store"
        SampleSet({sample.uid: sample}).save(source_dir, storage_scheme=StorageScheme.SET_DIR)

        loaded = SampleSet.from_storage(
            source_dir,
            storage_scheme=StorageScheme.SET_DIR,
            load_mode=SampleLoadMode.LAZY,
        )
        assert loaded[sample.uid].is_loaded("vel") is False

        target_path = self._target_path(tmp_path, target_scheme)
        loaded.convert_storage(target_path, storage_scheme=target_scheme)

        assert loaded.storage is not None
        assert loaded.storage.storage_scheme is target_scheme

        converted = SampleSet.from_storage(
            target_path,
            storage_scheme=target_scheme,
            load_mode=SampleLoadMode.EAGER,
        )

        assert sample.uid in converted
        assert converted[sample.uid].accel is not None
        assert converted[sample.uid].vel is not None

    @pytest.mark.parametrize(
        ("method_name", "helper_name", "args", "kwargs"),
        [
            (
                "connect_storage",
                "connect_storage_sample_set",
                (Path("delegated-connect"),),
                {"mode": StorageMode.CREATE, "storage_scheme": StorageScheme.SET_DIR},
            ),
            ("save", "save_sample_set", (Path("delegated-save"),), {"storage_scheme": StorageScheme.SET_DIR}),
            ("load", "load_sample_set", (Path("delegated-load"),), {"storage_scheme": StorageScheme.SET_DIR}),
            (
                "convert_storage",
                "convert_storage_sample_set",
                (Path("delegated-convert"),),
                {"storage_scheme": StorageScheme.SET_H5},
            ),
        ],
    )
    def test_storage_entrypoints_delegate_to_internal_helpers(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        method_name: str,
        helper_name: str,
        args: tuple[object, ...],
        kwargs: dict[str, object],
    ) -> None:
        sample = self._make_sample("delegate-storage")
        sample_set = SampleSet({sample.uid: sample})
        relocated_args = tuple(
            tmp_path / arg.name if isinstance(arg, Path) and not arg.is_absolute() else arg for arg in args
        )

        def _delegated(*inner_args: object, **inner_kwargs: object) -> SampleSet:
            del inner_args, inner_kwargs
            raise RuntimeError(f"delegated-{method_name}")

        monkeypatch.setattr(sample_sets_module, helper_name, _delegated, raising=False)

        with pytest.raises(RuntimeError, match=f"delegated-{method_name}"):
            getattr(sample_set, method_name)(*relocated_args, **kwargs)

    def test_save_all_supports_progress_callback(self, tmp_path: Path) -> None:
        sample_a = self._make_sample("save-progress-a")
        sample_b = self._make_sample("save-progress-b")
        source = SampleSet({sample_a.uid: sample_a, sample_b.uid: sample_b})
        store_dir = tmp_path / "save_progress_store"
        progress_updates: list[tuple[int, int]] = []

        source.connect_storage(
            store_dir,
            mode=StorageMode.CREATE,
            storage_scheme=StorageScheme.SET_DIR,
        )
        report = source.save_all(
            progress_callback=lambda completed, total: progress_updates.append((completed, total)),
            show_progress=False,
        )

        assert report.stats.failed == 0
        assert progress_updates == [(1, 2), (2, 2)]

    def test_convert_storage_supports_progress_callback(self, tmp_path: Path) -> None:
        sample_a = self._make_sample("convert-progress-a")
        sample_b = self._make_sample("convert-progress-b")
        source_dir = tmp_path / "convert_progress_source"
        target_path = tmp_path / "convert_progress_target.h5"
        progress_updates: list[tuple[int, int]] = []
        SampleSet({sample_a.uid: sample_a, sample_b.uid: sample_b}).save(
            source_dir,
            storage_scheme=StorageScheme.SET_DIR,
        )

        loaded = SampleSet.from_storage(
            source_dir,
            storage_scheme=StorageScheme.SET_DIR,
            load_mode=SampleLoadMode.LAZY,
        )
        loaded.convert_storage(
            target_path,
            storage_scheme=StorageScheme.SET_H5,
            progress_callback=lambda completed, total: progress_updates.append((completed, total)),
            show_progress=False,
        )

        assert progress_updates == [(1, 2), (2, 2)]

    def test_convert_storage_does_not_call_sample_model_copy(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        sample = self._make_sample("no-deep-copy")
        source_dir = tmp_path / "source_no_deep_copy"
        target_path = tmp_path / "target_no_deep_copy.h5"
        SampleSet({sample.uid: sample}).save(source_dir, storage_scheme=StorageScheme.SET_DIR)

        loaded = SampleSet.from_storage(
            source_dir,
            storage_scheme=StorageScheme.SET_DIR,
            load_mode=SampleLoadMode.LAZY,
        )

        def _unexpected(*args: object, **kwargs: object) -> object:
            del args, kwargs
            raise AssertionError("convert_storage 不应再调用 sample.model_copy(deep=True)")

        monkeypatch.setattr(Sample, "model_copy", _unexpected)

        loaded.convert_storage(target_path, storage_scheme=StorageScheme.SET_H5)

    def test_convert_storage_from_lazy_sqlite_source_prefetches_fields_in_batch(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        sample_a = self._make_sample("sqlite-batch-a")
        sample_b = self._make_sample("sqlite-batch-b")
        source_dir = tmp_path / "source_sqlite_batch"
        target_dir = tmp_path / "target_sqlite_batch"
        SampleSet({sample_a.uid: sample_a, sample_b.uid: sample_b}).save(
            source_dir,
            storage_scheme=StorageScheme.SET_SQLITE_H5,
        )

        loaded = SampleSet.from_storage(
            source_dir,
            storage_scheme=StorageScheme.SET_SQLITE_H5,
            load_mode=SampleLoadMode.LAZY,
        )
        calls: list[tuple[tuple[str, ...], tuple[str, ...]]] = []
        original = loaded.storage.load_many_fields

        def _tracked(uids: list[str], categories: list[str]) -> dict[str, dict[str, object]]:
            calls.append((tuple(uids), tuple(categories)))
            return original(uids, categories)

        monkeypatch.setattr(loaded.storage, "load_many_fields", _tracked)

        loaded.convert_storage(target_dir, storage_scheme=StorageScheme.SET_DIR)

        assert len(calls) == 1
        assert set(calls[0][0]) == {sample_a.uid, sample_b.uid}
        assert {"accel", "vel"}.issubset(set(calls[0][1]))

    @pytest.mark.parametrize(
        ("target_scheme", "strategy_cls"),
        [
            (StorageScheme.SET_H5, strategy_impl_module._SetH5Strategy),
            (StorageScheme.SET_SQLITE_H5, sqlite_strategy_module._SetSqliteH5Strategy),
        ],
    )
    def test_convert_storage_uses_target_write_session(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        target_scheme: StorageScheme,
        strategy_cls: type[object],
    ) -> None:
        sample = self._make_sample(f"writer-{target_scheme.value}")
        source_dir = tmp_path / f"source_{target_scheme.value}"
        target_path = self._target_path(tmp_path, target_scheme)
        SampleSet({sample.uid: sample}).save(source_dir, storage_scheme=StorageScheme.SET_DIR)

        loaded = SampleSet.from_storage(
            source_dir,
            storage_scheme=StorageScheme.SET_DIR,
            load_mode=SampleLoadMode.LAZY,
        )
        calls: list[str] = []
        original = strategy_cls.write_session

        def _tracked(self: object) -> object:
            calls.append(target_scheme.value)
            return original(self)

        monkeypatch.setattr(strategy_cls, "write_session", _tracked)

        loaded.convert_storage(target_path, storage_scheme=target_scheme)

        assert calls == [target_scheme.value]

    def test_convert_storage_to_sqlite_target_does_not_pollute_source_payload_id(
        self,
        tmp_path: Path,
    ) -> None:
        sample_a = self._make_sample("payload-a")
        sample_b = self._make_sample("payload-b")
        source_dir = tmp_path / "source_payload_clean"
        target_dir = tmp_path / "target_payload_clean"
        SampleSet({sample_a.uid: sample_a, sample_b.uid: sample_b}).save(
            source_dir,
            storage_scheme=StorageScheme.SET_DIR,
        )

        loaded = SampleSet.from_storage(source_dir, storage_scheme=StorageScheme.SET_DIR)
        original_payload_id = loaded[sample_a.uid]._storage_payload_id

        loaded.convert_storage(
            target_dir,
            storage_scheme=StorageScheme.SET_SQLITE_H5,
            filter=lambda sample: sample.metadata.extra["source"] == "payload-a",
        )

        assert loaded[sample_a.uid]._storage_payload_id == original_payload_id
        assert loaded.storage is not None
        assert loaded.storage.storage_scheme is StorageScheme.SET_DIR

    def test_storage_progress_default_follows_logging_console_output(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        sample = self._make_sample("progress-default")
        source = SampleSet({sample.uid: sample})
        store_dir = tmp_path / "progress_default_store"
        source.connect_storage(
            store_dir,
            mode=StorageMode.CREATE,
            storage_scheme=StorageScheme.SET_DIR,
        )

        created_bars: list[dict[str, object]] = []

        class _FakeTqdm:
            def __init__(self, *args: object, **kwargs: object) -> None:
                del args
                created_bars.append(dict(kwargs))

            def update(self, _step: int) -> None:
                return None

            def close(self) -> None:
                return None

        class _FakeProvider:
            def __init__(self, config: dt_logging.LoggingConfig) -> None:
                self.config = config

        monkeypatch.setattr(sample_set_storage_module, "tqdm", _FakeTqdm)
        monkeypatch.setattr(
            sample_set_storage_module,
            "get_log_provider",
            lambda: _FakeProvider(
                dt_logging.LoggingConfig(
                    provider="loguru",
                    mode=dt_logging.LoggingMode.SINGLE_FILE,
                    log_file=tmp_path / "logs" / "file.log",
                    mirror_to_console=False,
                )
            ),
        )

        source.storage.save_all(show_progress=None)
        assert created_bars == []

        monkeypatch.setattr(
            sample_set_storage_module,
            "get_log_provider",
            lambda: _FakeProvider(
                dt_logging.LoggingConfig(
                    provider="loguru",
                    mode=dt_logging.LoggingMode.SINGLE_FILE,
                    log_file=tmp_path / "logs" / "console.log",
                    mirror_to_console=True,
                )
            ),
        )

        source.storage.save_all(show_progress=None)

        assert len(created_bars) == 1
        assert created_bars[0]["desc"] == "批量保存"
        assert created_bars[0]["leave"] is False
        assert created_bars[0]["disable"] is False

    def test_convert_storage_full_conversion_rebinds_followup_saves(self, tmp_path: Path) -> None:
        sample = self._make_sample("rebind")
        source_dir = tmp_path / "source_rebind"
        target_path = tmp_path / "converted_rebind.h5"
        SampleSet({sample.uid: sample}).save(source_dir, storage_scheme=StorageScheme.SET_DIR)

        loaded = SampleSet.from_storage(source_dir, storage_scheme=StorageScheme.SET_DIR)
        loaded.convert_storage(target_path, storage_scheme=StorageScheme.SET_H5)
        loaded[sample.uid].set_alias("converted-alias")
        loaded.save_all()

        source_loaded = SampleSet.from_storage(source_dir, storage_scheme=StorageScheme.SET_DIR)
        converted_loaded = SampleSet.from_storage(target_path, storage_scheme=StorageScheme.SET_H5)

        assert source_loaded[sample.uid].alias != "converted-alias"
        assert converted_loaded[sample.uid].alias == "converted-alias"

    def test_convert_storage_partial_conversion_keeps_original_binding(self, tmp_path: Path) -> None:
        sample_a = self._make_sample("A")
        sample_b = self._make_sample("B")
        source_dir = tmp_path / "source_partial"
        target_path = tmp_path / "partial_target.h5"
        SampleSet({sample_a.uid: sample_a, sample_b.uid: sample_b}).save(
            source_dir,
            storage_scheme=StorageScheme.SET_DIR,
        )

        loaded = SampleSet.from_storage(source_dir, storage_scheme=StorageScheme.SET_DIR)
        loaded.convert_storage(
            target_path,
            storage_scheme=StorageScheme.SET_H5,
            categories=[DataCategory.TS_ACCEL],
            filter=lambda sample: sample.metadata.extra["source"] == "A",
        )

        assert loaded.storage is not None
        assert loaded.storage.storage_scheme is StorageScheme.SET_DIR
        assert loaded.storage.base_dir == source_dir.resolve()

        converted = SampleSet.from_storage(
            target_path,
            storage_scheme=StorageScheme.SET_H5,
            load_mode=SampleLoadMode.EAGER,
        )

        assert sample_a.uid in converted
        assert sample_b.uid not in converted
        assert converted[sample_a.uid].accel is not None
        assert converted[sample_a.uid].vel is None

    def test_convert_storage_from_lazy_view_prefetches_storable_slots(self, tmp_path: Path) -> None:
        sample = self._make_sample("lazy-prefetch")
        source_dir = tmp_path / "source_lazy_prefetch"
        target_dir = tmp_path / "target_lazy_prefetch"
        SampleSet({sample.uid: sample}).save(source_dir, storage_scheme=StorageScheme.SET_SQLITE_H5)

        loaded = SampleSet.from_storage(
            source_dir,
            storage_scheme=StorageScheme.SET_SQLITE_H5,
            load_mode=SampleLoadMode.LAZY,
        )
        assert loaded[sample.uid].is_loaded("accel") is False
        assert loaded[sample.uid].is_loaded("vel") is False

        loaded.convert_storage(target_dir, storage_scheme=StorageScheme.SET_DIR)

        converted = SampleSet.from_storage(
            target_dir,
            storage_scheme=StorageScheme.SET_DIR,
            load_mode=SampleLoadMode.EAGER,
        )

        assert converted[sample.uid].accel is not None
        assert converted[sample.uid].vel is not None

    def test_convert_storage_rejects_equivalent_target(self, tmp_path: Path) -> None:
        sample = self._make_sample("same-target")
        source_dir = tmp_path / "same_target_store"
        SampleSet({sample.uid: sample}).save(source_dir, storage_scheme=StorageScheme.SET_DIR)

        loaded = SampleSet.from_storage(source_dir, storage_scheme=StorageScheme.SET_DIR)

        with pytest.raises(ValueError, match="目标路径"):
            loaded.convert_storage(source_dir, storage_scheme=StorageScheme.SET_DIR)

    def test_convert_storage_requires_source_binding_for_unloaded_samples(self, tmp_path: Path) -> None:
        sample = self._make_sample("missing-source")
        source_dir = tmp_path / "missing_source_store"
        target_path = tmp_path / "missing_source_target.h5"
        SampleSet({sample.uid: sample}).save(source_dir, storage_scheme=StorageScheme.SET_DIR)

        loaded = SampleSet.from_storage(
            source_dir,
            storage_scheme=StorageScheme.SET_DIR,
            load_mode=SampleLoadMode.METADATA_ONLY,
        )
        loaded.storage = None

        with pytest.raises(RuntimeError, match="源存储连接"):
            loaded.convert_storage(target_path, storage_scheme=StorageScheme.SET_H5)

    def test_convert_storage_supports_fully_loaded_in_memory_sample_set(self, tmp_path: Path) -> None:
        sample = self._make_sample("memory-only")
        sample_set = SampleSet({sample.uid: sample})
        target_path = tmp_path / "memory_only_target.h5"

        sample_set.convert_storage(target_path, storage_scheme=StorageScheme.SET_H5)

        loaded = SampleSet.from_storage(target_path, storage_scheme=StorageScheme.SET_H5)
        assert sample.uid in loaded
        assert loaded[sample.uid].vel is not None

    def test_connect_storage_logs_detailed_summary(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        sample_set = SampleSet()
        store_dir = tmp_path / "connect_log_store"

        with caplog.at_level("INFO", logger="dyntool.infrastructure.sample_storage"):
            sample_set.connect_storage(
                store_dir,
                mode=StorageMode.CREATE,
                storage_scheme=StorageScheme.SET_H5,
                data_options={
                    "h5_compression": "gzip",
                    "h5_compression_level": 4,
                },
                set_filename="bundle.h5",
            )

        messages = [record.getMessage() for record in caplog.records]
        assert any("connect sample-set storage request:" in message for message in messages)
        assert any("mode=create" in message for message in messages)
        assert any("storage_scheme=SET_H5" in message for message in messages)
        assert any("set_filename=bundle.h5" in message for message in messages)
        assert any("h5_compression=gzip" in message for message in messages)
        assert any("connect sample-set storage ready:" in message for message in messages)
