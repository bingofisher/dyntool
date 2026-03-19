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


def test_center_freqs_returns_filtered_band_data() -> None:
    values, index = dt_resource.center_freqs((10.0, 20.0))

    assert len(values) == len(index)
    assert float(values.min()) >= 10.0
    assert float(values.max()) <= 20.0


def test_unknown_resource_key_raises_key_error() -> None:
    with pytest.raises(KeyError, match="未知资源 key"):
        dt_resource.path("unknown_key")
