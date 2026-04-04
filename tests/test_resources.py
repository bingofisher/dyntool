"""正式资源模块测试。"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

import dyntool.resources as dt_resource


def test_keys_and_manifest_are_available() -> None:
    keys = dt_resource.keys()
    manifest = dt_resource.manifest()

    assert isinstance(keys, tuple)
    assert "center_freq" in keys
    assert manifest["center_freq"]


def test_path_returns_existing_resource_file() -> None:
    path = dt_resource.path("center_freq")

    assert isinstance(path, Path)
    assert path.exists()


def test_csv_reads_resource_table() -> None:
    frame = dt_resource.csv("center_freq")

    assert isinstance(frame, pd.DataFrame)
    assert not frame.empty


def test_csv_defaults_to_utf8_sig_for_resource_files(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    resource_file = tmp_path / "center_freq.csv"
    resource_file.write_bytes(b"\xef\xbb\xbf" + "中心频率 (Hz)\n1.0\n2.0\n".encode("utf-8"))
    monkeypatch.setattr(dt_resource, "_STANDARD_KEYS", {"center_freq": resource_file.name})
    monkeypatch.setattr(dt_resource, "_RESOURCES_ROOT", tmp_path)

    frame = dt_resource.csv("center_freq")

    assert list(frame.columns) == ["中心频率 (Hz)"]
    assert frame.iloc[:, 0].tolist() == [1.0, 2.0]


def test_csv_honors_explicit_encoding_over_default(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    resource_file = tmp_path / "center_freq.csv"
    resource_file.write_text("中心频率 (Hz)\n3.0\n", encoding="utf-8", newline="\n")
    monkeypatch.setattr(dt_resource, "_STANDARD_KEYS", {"center_freq": resource_file.name})
    monkeypatch.setattr(dt_resource, "_RESOURCES_ROOT", tmp_path)

    frame = dt_resource.csv("center_freq", csv_options={"encoding": "utf-8"})

    assert frame.iloc[:, 0].tolist() == [3.0]


def test_center_freqs_returns_filtered_band_data() -> None:
    values, index = dt_resource.center_freqs((10.0, 20.0))

    assert len(values) == len(index)
    assert float(values.min()) >= 10.0
    assert float(values.max()) <= 20.0


def test_unknown_resource_key_raises_key_error() -> None:
    with pytest.raises(KeyError, match="未知资源 key"):
        dt_resource.path("unknown_key")
