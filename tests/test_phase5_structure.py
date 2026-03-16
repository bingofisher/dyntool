"""Canonical module location tests after final refactor."""

from __future__ import annotations

from dyntool.domain.samples import VibrationTestSample, VibrationTestSampleSet
from dyntool.logging import LogProvider, LoggingConfig, LoggingMode
from dyntool.plotting import configure_zh
from dyntool.storage import StorageMode, StorageScheme


def test_vibration_symbols_are_defined_in_vibration_test_module() -> None:
    assert VibrationTestSample.__module__ == "dyntool.domain.samples.vibration_test"
    assert VibrationTestSampleSet.__module__ == "dyntool.domain.samples.vibration_test"


def test_logging_symbols_are_defined_in_logging_module() -> None:
    assert LogProvider.__module__ == "dyntool.logging.provider"
    assert LoggingConfig.__module__ == "dyntool.logging.config"
    assert LoggingMode.__module__ == "dyntool.logging.types"


def test_plotting_config_symbols_are_defined_in_plotting_module() -> None:
    assert configure_zh.__module__ == "dyntool.plotting.config"


def test_storage_enums_are_defined_in_storage_module() -> None:
    assert StorageMode.__module__ == "dyntool.storage.types"
    assert StorageScheme.__module__ == "dyntool.storage.types"
