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
    assert not hasattr(dt_plotting.FramePlotter, "plot")
    assert "backend" not in inspect.signature(dt_plotting.FramePlotter.plot_dataset).parameters
    assert "backend" not in getattr(dt_plotting.PlotResult, "__annotations__", {})


def test_concrete_plotter_public_signatures_only_expose_ax_and_theme() -> None:
    for plotter in (
        dt_plotting.FramePlotter,
        dt_plotting.BoxPlotter,
        dt_plotting.OneThirdOctavePlotter,
        dt_plotting.StoryValuePlotter,
    ):
        params = tuple(inspect.signature(plotter).parameters)
        assert params == ("ax", "theme")


def test_plotting_public_bridge_helpers_stay_hidden() -> None:
    theme = dt_plotting.PlotTheme.default()
    assert not hasattr(theme, "axis_frame")
    assert not hasattr(theme, "grid_frame")

    frame_plotter = dt_plotting.FramePlotter()
    assert not hasattr(frame_plotter, "axis_frame")
    assert not hasattr(frame_plotter, "grid_frame")

    octave_plotter = dt_plotting.OneThirdOctavePlotter()
    assert "band_spec" not in inspect.signature(dt_plotting.OneThirdOctavePlotter).parameters
    assert not hasattr(octave_plotter, "band_spec")
