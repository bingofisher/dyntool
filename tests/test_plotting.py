"""独立绘图模块测试。"""

from __future__ import annotations

import matplotlib
import matplotlib.pyplot as plt
import numpy as np

matplotlib.use("Agg")

import dyntool.plotting as dt_plotting
from dyntool import AccelSeries, PlotKind, Sample, SampleDomain, SampleSet, VibrationTestMetadata
from dyntool.plotting import (
    AxisFrame,
    FramePlotPayload,
    FramePlotter,
    OctaveBandSpec,
    OneThirdOctavePlotter,
    PlotLinePayload,
    PlotResult,
    StoryLimitPayload,
    StorySeriesPayload,
    StoryValuePayload,
    StoryValuePlotter,
    ZhPlotConfig,
    configure_zh,
)


def _make_vibration_kwargs() -> dict[str, object]:
    return {
        "case": "plot",
        "point": "P1",
        "instr": "ACC-01",
        "dir": "Z",
        "record": "R1",
        "timestamp": "2026-03-08 12:00:00",
    }


def test_time_series_exports_frame_payload_and_renders() -> None:
    accel = AccelSeries.from_data(np.random.randn(200) * 0.01, dt=0.002)
    payload = accel.to_plot_payload(kind=PlotKind.TIME)

    assert payload["plotter_kind"] == "frame"

    result = dt_plotting.render_payload(payload)
    assert isinstance(result, PlotResult)
    assert result.figure is not None
    assert result.axes


def test_freqspec_exports_multi_panel_frame_payload_and_renders() -> None:
    accel = AccelSeries.from_data(np.random.randn(256) * 0.01, dt=0.002)
    freqspec = accel.calc_freqspec()

    payload = freqspec.to_plot_payload(kind=PlotKind.FREQSPEC)
    assert payload["plotter_kind"] == "frame"
    panels = payload["panels"]
    assert isinstance(panels, tuple)
    assert len(panels) == 2

    result = dt_plotting.render_payload(payload)
    assert isinstance(result, PlotResult)
    assert result.figure is not None
    assert len(result.axes) == 2


def test_respspec_exports_grouped_frame_payload_and_renders() -> None:
    accel = AccelSeries.from_data(np.random.randn(512) * 0.01, dt=0.002)
    respspec = accel.calc_respspec_bundle()

    payload = respspec.to_plot_payload(kind=PlotKind.RESPSPEC)
    assert payload["plotter_kind"] == "frame"

    result = dt_plotting.render_payload(payload)
    assert isinstance(result, PlotResult)
    assert result.figure is not None
    assert len(result.axes[0].lines) >= 1


def test_otovl_exports_octave_payload_and_renders() -> None:
    accel = AccelSeries.from_data(np.random.randn(1200) * 0.01, dt=0.002)
    otovl = accel.eval_otovl(freq_range=(1.0, 80.0))

    payload = otovl.to_plot_payload(kind=PlotKind.OTOVL)
    assert payload["plotter_kind"] == "one_third_octave"

    result = dt_plotting.render_payload(payload)
    assert isinstance(result, PlotResult)
    assert result.figure is not None
    assert result.axes


def test_story_value_plotter_renders_samples_stats_and_limits() -> None:
    payload = StoryValuePayload(
        title="story-values",
        y_label="story",
        x_label="value",
        x_unit="meter/second**2",
        tick_labels={-1.0: "B1", 0.0: "B2", 1.0: "B3", 2.0: "B4"},
        samples=(StorySeriesPayload(levels=[-1, 0, 1, 2], values=[0.001, 0.002, 0.003, 0.004], label="sample-a"),),
        stats=(StorySeriesPayload(levels=[-1, 0, 1, 2], values=[0.0012, 0.0022, 0.0032, 0.0042], label="mean"),),
        limits=(
            StoryLimitPayload(value=0.0035, label="limit-a"),
            StoryLimitPayload(value=0.0045, label="limit-b"),
        ),
    )

    result = dt_plotting.render_payload(payload)
    assert isinstance(result, PlotResult)
    assert result.figure is not None
    assert result.axes


def test_render_plotter_accepts_explicit_plotter_instance() -> None:
    accel = AccelSeries.from_data(np.random.randn(64) * 0.01, dt=0.002)
    payload = accel.to_plot_payload(kind=PlotKind.TIME)
    fig, ax = plt.subplots()

    result = dt_plotting.render_plotter(FramePlotter(ax=ax), payload)

    assert isinstance(result, PlotResult)
    assert result.figure is fig
    assert result.axes[0] is ax


def test_axis_frame_and_octave_band_spec_are_exposed() -> None:
    assert AxisFrame.__module__ == "dyntool.plotting.plotters"
    spec = OctaveBandSpec.from_default_table(lower_frequency=1.0, upper_frequency=80.0)
    assert spec.band_numbers_from_range()


def test_new_plotter_types_are_exposed_from_plotting_module() -> None:
    assert FramePlotter.__module__ == "dyntool.plotting.plotters"
    assert OneThirdOctavePlotter.__module__ == "dyntool.plotting.plotters"
    assert StoryValuePlotter.__module__ == "dyntool.plotting.plotters"


def test_object_level_plotting_api_is_removed() -> None:
    accel = AccelSeries.from_data([0.0, 0.1, -0.05], dt=0.01)
    sample = Sample.from_accel_data(
        [0.0, 0.1, -0.02],
        dt=0.01,
        sample_domain=SampleDomain.VIBRATION_TEST,
        metadata_cls=VibrationTestMetadata,
        **_make_vibration_kwargs(),
    )
    sample_set = SampleSet.from_samples([sample], sample_domain=SampleDomain.VIBRATION_TEST)

    assert not hasattr(dt_plotting, "plot_model")
    assert not hasattr(dt_plotting, "plot_sample")
    assert not hasattr(dt_plotting, "plot_sample_set")
    assert not hasattr(dt_plotting, "render_target")
    assert not hasattr(accel, "plot")
    assert not hasattr(accel, "plot_static")
    assert not hasattr(sample, "plot")
    assert not hasattr(sample, "plot_attr")
    assert not hasattr(sample_set, "plot_sample")
    assert not hasattr(sample_set, "plot_data")


def test_configure_zh_uses_songtnr_by_default() -> None:
    font_name = configure_zh()
    assert font_name == "SongTNR"
    assert plt.rcParams["font.sans-serif"][0] == "SongTNR"


def test_plotting_config_objects_are_exposed_from_plotting_module() -> None:
    assert ZhPlotConfig.__module__ == "dyntool.plotting.config"


def test_frame_payload_dataclass_can_be_rendered_directly() -> None:
    payload = FramePlotPayload(
        panels=(
            dt_plotting.FramePanelPayload(
                title="raw-series",
                x_label="time",
                y_label="acceleration",
                x_unit="second",
                y_unit="meter/second**2",
                series=(
                    PlotLinePayload(
                        x=[0.0, 0.1, 0.2],
                        y=[0.0, 0.1, -0.05],
                        label="accel",
                    ),
                ),
            ),
        ),
    )

    result = dt_plotting.render_payload(payload)
    assert isinstance(result, PlotResult)
    assert result.figure is not None
    assert result.axes[0].get_title() == "raw-series"
