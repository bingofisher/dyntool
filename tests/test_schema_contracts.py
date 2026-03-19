"""Schema-first contract tests for metadata and sample definitions."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import ClassVar

import pytest
from pydantic import Field

from dyntool.domain.metadata import Metadata, VibrationTestMetadata
from dyntool.domain.metadata.schema import MetadataSchema
from dyntool.domain.models import AccelSeries, VelSeries
from dyntool.domain.samples import SampleBase, SampleSetBase, VibrationTestSample
from dyntool.domain.samples.schema import SampleSchema, SampleSlotSpec
from dyntool.infrastructure.sample_set_storage import SampleSetStorage
from dyntool.infrastructure.sample_storage import SampleStorage
from dyntool.infrastructure.sample_storage_context import StorageContext
from dyntool.storage.types import StorageMode, StorageScheme


class _StorageAliasSample(SampleBase):
    metadata: Metadata = Field(...)
    sample_schema: ClassVar[SampleSchema] = SampleSchema(
        name="storage_alias_sample",
        metadata_type=Metadata,
        slots=(
            SampleSlotSpec(
                name="accel",
                model_type=AccelSeries,
                aliases=("a",),
            ),
            SampleSlotSpec(
                name="vel",
                model_type=VelSeries,
                aliases=("v",),
                include_in_storage=False,
            ),
        ),
    )


class _StorageAliasSampleSet(SampleSetBase[_StorageAliasSample]):
    _sample_type = _StorageAliasSample


class _SelectableStorageSample(SampleBase):
    metadata: Metadata = Field(...)
    sample_schema: ClassVar[SampleSchema] = SampleSchema(
        name="selectable_storage_sample",
        metadata_type=Metadata,
        slots=(
            SampleSlotSpec(
                name="accel",
                model_type=AccelSeries,
                aliases=("a",),
            ),
            SampleSlotSpec(
                name="vel",
                model_type=VelSeries,
                aliases=("v",),
                include_in_storage=True,
            ),
        ),
    )


class _SelectableStorageSampleSet(SampleSetBase[_SelectableStorageSample]):
    _sample_type = _SelectableStorageSample


def test_metadata_schema_projects_alias_fields_before_projection() -> None:
    schema = MetadataSchema(
        name="vibration_metadata",
        identity_fields=("case", "point"),
        attribute_fields=("dir",),
        aliases={"pt": "point", "direction": "dir"},
    )
    payload = {
        "case": "c1",
        "pt": "p1",
        "direction": "Z",
        "ignored": "drop-me",
    }
    assert schema.normalize_identity(payload) == {"case": "c1", "point": "p1"}
    assert schema.normalize_attributes(payload) == {"dir": "Z"}


def test_sample_schema_returns_storage_slot_names_only() -> None:
    schema = SampleSchema(
        name="sample",
        metadata_type=Metadata,
        slots=(
            SampleSlotSpec(name="accel", model_type=AccelSeries, required=True),
            SampleSlotSpec(name="vel", model_type=VelSeries, include_in_storage=False),
        ),
        aliases={"a": "accel"},
    )
    assert schema.canonical_name("a") == "accel"
    assert schema.slot_names(include_storage_only=True) == ("accel",)


def test_sample_structured_payload_includes_storable_freqspec_slot() -> None:
    sample = VibrationTestSample(
        metadata=VibrationTestMetadata(
            case="c1",
            point="p1",
            instr="a1",
            dir="Z",
            record="r1",
            timestamp=datetime(2026, 3, 13, 12, 0, 0),
        ),
        accel=AccelSeries.from_data([0.0, 0.1, -0.1], dt=0.01),
    )
    result = sample.calc_freqspec(overwrite=True)
    assert result.success is True
    payload = sample.to_structured_payload()
    assert "freqspec" in payload.data_vars


def test_storage_context_canonicalizes_alias_categories_for_storage(
    tmp_path: Path,
) -> None:
    sample = _StorageAliasSample(
        metadata=Metadata(identity={"case": "c1"}),
        accel=AccelSeries.from_data([0.0, 0.1, -0.1], dt=0.01),
    )
    sampleset = _StorageAliasSampleSet([sample])
    ctx = StorageContext(
        sampleset,
        base_dir=tmp_path,
        storage_scheme=StorageScheme.SAMPLE_DIR,
    )

    data_dict = ctx.sample_data_dict(sample, ["a"])

    assert tuple(data_dict) == ("accel",)
    assert data_dict["accel"] is sample.accel


def test_storage_context_rejects_non_storage_slots_even_when_explicit(
    tmp_path: Path,
) -> None:
    sample = _StorageAliasSample(
        metadata=Metadata(identity={"case": "c1"}),
        accel=AccelSeries.from_data([0.0, 0.1, -0.1], dt=0.01),
        vel=VelSeries.from_data([0.0, 0.2, 0.1], dt=0.01),
    )
    sampleset = _StorageAliasSampleSet([sample])
    ctx = StorageContext(
        sampleset,
        base_dir=tmp_path,
        storage_scheme=StorageScheme.SAMPLE_DIR,
    )

    with pytest.raises(ValueError, match="vel"):
        ctx.sample_data_dict(sample, ["v"])


def test_sample_storage_load_canonicalizes_categories_before_strategy_call(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    sample = _StorageAliasSample(
        metadata=Metadata(identity={"case": "c1"}),
        accel=AccelSeries.from_data([0.0, 0.1, -0.1], dt=0.01),
    )
    sampleset = _StorageAliasSampleSet([sample])
    ctx = StorageContext(
        sampleset,
        base_dir=tmp_path,
        storage_scheme=StorageScheme.SAMPLE_DIR,
    )
    storage = SampleStorage(ctx)
    calls: list[tuple[str, object]] = []

    monkeypatch.setattr(storage, "index", lambda: {sample.uid: "sample-1"})

    def fake_load_sample(
        uid: str,
        name: str,
        categories: list[str] | None = None,
    ) -> _StorageAliasSample:
        calls.append(("load", {"uid": uid, "name": name, "categories": categories}))
        return sample

    monkeypatch.setattr(storage.strategy, "load_sample", fake_load_sample)

    loaded = storage.load(sample.uid, ["a"])

    assert loaded is sample
    assert calls == [
        (
            "load",
            {"uid": sample.uid, "name": "sample-1", "categories": ["accel"]},
        )
    ]


def test_sample_storage_load_rejects_non_storage_categories(
    tmp_path: Path,
) -> None:
    sample = _StorageAliasSample(
        metadata=Metadata(identity={"case": "c1"}),
        accel=AccelSeries.from_data([0.0, 0.1, -0.1], dt=0.01),
    )
    sampleset = _StorageAliasSampleSet([sample])
    ctx = StorageContext(
        sampleset,
        base_dir=tmp_path,
        storage_scheme=StorageScheme.SAMPLE_DIR,
    )
    storage = SampleStorage(ctx)

    with pytest.raises(ValueError, match="vel"):
        storage.load(sample.uid, ["v"])


def test_sample_storage_load_only_restores_selected_storage_categories(
    tmp_path: Path,
) -> None:
    sample = _SelectableStorageSample(
        metadata=Metadata(identity={"case": "c1"}),
        accel=AccelSeries.from_data([0.0, 0.1, -0.1], dt=0.01),
        vel=VelSeries.from_data([0.0, 0.2, 0.1], dt=0.01),
    )
    sampleset = _SelectableStorageSampleSet([sample])
    ctx = StorageContext(
        sampleset,
        base_dir=tmp_path,
        storage_scheme=StorageScheme.SAMPLE_DIR,
    )
    storage = SampleStorage(ctx)

    storage.save(sample)
    loaded = storage.load(sample.uid, ["a"])

    assert loaded.accel is not None
    assert loaded.vel is None


def test_sample_set_storage_save_all_only_persists_selected_storage_categories(
    tmp_path: Path,
) -> None:
    sample = _SelectableStorageSample(
        metadata=Metadata(identity={"case": "c1"}),
        accel=AccelSeries.from_data([0.0, 0.1, -0.1], dt=0.01),
        vel=VelSeries.from_data([0.0, 0.2, 0.1], dt=0.01),
    )
    source = _SelectableStorageSampleSet([sample])
    source.storage = SampleSetStorage(source)
    source.storage.connect(
        tmp_path / "selected-save",
        mode=StorageMode.CREATE,
        storage_scheme=StorageScheme.SAMPLE_DIR,
    )

    source.storage.save_all(categories=["a"])

    loaded = _SelectableStorageSampleSet()
    loaded.storage = SampleSetStorage(loaded)
    loaded.storage.connect(
        tmp_path / "selected-save",
        mode=StorageMode.OPEN,
        storage_scheme=StorageScheme.SAMPLE_DIR,
    )
    loaded.storage.load_all()

    assert loaded[sample.uid].accel is not None
    assert loaded[sample.uid].vel is None


def test_sample_set_storage_load_all_only_restores_selected_storage_categories(
    tmp_path: Path,
) -> None:
    sample = _SelectableStorageSample(
        metadata=Metadata(identity={"case": "c1"}),
        accel=AccelSeries.from_data([0.0, 0.1, -0.1], dt=0.01),
        vel=VelSeries.from_data([0.0, 0.2, 0.1], dt=0.01),
    )
    source = _SelectableStorageSampleSet([sample])
    source.storage = SampleSetStorage(source)
    source.storage.connect(
        tmp_path / "selected-load",
        mode=StorageMode.CREATE,
        storage_scheme=StorageScheme.SAMPLE_DIR,
    )
    source.storage.save_all()

    loaded = _SelectableStorageSampleSet()
    loaded.storage = SampleSetStorage(loaded)
    loaded.storage.connect(
        tmp_path / "selected-load",
        mode=StorageMode.OPEN,
        storage_scheme=StorageScheme.SAMPLE_DIR,
    )
    loaded.storage.load_all(categories=["a"])

    assert loaded[sample.uid].accel is not None
    assert loaded[sample.uid].vel is None
