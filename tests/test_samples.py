"""样本与样本集基本行为测试。"""

from datetime import datetime
from pathlib import Path
import sqlite3

import h5py
import numpy as np
import pytest

from dyntool.domain.constants import DataCategory
from dyntool.domain.metadata import (
    Metadata,
    VibrationTestMetadata,
)
from dyntool.domain.models import AccelSeries, FreqSpec, RespSpec
from dyntool.domain.samples import default as default_samples_module
from dyntool.domain.samples import sets as sample_sets_module
from dyntool.domain.samples import vibration_test as vibration_samples_module
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
        source.connect_storage(base_dir, mode=StorageMode.CREATE, storage_scheme=StorageScheme.SAMPLE_DIR)
        save_report = source.save_all()

        loaded = VibrationTestSampleSet()
        loaded.connect_storage(base_dir, mode=StorageMode.OPEN, storage_scheme=StorageScheme.SAMPLE_DIR)
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
        sample_set.save(store_dir, storage_scheme=StorageScheme.SAMPLE_DIR)
        old_uid = sample.uid

        sample.metadata.point = "pt-updated"

        assert sample_set.storage is not None
        assert getattr(sample_set, "storage_dirty", False) is True

        loaded_before_cleanup = VibrationTestSampleSet.from_storage(
            store_dir,
            storage_scheme=StorageScheme.SAMPLE_DIR,
        )
        assert old_uid in loaded_before_cleanup

        sample_set.save_all()
        sample_set.organize_storage()

        loaded_after_cleanup = VibrationTestSampleSet.from_storage(
            store_dir,
            storage_scheme=StorageScheme.SAMPLE_DIR,
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
        source.save(csv_dir, storage_scheme=StorageScheme.SAMPLE_DIR)
        source.save(h5_path, storage_scheme=StorageScheme.SET_H5)

        from_csv = VibrationTestSampleSet.from_storage(
            csv_dir,
            storage_scheme=StorageScheme.SAMPLE_DIR,
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
        sample_set.save(csv_dir, storage_scheme=StorageScheme.SAMPLE_DIR)
        sample_set.save(h5_path, storage_scheme=StorageScheme.SET_H5)

        from_csv_set = SampleSet.from_storage(
            csv_dir,
            storage_scheme=StorageScheme.SAMPLE_DIR,
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
        source.save(csv_dir, storage_scheme=StorageScheme.SAMPLE_DIR)
        source.save(h5_path, storage_scheme=StorageScheme.SET_H5)

        from_csv = SampleSet.from_storage(
            csv_dir,
            storage_scheme=StorageScheme.SAMPLE_DIR,
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
            StorageScheme.SAMPLE_DIR,
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
            storage_scheme=StorageScheme.ATTR_TABLE,
            data_options={"attr_data_format": attr_data_format.value},
        )
        source.save_all()

        loaded = SampleSet.from_storage(
            base_dir,
            storage_scheme=StorageScheme.ATTR_TABLE,
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
            storage_scheme=StorageScheme.SAMPLE_DIR,
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
            storage_scheme=StorageScheme.SAMPLE_DIR,
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
        source.connect_storage(base_dir, mode=StorageMode.CREATE, storage_scheme=StorageScheme.SAMPLE_DIR)
        save_errors = source.save_all(strict=True, workers=2, chunk_size=1)
        assert isinstance(save_errors, BatchOperationReport)
        assert save_errors.stats.failed == 0

        loaded = SampleSet()
        loaded.connect_storage(base_dir, mode=StorageMode.OPEN, storage_scheme=StorageScheme.SAMPLE_DIR)
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
            storage_scheme=StorageScheme.SAMPLE_DIR,
        )
        with pytest.raises(ValueError, match="chunk_size"):
            source.save_all(strict=True, workers=2, chunk_size=0)

    def test_from_storage_supports_workers_on_class_entry(self, tmp_path: Path) -> None:
        source = SampleSet()
        sample = self._make_default_sample("class-entry")
        source[sample.uid] = sample
        base_dir = tmp_path / "class_entry_workers"

        source.save(base_dir, storage_scheme=StorageScheme.SAMPLE_DIR, workers=2, chunk_size=1)
        loaded = SampleSet.from_storage(
            base_dir,
            storage_scheme=StorageScheme.SAMPLE_DIR,
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
        source.save(base_dir, storage_scheme=StorageScheme.SAMPLE_DIR)

        existing = self._make_default_sample("existing")
        loaded = SampleSet({existing.uid: existing})

        loaded.load(
            base_dir,
            storage_scheme=StorageScheme.SAMPLE_DIR,
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
        source.save(base_dir, storage_scheme=StorageScheme.SAMPLE_DIR)

        loaded = SampleSet({sample.uid: sample})
        loaded.connect_storage(base_dir, mode=StorageMode.OPEN, storage_scheme=StorageScheme.SAMPLE_DIR)

        with pytest.raises(RecoverableIOError, match=sample.uid):
            loaded.load_all()

    def test_load_all_allows_instance_strict_override_for_uid_conflict(self, tmp_path: Path) -> None:
        source = SampleSet()
        sample = self._make_default_sample("conflict-override")
        source[sample.uid] = sample
        base_dir = tmp_path / "strict_conflict_override"
        source.save(base_dir, storage_scheme=StorageScheme.SAMPLE_DIR)

        loaded = SampleSet({sample.uid: sample})
        loaded.strict = False
        loaded.connect_storage(base_dir, mode=StorageMode.OPEN, storage_scheme=StorageScheme.SAMPLE_DIR)

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
        sample_set.save(base_dir, storage_scheme=StorageScheme.SAMPLE_DIR)

        loaded = SampleSet.from_storage(
            base_dir,
            storage_scheme=StorageScheme.SAMPLE_DIR,
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
        sample_set.save(base_dir, storage_scheme=StorageScheme.SAMPLE_DIR)

        loaded = SampleSet.from_storage(
            base_dir,
            storage_scheme=StorageScheme.SAMPLE_DIR,
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
        sample_set.save(base_dir, storage_scheme=StorageScheme.SAMPLE_DIR)

        loaded = SampleSet.from_storage(
            base_dir,
            storage_scheme=StorageScheme.SAMPLE_DIR,
            load_mode=SampleLoadMode.EAGER,
            categories=[DataCategory.TS_ACCEL],
        )

        assert loaded[sample.uid].is_loaded("accel") is True

        with pytest.raises(ValueError, match="DataCategory"):
            SampleSet.from_storage(
                base_dir,
                storage_scheme=StorageScheme.SAMPLE_DIR,
                load_mode=SampleLoadMode.LAZY,
                categories=[DataCategory.FS_AMP],
            )

        with pytest.raises(TypeError, match="slots"):
            SampleSet.from_storage(  # type: ignore[call-arg]
                base_dir,
                storage_scheme=StorageScheme.SAMPLE_DIR,
                load_mode=SampleLoadMode.LAZY,
                slots=["accel"],
            )

        with pytest.raises(TypeError, match="data_categories"):
            SampleSet.from_storage(  # type: ignore[call-arg]
                base_dir,
                storage_scheme=StorageScheme.SAMPLE_DIR,
                load_mode=SampleLoadMode.LAZY,
                data_categories=[DataCategory.TS_ACCEL],
            )

        with pytest.raises(ValueError, match="not_a_selector"):
            SampleSet.from_storage(
                base_dir,
                storage_scheme=StorageScheme.SAMPLE_DIR,
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

        source.save(base_dir, storage_scheme=StorageScheme.SAMPLE_DIR, categories=categories)

        loaded = VibrationTestSampleSet.from_storage(
            base_dir,
            storage_scheme=StorageScheme.SAMPLE_DIR,
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
        source.save(base_dir, storage_scheme=StorageScheme.SAMPLE_DIR)

        loaded = VibrationTestSampleSet.from_storage(
            base_dir,
            storage_scheme=StorageScheme.SAMPLE_DIR,
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
        source.save(store_dir, storage_scheme=StorageScheme.SAMPLE_DIR)

        loaded = VibrationTestSampleSet.from_storage(
            store_dir,
            storage_scheme=StorageScheme.SAMPLE_DIR,
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
            sample_rows = conn.execute("SELECT uid, alias, payload_id FROM sample").fetchall()
            metadata_rows = conn.execute(
                "SELECT key, value_text FROM sample_metadata_flat ORDER BY key",
            ).fetchall()
            presence_rows = conn.execute(
                "SELECT slot_name, exists_flag, h5_path FROM sample_slot_presence",
            ).fetchall()
        finally:
            conn.close()

        assert len(sample_rows) == 1
        assert sample_rows[0][0] == sample.uid
        assert sample_rows[0][1] == sample.alias
        assert ("attributes@line", "L1") in metadata_rows
        assert ("extra@source", "sqlite-index") in metadata_rows
        assert presence_rows == [("accel", 1, f"/samples/{sample_rows[0][2]}/slots/accel")]

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
            StorageScheme.ATTR_TABLE,
            StorageScheme.SAMPLE_DIR,
        ],
    )
    def test_convert_storage_supports_formal_sample_set_schemes(
        self,
        tmp_path: Path,
        target_scheme: StorageScheme,
    ) -> None:
        sample = self._make_sample("formal")
        source_dir = tmp_path / "source_store"
        SampleSet({sample.uid: sample}).save(source_dir, storage_scheme=StorageScheme.SAMPLE_DIR)

        loaded = SampleSet.from_storage(
            source_dir,
            storage_scheme=StorageScheme.SAMPLE_DIR,
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

    def test_convert_storage_full_conversion_rebinds_followup_saves(self, tmp_path: Path) -> None:
        sample = self._make_sample("rebind")
        source_dir = tmp_path / "source_rebind"
        target_path = tmp_path / "converted_rebind.h5"
        SampleSet({sample.uid: sample}).save(source_dir, storage_scheme=StorageScheme.SAMPLE_DIR)

        loaded = SampleSet.from_storage(source_dir, storage_scheme=StorageScheme.SAMPLE_DIR)
        loaded.convert_storage(target_path, storage_scheme=StorageScheme.SET_H5)
        loaded[sample.uid].set_alias("converted-alias")
        loaded.save_all()

        source_loaded = SampleSet.from_storage(source_dir, storage_scheme=StorageScheme.SAMPLE_DIR)
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
            storage_scheme=StorageScheme.SAMPLE_DIR,
        )

        loaded = SampleSet.from_storage(source_dir, storage_scheme=StorageScheme.SAMPLE_DIR)
        loaded.convert_storage(
            target_path,
            storage_scheme=StorageScheme.SET_H5,
            categories=[DataCategory.TS_ACCEL],
            filter=lambda sample: sample.metadata.extra["source"] == "A",
        )

        assert loaded.storage is not None
        assert loaded.storage.storage_scheme is StorageScheme.SAMPLE_DIR
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

        loaded.convert_storage(target_dir, storage_scheme=StorageScheme.SAMPLE_DIR)

        converted = SampleSet.from_storage(
            target_dir,
            storage_scheme=StorageScheme.SAMPLE_DIR,
            load_mode=SampleLoadMode.EAGER,
        )

        assert converted[sample.uid].accel is not None
        assert converted[sample.uid].vel is not None

    def test_convert_storage_rejects_equivalent_target(self, tmp_path: Path) -> None:
        sample = self._make_sample("same-target")
        source_dir = tmp_path / "same_target_store"
        SampleSet({sample.uid: sample}).save(source_dir, storage_scheme=StorageScheme.SAMPLE_DIR)

        loaded = SampleSet.from_storage(source_dir, storage_scheme=StorageScheme.SAMPLE_DIR)

        with pytest.raises(ValueError, match="目标路径"):
            loaded.convert_storage(source_dir, storage_scheme=StorageScheme.SAMPLE_DIR)

    def test_convert_storage_requires_source_binding_for_unloaded_samples(self, tmp_path: Path) -> None:
        sample = self._make_sample("missing-source")
        source_dir = tmp_path / "missing_source_store"
        target_path = tmp_path / "missing_source_target.h5"
        SampleSet({sample.uid: sample}).save(source_dir, storage_scheme=StorageScheme.SAMPLE_DIR)

        loaded = SampleSet.from_storage(
            source_dir,
            storage_scheme=StorageScheme.SAMPLE_DIR,
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
