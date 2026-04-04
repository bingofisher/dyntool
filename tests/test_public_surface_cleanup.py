"""公开面二次收口回归测试。"""

from __future__ import annotations

import importlib
import inspect
from pathlib import Path

import dyntool
import dyntool.plotting as dt_plotting
import dyntool.resources as dt_resource
import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_dyntool_facade_is_removed_from_top_level() -> None:
    assert "DynTool" not in dyntool.__all__
    assert not hasattr(dyntool, "DynTool")


def test_resource_is_formal_public_module() -> None:
    assert "resources" in dyntool.__all__
    assert not hasattr(dyntool, "resource")
    assert callable(dt_resource.keys)
    assert callable(dt_resource.manifest)
    assert callable(dt_resource.path)
    assert callable(dt_resource.csv)
    assert callable(dt_resource.center_freqs)


def test_legacy_resource_module_is_not_importable() -> None:
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("dyntool.resource")


def test_legacy_resource_package_is_removed_from_source_tree() -> None:
    assert not (PROJECT_ROOT / "src" / "dyntool" / "resource").exists()


def test_plot_backend_and_backend_parameter_are_removed() -> None:
    assert "PlotBackend" not in dyntool.__all__
    assert not hasattr(dt_plotting, "PlotBackend")
    assert "backend" not in inspect.signature(dt_plotting.FramePlotter.plot).parameters
    assert "backend" not in inspect.signature(dt_plotting.FramePlotter.plot_dataset).parameters
    assert "backend" not in getattr(dt_plotting.PlotResult, "__annotations__", {})
