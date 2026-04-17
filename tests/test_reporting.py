"""reporting 正式导出接口测试。"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import dyntool.reporting as dt_reporting
from dyntool.domain.models import AccelSeries
from dyntool.domain.metadata import VibrationTestMetadata
from dyntool.domain.samples import VibrationTestSample, VibrationTestSampleSet
from dyntool.storage import SampleLoadMode
from dyntool.storage.types import StorageScheme


def _make_metadata(*, case: str, point: str, record: str) -> VibrationTestMetadata:
    return VibrationTestMetadata(
        case=case,
        point=point,
        instr="ACC-01",
        dir="Z",
        record=record,
        timestamp=datetime(2026, 4, 1, 12, 0, 0),
    )


def _make_sample(*, case: str, point: str, record: str, values: np.ndarray) -> VibrationTestSample:
    return VibrationTestSample(
        metadata=_make_metadata(case=case, point=point, record=record),
        accel=AccelSeries.from_data(values, dt=0.01, axis_unit="second", data_unit="meter/second**2"),
    )


def _make_sample_set(*, with_eval: bool = False) -> VibrationTestSampleSet:
    axis = np.linspace(0.0, 20.47, 2048, dtype=float)
    sample_a = _make_sample(
        case="case-a",
        point="P1",
        record="R1",
        values=0.01 * np.sin(2 * np.pi * 3.15 * axis) + 0.002 * np.sin(2 * np.pi * 10.0 * axis),
    )
    sample_b = _make_sample(
        case="case-b",
        point="P2",
        record="R2",
        values=0.012 * np.sin(2 * np.pi * 4.0 * axis) + 0.0025 * np.sin(2 * np.pi * 12.5 * axis),
    )
    sample_set = VibrationTestSampleSet({sample_a.uid: sample_a, sample_b.uid: sample_b})
    if with_eval:
        sample_set.eval_zvl(overwrite=True, freq_range=(2.0, 80.0))
        sample_set.eval_otovl(overwrite=True, freq_range=(2.0, 80.0))
    return sample_set


def test_export_scalar_frame_supports_csv_and_xlsx(tmp_path: Path) -> None:
    sample_set = _make_sample_set()
    csv_path = tmp_path / "scalar_frame.csv"
    xlsx_path = tmp_path / "scalar_frame.xlsx"

    returned_csv = dt_reporting.export_scalar_frame(
        sample_set,
        csv_path,
        features=["pga", "rms"],
        strict=False,
        format="csv",
    )
    returned_xlsx = dt_reporting.export_scalar_frame(
        sample_set,
        xlsx_path,
        features=["pga", "rms"],
        strict=False,
        format="xlsx",
    )

    assert returned_csv == csv_path
    assert returned_xlsx == xlsx_path
    csv_frame = pd.read_csv(csv_path)
    xlsx_frame = pd.read_excel(xlsx_path, sheet_name="scalar_frame")
    assert {"uid", "alias", "pga", "rms"} <= set(csv_frame.columns)
    assert {"uid", "alias", "pga", "rms"} <= set(xlsx_frame.columns)


def test_export_series_frame_flattens_multiindex_columns_for_export(tmp_path: Path) -> None:
    sample_set = _make_sample_set()
    csv_path = tmp_path / "series_frame.csv"

    returned = dt_reporting.export_series_frame(
        sample_set,
        csv_path,
        data_var="accel",
        metadata_fields=["case"],
        strict=True,
        format="csv",
    )

    assert returned == csv_path
    frame = pd.read_csv(csv_path)
    exported_columns = set(frame.columns)
    assert any(column.endswith("@value") for column in exported_columns)
    assert any("case-a" in column for column in exported_columns)
    assert any("case-b" in column for column in exported_columns)


def test_export_peaks_frame_supports_xlsx(tmp_path: Path) -> None:
    sample_set = _make_sample_set()
    xlsx_path = tmp_path / "peaks_frame.xlsx"

    returned = dt_reporting.export_peaks_frame(
        sample_set,
        xlsx_path,
        source="accel",
        prominence=0.01,
        format="xlsx",
    )

    assert returned == xlsx_path
    frame = pd.read_excel(xlsx_path, sheet_name="peaks_frame")
    assert "peak_rank" in frame.columns
    assert any(column.endswith("@peak_value") for column in frame.columns)


def test_export_compare_report_supports_csv_directory_and_xlsx(tmp_path: Path) -> None:
    left = _make_sample_set()
    right = _make_sample_set()
    first_right = next(iter(right.values()))
    first_right.update_metadata(case="case-a-updated")
    first_right.update_data(
        accel=AccelSeries.from_data(
            np.asarray([0.0, 0.20, -0.02, 0.05, -0.01, 0.01], dtype=float),
            dt=0.01,
            axis_unit="second",
            data_unit="meter/second**2",
        )
    )
    csv_dir = tmp_path / "compare_csv"
    xlsx_path = tmp_path / "compare.xlsx"

    returned_csv_dir = dt_reporting.export_compare_report(
        left,
        right,
        csv_dir,
        features=["pga"],
        format="csv",
    )
    returned_xlsx = dt_reporting.export_compare_report(
        left,
        right,
        xlsx_path,
        features=["pga"],
        format="xlsx",
    )

    assert returned_csv_dir == csv_dir
    assert returned_xlsx == xlsx_path
    assert (csv_dir / "metadata_diff.csv").exists()
    assert (csv_dir / "presence_diff.csv").exists()
    assert (csv_dir / "scalar_diff.csv").exists()
    workbook = pd.read_excel(xlsx_path, sheet_name=None)
    assert {"metadata_diff", "presence_diff", "scalar_diff"} <= set(workbook)


def test_export_report_package_generates_complete_project_bundle(tmp_path: Path) -> None:
    sample_set = _make_sample_set(with_eval=True)
    compare_to = _make_sample_set(with_eval=True)
    package_dir = tmp_path / "report_package"

    returned_dir = dt_reporting.export_report_package(
        sample_set,
        package_dir,
        compare_to=compare_to,
        features=["pga", "rms"],
        series_vars=["accel"],
        peak_sources=["accel"],
        include_plots=True,
        include_eval_summary=True,
    )

    assert returned_dir == package_dir
    report_path = package_dir / "report.xlsx"
    tables_dir = package_dir / "tables"
    figures_dir = package_dir / "figures"
    manifest_path = package_dir / "manifest.json"
    metadata_summary_path = package_dir / "metadata_summary.json"

    assert report_path.exists()
    assert tables_dir.is_dir()
    assert figures_dir.is_dir()
    assert manifest_path.exists()
    assert metadata_summary_path.exists()
    assert (tables_dir / "scalar_frame.csv").exists()
    assert (tables_dir / "series_accel.csv").exists()
    assert (tables_dir / "peaks_accel.csv").exists()
    assert (tables_dir / "compare_metadata_diff.csv").exists()
    assert (tables_dir / "eval_summary.csv").exists()

    workbook = pd.read_excel(report_path, sheet_name=None)
    assert {
        "metadata_summary",
        "scalar_frame",
        "series_accel",
        "peaks_accel",
        "compare_metadata_diff",
        "compare_presence_diff",
        "compare_scalar_diff",
        "eval_summary",
        "figures_index",
    } <= set(workbook)

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["sample_count"] == 2
    assert manifest["report_workbook"] == "report.xlsx"
    assert any(item["name"] == "scalar_frame" for item in manifest["tables"])
    assert any(item["theme"] == "plot_theme_report.toml" for item in manifest["figures"])
    assert any(item["theme"] == "plot_theme_one_third_octave.toml" for item in manifest["figures"])


def test_export_scalar_frame_uses_sqlite_h5_summary_fast_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sample_set = _make_sample_set()
    store_dir = tmp_path / "sqlite_h5_scalar_report"
    sample_set.save(store_dir, storage_scheme=StorageScheme.SET_SQLITE_H5)
    loaded = VibrationTestSampleSet.from_storage(
        store_dir,
        storage_scheme=StorageScheme.SET_SQLITE_H5,
        load_mode=SampleLoadMode.LAZY,
    )

    strategy = loaded.storage._sample_storage.strategy
    summary_calls: list[tuple[tuple[str, ...] | None, tuple[str, ...] | None]] = []
    original_summary_frame = loaded.storage.summary_frame

    def _tracked_summary_frame(*args: object, **kwargs: object) -> object:
        summary_calls.append(
            (
                tuple(kwargs.get("uids")) if kwargs.get("uids") is not None else None,
                tuple(kwargs.get("metadata_fields")) if kwargs.get("metadata_fields") is not None else None,
            )
        )
        return original_summary_frame(*args, **kwargs)

    def _unexpected(*args: object, **kwargs: object) -> object:
        del args, kwargs
        raise AssertionError("reporting 不应回退到 payload 读取")

    monkeypatch.setattr(loaded.storage, "summary_frame", _tracked_summary_frame)
    monkeypatch.setattr(strategy, "load_sample", _unexpected)
    monkeypatch.setattr(strategy, "load_sample_fields", _unexpected)
    monkeypatch.setattr(strategy, "load_many_sample_fields", _unexpected)

    returned = dt_reporting.export_scalar_frame(
        loaded,
        tmp_path / "scalar_frame.csv",
        features=["pga", "rms"],
        strict=False,
        format="csv",
    )

    assert returned == tmp_path / "scalar_frame.csv"
    assert summary_calls
    frame = pd.read_csv(returned)
    assert {"uid", "alias"} <= set(frame.columns)
    assert any("pga" in column for column in frame.columns)
    assert len(frame) == len(sample_set)


def test_export_compare_report_uses_sqlite_h5_scalar_fast_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    left = _make_sample_set()
    right = _make_sample_set()
    right_first = next(iter(right.values()))
    right_first.update_metadata(case="case-a-updated")

    left_store = tmp_path / "sqlite_h5_compare_left"
    right_store = tmp_path / "sqlite_h5_compare_right"
    left.save(left_store, storage_scheme=StorageScheme.SET_SQLITE_H5)
    right.save(right_store, storage_scheme=StorageScheme.SET_SQLITE_H5)

    loaded_left = VibrationTestSampleSet.from_storage(
        left_store,
        storage_scheme=StorageScheme.SET_SQLITE_H5,
        load_mode=SampleLoadMode.LAZY,
    )
    loaded_right = VibrationTestSampleSet.from_storage(
        right_store,
        storage_scheme=StorageScheme.SET_SQLITE_H5,
        load_mode=SampleLoadMode.LAZY,
    )

    left_strategy = loaded_left.storage._sample_storage.strategy
    right_strategy = loaded_right.storage._sample_storage.strategy
    left_summary_calls = 0
    right_summary_calls = 0
    original_left_summary_frame = loaded_left.storage.summary_frame
    original_right_summary_frame = loaded_right.storage.summary_frame

    def _tracked_left_summary_frame(*args: object, **kwargs: object) -> object:
        nonlocal left_summary_calls
        left_summary_calls += 1
        return original_left_summary_frame(*args, **kwargs)

    def _tracked_right_summary_frame(*args: object, **kwargs: object) -> object:
        nonlocal right_summary_calls
        right_summary_calls += 1
        return original_right_summary_frame(*args, **kwargs)

    def _unexpected(*args: object, **kwargs: object) -> object:
        del args, kwargs
        raise AssertionError("compare report 不应回退到 payload 读取")

    monkeypatch.setattr(loaded_left.storage, "summary_frame", _tracked_left_summary_frame)
    monkeypatch.setattr(loaded_right.storage, "summary_frame", _tracked_right_summary_frame)
    for strategy in (left_strategy, right_strategy):
        monkeypatch.setattr(strategy, "load_sample", _unexpected)
        monkeypatch.setattr(strategy, "load_sample_fields", _unexpected)
        monkeypatch.setattr(strategy, "load_many_sample_fields", _unexpected)

    returned = dt_reporting.export_compare_report(
        loaded_left,
        loaded_right,
        tmp_path / "compare_report",
        features=["pga"],
        format="csv",
    )

    assert returned == tmp_path / "compare_report"
    assert left_summary_calls > 0
    assert right_summary_calls > 0
    assert (returned / "scalar_diff.csv").exists()
    assert (returned / "metadata_diff.csv").exists()
    assert (returned / "presence_diff.csv").exists()
