"""sqlite+h5 内部模块回归测试。"""

from __future__ import annotations

from pathlib import Path

import pytest

import dyntool.storage as dt_storage
from dyntool.domain.samples import SampleSet
from dyntool.domain.models import AccelSeries
from dyntool.infrastructure.sample_storage_sqlite_h5_payload import _collect_payload_path_refs
from dyntool.infrastructure.sample_storage_sqlite_h5_projection import _build_summary_rows
from dyntool.infrastructure.sample_storage_sqlite_h5_types import _SqlitePresenceRow
from dyntool.storage._sample_set_runtime import _resolve_sample_set_path_request
from dyntool.storage.runtime import StorageRuntime
from dyntool.storage.types import StorageMode, StorageScheme


def test_collect_payload_path_refs_groups_shared_h5_paths() -> None:
    items = [("u1", "alias-1"), ("u2", "alias-2")]
    selected_categories = ["accel", "vel", "disp"]
    presence_by_uid = {
        "u1": {
            "accel": _SqlitePresenceRow(
                slot_name="accel",
                exists_flag=True,
                model_type="AccelSeries",
                data_category="time_series",
                h5_path="/samples/p1/slots/accel",
                updated_at="2026-04-17T00:00:00",
            ),
            "vel": _SqlitePresenceRow(
                slot_name="vel",
                exists_flag=False,
                model_type="VelocitySeries",
                data_category="time_series",
                h5_path="/samples/p1/slots/vel",
                updated_at="2026-04-17T00:00:00",
            ),
        },
        "u2": {
            "accel": _SqlitePresenceRow(
                slot_name="accel",
                exists_flag=True,
                model_type="AccelSeries",
                data_category="time_series",
                h5_path="/samples/p2/slots/accel",
                updated_at="2026-04-17T00:00:00",
            ),
            "disp": _SqlitePresenceRow(
                slot_name="disp",
                exists_flag=True,
                model_type="DispSeries",
                data_category="time_series",
                h5_path="/samples/p2/slots/disp",
                updated_at="2026-04-17T00:00:00",
            ),
        },
    }

    grouped = _collect_payload_path_refs(
        items=items,
        selected_categories=selected_categories,
        presence_by_uid=presence_by_uid,
    )

    assert grouped == {
        "/samples/p1/slots/accel": [("u1", "accel")],
        "/samples/p2/slots/accel": [("u2", "accel")],
        "/samples/p2/slots/disp": [("u2", "disp")],
    }


def test_build_summary_rows_extracts_sampling_metrics_and_peak_value() -> None:
    accel = AccelSeries.from_data([0.0, 0.2, -0.1, 0.05], dt=0.01)

    rows = _build_summary_rows({"accel": accel})

    assert rows["accel@sample_count"]["value_real"] == 4.0
    assert rows["accel@dt"]["unit"] == "second"
    assert rows["accel@duration"]["value_real"] == 0.03
    assert rows["pga"]["value_real"] == accel.pga()


def test_resolve_sample_set_path_request_extracts_set_filename_for_set_h5(tmp_path: Path) -> None:
    request = _resolve_sample_set_path_request(
        tmp_path / "bundle.h5",
        default_mode=StorageMode.CREATE,
        storage_scheme=StorageScheme.SET_H5,
        set_filename=None,
        for_read=False,
    )

    assert request.base_dir == tmp_path
    assert request.storage_scheme is StorageScheme.SET_H5
    assert request.mode is StorageMode.CREATE
    assert request.set_filename == "bundle.h5"


def test_connect_sample_set_treats_set_h5_file_path_as_file_target(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sample_set = SampleSet()
    captured: dict[str, object] = {}

    class _DummyStorage:
        def __init__(self, *, sampleset: SampleSet) -> None:
            self.sampleset = sampleset

        def connect(self, base_dir: Path, **kwargs: object) -> None:
            captured["base_dir"] = base_dir
            captured["kwargs"] = kwargs

    monkeypatch.setattr("dyntool.storage.runtime.SampleSetStorage", _DummyStorage)

    dt_storage.connect_sample_set(
        sample_set,
        tmp_path / "bundle.h5",
        scheme=StorageScheme.SET_H5,
        mode=StorageMode.CREATE,
    )

    assert captured["base_dir"] == tmp_path
    assert captured["kwargs"] == {
        "mode": StorageMode.CREATE,
        "storage_scheme": StorageScheme.SET_H5,
        "data_options": None,
        "name_resolver": None,
        "set_filename": "bundle.h5",
    }


def test_top_level_load_sample_set_forwards_progress_arguments(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _progress_callback(completed: int, total: int) -> None:
        del completed, total

    captured: dict[str, object] = {}

    class _DummySampleSet:
        def __init__(self) -> None:
            self.strict = True
            self.storage_dirty = True

        @classmethod
        def from_samples(
            cls,
            _samples: object,
            *,
            sample_domain: object | None = None,
        ) -> "_DummySampleSet":
            del _samples, sample_domain
            return cls()

        @classmethod
        def from_storage(cls, *args: object, **kwargs: object) -> "_DummySampleSet":
            del args, kwargs
            raise AssertionError("top-level load_sample_set 不应直接绕到 SampleSet.from_storage()")

        def values(self) -> list[object]:
            return []

    def _fake_load_sample_set_runtime(
        self: StorageRuntime,
        sample_set: object,
        path: str | Path | None = None,
        *,
        progress_callback: object = None,
        show_progress: object = None,
        **kwargs: object,
    ) -> object:
        captured["sample_set"] = sample_set
        captured["path"] = path
        captured["progress_callback"] = progress_callback
        captured["show_progress"] = show_progress
        captured["kwargs"] = kwargs
        return sample_set

    monkeypatch.setattr("dyntool.storage._sample_set_runtime.get_sample_set_class", lambda _domain: _DummySampleSet)
    monkeypatch.setattr(StorageRuntime, "load_sample_set_runtime", _fake_load_sample_set_runtime)

    loaded = dt_storage.load_sample_set(
        tmp_path / "bundle.h5",
        domain=dt_storage.SampleDomain.DEFAULT,
        progress_callback=_progress_callback,
        show_progress=False,
        scheme=StorageScheme.SET_H5,
    )

    assert loaded is captured["sample_set"]
    assert captured["path"] == tmp_path / "bundle.h5"
    assert captured["progress_callback"] is _progress_callback
    assert captured["show_progress"] is False
    assert captured["kwargs"]["storage_scheme"] is StorageScheme.SET_H5


def test_storage_runtime_is_not_visible_from_top_level_storage_module() -> None:
    assert not hasattr(dt_storage, "StorageRuntime")
