"""样本与样本集基本行为测试。"""

from datetime import datetime
from pathlib import Path

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
    Sample,
    SampleSet,
    VibrationTestSample,
    VibrationTestSampleSet,
)
from dyntool.domain.samples.factories import build_metadata
from dyntool.infrastructure.persistence import RecoverableIOError
from dyntool.storage.types import (
    AttrDataFormat,
    StorageMode,
    StorageScheme,
)


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
        success, msg = sample.evaluation.zvl(force=True, freq_range=(2.0, 60.0))
        assert success is True
        assert sample.zvl is not None

    def test_eval_zvl_skip_when_exists(self) -> None:
        """已有 zvl 时 eval_zvl(force=False) 跳过。"""
        meta = _make_vib_meta()
        accel = AccelSeries.from_data(np.random.randn(500) * 0.01, dt=0.002)
        sample = VibrationTestSample(metadata=meta, accel=accel)
        sample.evaluation.zvl(force=True)
        success2, msg2 = sample.evaluation.zvl(force=False)
        assert success2 is False
        assert "已存在" in msg2 or "跳过" in msg2

    def test_calc_vel_calc_disp(self) -> None:
        """振动样本共享基类会写回 vel / disp。"""
        meta = _make_vib_meta()
        accel = AccelSeries.from_data(np.random.randn(500) * 0.01, dt=0.002)
        sample = VibrationTestSample(metadata=meta, accel=accel)
        ok_vel, _ = sample.calc_vel(force=True)
        ok_disp, _ = sample.calc_disp(force=True)
        assert ok_vel is True and sample.vel is not None
        assert ok_disp is True and sample.disp is not None

    def test_calc_freqspec(self) -> None:
        """振动样本共享基类会写回幅频与相频。"""
        meta = _make_vib_meta()
        accel = AccelSeries.from_data(np.random.randn(512) * 0.01, dt=0.002)
        sample = VibrationTestSample(metadata=meta, accel=accel)
        ok, _ = sample.calc_freqspec(force=True)
        assert ok is True
        assert sample.freqspec is not None
        assert not hasattr(sample, "freq_amp")
        assert not hasattr(sample, "freq_pha")

    def test_calc_respspec(self) -> None:
        """振动样本共享基类会写回 sa/sv/sd/psa/psv。"""
        meta = _make_vib_meta()
        accel = AccelSeries.from_data(np.random.randn(500) * 0.01, dt=0.002)
        sample = VibrationTestSample(metadata=meta, accel=accel)
        ok, _ = sample.calc_respspec(force=True)
        assert ok is True
        assert sample.respspec is not None
        assert not hasattr(sample, "respspec_sa")
        assert not hasattr(sample, "respspec_sv")
        assert not hasattr(sample, "respspec_sd")
        assert not hasattr(sample, "respspec_psa")
        assert not hasattr(sample, "respspec_psv")


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

        assert sample_set.get_sample(lambda sample: sample.metadata.point == "missing") is None
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
        assert save_errors == {}

        loaded = SampleSet()
        loaded.connect_storage(base_dir, mode=StorageMode.OPEN, storage_scheme=StorageScheme.SAMPLE_DIR)
        load_errors = loaded.load_all(strict=True, workers=2, chunk_size=1)
        assert load_errors == {}
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
