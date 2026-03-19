"""独立绘图模块测试。"""

from __future__ import annotations

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pytest
import pandas as pd
import warnings

matplotlib.use("Agg")

import dyntool.plotting as dt_plotting
from dyntool import (
    AccelSeries,
    OTOVLEval,
    OTOVLLimit,
    OTOVLLimitStandard,
    Sample,
    SampleDomain,
    SampleSet,
    VibrationTestMetadata,
    ZVLLimit,
    ZVLLimitStandard,
)
from dyntool.plotting import (
    AxisFrame,
    AxisHelper,
    AxisNumberFormatter,
    DiscreteAxisFormatter,
    FramePlotter,
    GridFrame,
    LegendHelper,
    OctaveBandSpec,
    OneThirdOctavePlotter,
    PlotCategory,
    PlotDataset,
    PlotResult,
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


def _load_scalar_limit() -> ZVLLimit:
    return ZVLLimit.from_standard(
        ZVLLimitStandard.GB_10070_1988,
        scene="特殊住宅区昼间",
    )


def _load_curve_limit() -> OTOVLLimit:
    return OTOVLLimit.from_standard(
        OTOVLLimitStandard.GB_T_50355_2018,
        scene="卧室昼间一级",
    )


def test_plot_dataset_from_axis_value_uses_multiindex_and_default_label() -> None:
    dataset = PlotDataset.from_axis_value(
        axis=[0.0, 0.1, 0.2],
        value=[0.0, 0.2, -0.1],
        name="sample-1",
        category=PlotCategory.SAMPLE,
        axis_unit="second",
        value_unit="meter/second**2",
    )

    assert isinstance(dataset.to_dataframe(), pd.DataFrame)
    frame = dataset.to_dataframe()
    assert frame.index.ndim == 1
    assert isinstance(frame.columns, pd.MultiIndex)
    assert frame.columns.nlevels == 2
    assert frame.columns.tolist() == [(PlotCategory.SAMPLE.value, "sample-1")]

    meta = dataset.meta_frame()
    assert meta.loc[(PlotCategory.SAMPLE.value, "sample-1"), "label"] == "sample-1"
    assert meta.loc[(PlotCategory.SAMPLE.value, "sample-1"), "axis_unit"] == "second"
    assert meta.loc[(PlotCategory.SAMPLE.value, "sample-1"), "value_unit"] == "meter/second**2"


def test_plot_dataset_from_array2d_uses_first_column_as_axis() -> None:
    raw = np.array(
        [
            [1.0, 10.0, 12.0],
            [2.0, 11.0, 13.0],
            [4.0, 12.0, 14.0],
        ]
    )

    dataset = PlotDataset.from_array2d(
        raw,
        category=PlotCategory.SAMPLE,
        names=["curve-a", "curve-b"],
        axis_unit="hertz",
        value_unit="decibel",
    )

    frame = dataset.to_dataframe()
    np.testing.assert_allclose(frame.index.to_numpy(dtype=float), raw[:, 0])
    np.testing.assert_allclose(frame[(PlotCategory.SAMPLE.value, "curve-a")].to_numpy(), raw[:, 1])
    np.testing.assert_allclose(frame[(PlotCategory.SAMPLE.value, "curve-b")].to_numpy(), raw[:, 2])


def test_plot_dataset_add_limit_broadcasts_scalar_limit_to_given_axis() -> None:
    axis = np.array([1.0, 2.0, 4.0, 8.0])
    dataset = PlotDataset.from_axis_value(
        axis=axis,
        value=[60.0, 62.0, 63.0, 61.0],
        name="sample-1",
        category=PlotCategory.SAMPLE,
    )

    dataset.add_limit(
        _load_scalar_limit(),
        axis=axis,
        name="city-limit",
        category=PlotCategory.LIMIT,
    )

    frame = dataset.to_dataframe()
    limit_values = frame[(PlotCategory.LIMIT.value, "city-limit")].to_numpy()
    assert np.unique(limit_values).size == 1
    assert float(limit_values[0]) == 65.0


def test_plot_dataset_supports_minimal_meta_updates() -> None:
    dataset = PlotDataset.from_axis_value(
        axis=[1.0, 2.0, 4.0],
        value=[30.0, 32.0, 35.0],
        name="sample-a",
        category=PlotCategory.SAMPLE,
    )

    dataset.set_label(PlotCategory.SAMPLE, "sample-a", "主样本")
    dataset.set_style(
        PlotCategory.SAMPLE,
        "sample-a",
        {
            "color": "gray",
            "linewidth": 1.5,
        },
    )
    dataset.set_meta(
        PlotCategory.SAMPLE,
        "sample-a",
        axis_unit="hertz",
        value_unit="decibel",
        source_type="otovl-env",
    )

    meta = dataset.meta_frame()
    assert meta.loc[(PlotCategory.SAMPLE.value, "sample-a"), "label"] == "主样本"
    assert meta.loc[(PlotCategory.SAMPLE.value, "sample-a"), "axis_unit"] == "hertz"
    assert meta.loc[(PlotCategory.SAMPLE.value, "sample-a"), "value_unit"] == "decibel"
    assert meta.loc[(PlotCategory.SAMPLE.value, "sample-a"), "source_type"] == "otovl-env"
    assert meta.loc[(PlotCategory.SAMPLE.value, "sample-a"), "style"] == {
        "color": "gray",
        "linewidth": 1.5,
    }


def test_plot_dataset_avoids_fragmentation_warning_when_adding_many_columns() -> None:
    axis = np.array([1.0, 2.0, 4.0, 8.0], dtype=float)
    dataset = PlotDataset()

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", pd.errors.PerformanceWarning)
        for idx in range(32):
            dataset.add_axis_value(
                axis=axis,
                value=np.full(axis.shape[0], float(idx), dtype=float),
                name=f"series-{idx}",
                category=PlotCategory.SAMPLE,
            )

    performance_warnings = [item for item in caught if issubclass(item.category, pd.errors.PerformanceWarning)]
    assert performance_warnings == []


def test_frame_plotter_can_add_axis_value_and_filter_by_category_and_name() -> None:
    plotter = FramePlotter()
    plotter.add(
        axis=[0.0, 0.1, 0.2],
        value=[0.0, 0.2, -0.1],
        name="sample-a",
        category=PlotCategory.SAMPLE,
    )
    plotter.add(
        axis=[0.0, 0.1, 0.2],
        value=[0.1, 0.15, 0.12],
        name="envelope-a",
        category=PlotCategory.ENVELOPE,
    )

    result = plotter.plot(categories=[PlotCategory.SAMPLE], names=["sample-a"])
    assert isinstance(result, PlotResult)
    assert len(result.axes[0].lines) == 1
    assert result.axes[0].lines[0].get_label() == "sample-a"


def test_frame_plotter_accepts_model_directly_and_preserves_dataset() -> None:
    accel = AccelSeries.from_data(np.random.randn(64) * 0.01, dt=0.002)
    plotter = FramePlotter()

    plotter.add(accel)
    dataset = plotter.get_dataset()
    frame = dataset.to_dataframe()

    assert isinstance(dataset, PlotDataset)
    assert frame.shape[0] == accel.get_axis().shape[0]
    result = plotter.plot()
    assert isinstance(result, PlotResult)
    np.testing.assert_allclose(result.axes[0].lines[0].get_xdata(), accel.get_axis())


def test_one_third_octave_plotter_consumes_plot_dataset() -> None:
    accel = AccelSeries.from_data(np.random.randn(1200) * 0.01, dt=0.002)
    otovl = accel.eval_otovl(freq_range=(1.0, 80.0))
    assert isinstance(otovl, OTOVLEval)

    dataset = PlotDataset.from_model(
        otovl,
        category=PlotCategory.SAMPLE,
        name="otovl-sample",
    )
    dataset.add_limit(
        _load_curve_limit(),
        name="otovl-limit",
        category=PlotCategory.LIMIT,
    )

    result = OneThirdOctavePlotter().plot_dataset(dataset)
    assert isinstance(result, PlotResult)
    assert result.figure is not None
    assert len(result.axes[0].lines) >= 2


def test_story_value_plotter_consumes_plot_dataset_and_limit_columns() -> None:
    dataset = PlotDataset.from_axis_value(
        axis=[-1.0, 0.0, 1.0, 2.0],
        value=[0.001, 0.002, 0.003, 0.004],
        name="sample-a",
        category=PlotCategory.SAMPLE,
        axis_unit="story",
        value_unit="meter/second**2",
    )
    dataset.add_axis_value(
        axis=[-1.0, 0.0, 1.0, 2.0],
        value=[0.0012, 0.0022, 0.0032, 0.0042],
        name="stat-a",
        category=PlotCategory.STAT,
    )
    dataset.add_limit(
        _load_scalar_limit(),
        axis=[-1.0, 0.0, 1.0, 2.0],
        name="limit-a",
        category=PlotCategory.LIMIT,
    )

    result = StoryValuePlotter().plot_dataset(dataset)
    assert isinstance(result, PlotResult)
    assert result.figure is not None
    assert len(result.axes[0].lines) >= 2


def test_frame_plotter_adds_model_directly_without_payload_bridge() -> None:
    accel = AccelSeries.from_data(np.random.randn(200) * 0.01, dt=0.002)
    plotter = FramePlotter()

    plotter.add(accel, name="time-accel", category=PlotCategory.SAMPLE)
    result = plotter.plot()

    assert isinstance(result, PlotResult)
    assert result.figure is not None
    assert result.axes
    assert len(result.axes[0].lines) == 1
    assert result.axes[0].lines[0].get_label() == "time-accel"


def test_one_third_octave_plotter_adds_otovl_eval_as_comps_and_env() -> None:
    accel = AccelSeries.from_data(np.random.randn(1200) * 0.01, dt=0.002)
    otovl = accel.eval_otovl(freq_range=(1.0, 80.0))
    assert isinstance(otovl, OTOVLEval)

    plotter = OneThirdOctavePlotter()
    plotter.add(otovl)
    dataset = plotter.get_dataset()
    frame = dataset.to_dataframe()
    meta = dataset.meta_frame()

    sample_columns = [key for key in frame.columns.tolist() if key[0] == PlotCategory.SAMPLE.value]
    envelope_columns = [key for key in frame.columns.tolist() if key[0] == PlotCategory.ENVELOPE.value]

    assert sample_columns
    assert envelope_columns == [(PlotCategory.ENVELOPE.value, "env")]
    for key in sample_columns:
        assert meta.loc[key, "label"] == "_nolegend_"
        style = meta.loc[key, "style"]
        assert style["color"] == "lightgray"
    assert meta.loc[(PlotCategory.ENVELOPE.value, "env"), "label"] == "包络值"

    result = plotter.plot()
    assert isinstance(result, PlotResult)
    assert result.figure is not None
    legend = result.axes[0].get_legend()
    assert legend is not None
    legend_labels = [text.get_text() for text in legend.get_texts()]
    assert "包络值" in legend_labels
    assert "_nolegend_" not in legend_labels


def test_one_third_octave_plotter_adds_curve_limits_with_default_labels() -> None:
    limit = _load_curve_limit()
    plotter = OneThirdOctavePlotter()

    plotter.add(limit)
    dataset = plotter.get_dataset()
    meta = dataset.meta_frame()
    keys = dataset.to_dataframe().columns.tolist()

    assert keys == [(PlotCategory.LIMIT.value, f"{type(limit).__name__}:{limit.scene}")]
    assert meta.iloc[0]["label"] == limit.scene

    result = plotter.plot()
    assert isinstance(result, PlotResult)
    assert result.figure is not None
    assert result.axes[0].lines[0].get_label() == limit.scene


def test_story_value_plotter_adds_dataset_without_payload_bridge() -> None:
    plotter = StoryValuePlotter()
    plotter.add(
        axis=[-1.0, 0.0, 1.0, 2.0],
        value=[0.001, 0.002, 0.003, 0.004],
        name="sample-a",
        category=PlotCategory.SAMPLE,
    )
    plotter.add(
        axis=[-1.0, 0.0, 1.0, 2.0],
        value=[0.0035, 0.0035, 0.0035, 0.0035],
        name="limit-a",
        category=PlotCategory.LIMIT,
    )

    result = plotter.plot()
    assert isinstance(result, PlotResult)
    assert result.figure is not None
    assert result.axes


def test_plotting_module_no_longer_exports_function_dispatchers() -> None:
    fig, ax = plt.subplots()
    plotter = FramePlotter(ax=ax)
    plotter.add(
        axis=[0.0, 0.1, 0.2],
        value=[0.0, 0.1, -0.05],
        name="sample-a",
        category=PlotCategory.SAMPLE,
    )
    result = plotter.plot()

    assert isinstance(result, PlotResult)
    assert result.figure is fig
    assert result.axes[0] is ax
    assert not hasattr(dt_plotting, "render_payload")
    assert not hasattr(dt_plotting, "render_plotter")
    assert not hasattr(dt_plotting, "normalize_payload")
    assert not hasattr(FramePlotter, "render_input")
    assert not hasattr(FramePlotter, "render")


def test_frame_plotter_add_supports_model_and_array_inputs() -> None:
    accel = AccelSeries.from_data(np.random.randn(64) * 0.01, dt=0.002)
    plotter = FramePlotter()

    plotter.add(accel, name="accel-model", category=PlotCategory.SAMPLE)

    raw = np.column_stack(
        [
            accel.get_axis(),
            np.linspace(0.0, 1.0, accel.get_axis().shape[0]),
        ]
    )
    plotter.add(raw, category=PlotCategory.ENVELOPE, names=["array-a"])
    result = plotter.plot()
    assert isinstance(result, PlotResult)
    assert result.figure is not None
    assert len(result.axes[0].lines) == 2
    np.testing.assert_allclose(result.axes[0].lines[0].get_xdata(), accel.get_axis())
    np.testing.assert_allclose(result.axes[0].lines[1].get_xdata(), raw[:, 0])
    np.testing.assert_allclose(result.axes[0].lines[1].get_ydata(), raw[:, 1])


def test_axis_frame_and_octave_band_spec_are_exposed() -> None:
    assert AxisFrame.__module__ == "dyntool.plotting.axes"
    spec = OctaveBandSpec.from_default_table(lower_frequency=1.0, upper_frequency=80.0)
    assert spec.band_numbers_from_range()


def test_new_plotter_types_are_exposed_from_plotting_module() -> None:
    assert FramePlotter.__module__ == "dyntool.plotting.plotters"
    assert OneThirdOctavePlotter.__module__ == "dyntool.plotting.plotters"
    assert StoryValuePlotter.__module__ == "dyntool.plotting.plotters"


def test_axis_helper_types_are_exposed_from_plotting_module() -> None:
    assert AxisHelper.__module__ == "dyntool.plotting.axes"
    assert AxisNumberFormatter.__module__ == "dyntool.plotting.axes"
    assert DiscreteAxisFormatter.__module__ == "dyntool.plotting.axes"
    assert GridFrame.__module__ == "dyntool.plotting.axes"
    assert LegendHelper.__module__ == "dyntool.plotting.axes"


def test_axis_frame_supports_frame_base_and_axis_override(tmp_path) -> None:
    config_path = tmp_path / "axis_frame.toml"
    config_path.write_text(
        """
[frame.spine]
linewidth = 1.5
color = "black"
visible = true

[bottom.spine]
linewidth = 2.5
color = "red"
        """.strip(),
        encoding="utf-8",
    )

    frame = AxisFrame.from_file(config_path)
    fig, ax = plt.subplots()
    frame.apply(ax)

    assert ax.spines["left"].get_linewidth() == 1.5
    assert ax.spines["bottom"].get_linewidth() == 2.5
    assert ax.spines["bottom"].get_edgecolor()[:3] == matplotlib.colors.to_rgb("red")


def test_unified_plotting_config_is_consumed_by_zh_axis_grid_and_legend(tmp_path) -> None:
    config_path = tmp_path / "plotting.toml"
    config_path.write_text(
        """
[zh]
font.size = 9
axes.unicode_minus = false

[axis_frame.frame.spine]
linewidth = 1.2
color = "black"

[grid_frame.frame]
able = true
which = "major"
color = "#cccccc"
linewidth = 0.4
linestyle = "--"

[legend.frame]
framealpha = 1.0
edgecolor = "black"

[legend.one_third_octave]
ncol = 3
        """.strip(),
        encoding="utf-8",
    )

    font_name = configure_zh(config_path=str(config_path))
    assert font_name == "SongTNR"
    assert plt.rcParams["font.size"] == 9

    frame = AxisFrame.from_file(config_path)
    grid = GridFrame.from_file(config_path)
    helper = LegendHelper.from_file(config_path)

    fig, ax = plt.subplots()
    frame.apply(ax)
    grid.apply(ax)

    assert ax.spines["left"].get_linewidth() == 1.2
    assert helper.base_options["framealpha"] == 1.0
    assert helper.section_options("one_third_octave")["ncol"] == 3


def test_grid_frame_supports_frame_base_and_axis_override(tmp_path) -> None:
    config_path = tmp_path / "plotting.toml"
    config_path.write_text(
        """
[grid_frame.frame]
able = true
which = "major"
color = "#dddddd"
linewidth = 0.5

[grid_frame.x]
linestyle = "--"

[grid_frame.y]
which = "both"
linestyle = ":"
alpha = 0.8
        """.strip(),
        encoding="utf-8",
    )

    fig, ax = plt.subplots()
    ax.plot([0.0, 1.0], [0.0, 1.0])
    ax.minorticks_on()

    frame = GridFrame.from_file(config_path)
    frame.apply(ax)

    assert any(line.get_visible() for line in ax.get_xgridlines())
    assert any(line.get_visible() for line in ax.get_ygridlines())
    assert ax.get_xgridlines()[0].get_linestyle() == "--"
    assert ax.get_ygridlines()[0].get_linestyle() == ":"


def test_grid_frame_defaults_to_disabled_when_able_is_omitted() -> None:
    fig, ax = plt.subplots()
    ax.plot([0.0, 1.0], [0.0, 1.0])

    frame = GridFrame(
        params={
            "frame": {
                "which": "major",
                "color": "#dddddd",
                "linewidth": 0.5,
                "linestyle": "--",
            }
        }
    )
    frame.apply(ax)

    assert not any(line.get_visible() for line in ax.get_xgridlines())
    assert not any(line.get_visible() for line in ax.get_ygridlines())


def test_grid_frame_disabled_does_not_emit_matplotlib_warning() -> None:
    fig, ax = plt.subplots()
    ax.plot([0.0, 1.0], [0.0, 1.0])
    frame = GridFrame(
        params={
            "frame": {
                "able": False,
                "which": "major",
                "color": "#dddddd",
                "linewidth": 0.5,
                "linestyle": "--",
            }
        }
    )

    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        frame.apply(ax)

    assert all("First parameter to grid()" not in str(item.message) for item in captured)


def test_plotter_can_apply_grid_frame_without_overriding_existing_behavior() -> None:
    dataset = PlotDataset.from_axis_value(
        axis=[0.0, 1.0, 2.0],
        value=[1.0, 2.0, 3.0],
        name="sample-a",
        category=PlotCategory.SAMPLE,
    )
    fig, ax = plt.subplots()
    grid_frame = GridFrame(
        params={
            "frame": {
                "able": True,
                "which": "major",
                "color": "#dddddd",
                "linewidth": 0.5,
            },
            "x": {"linestyle": "--"},
        }
    )

    result = FramePlotter(ax=ax, grid_frame=grid_frame).plot_dataset(dataset)

    assert result.axes[0] is ax
    assert any(line.get_visible() for line in ax.get_xgridlines())


def test_legend_helper_supports_rename_filter_and_multiple_legends() -> None:
    fig, ax = plt.subplots()
    ax.plot([0.0, 1.0], [0.0, 1.0], label="sample-a")
    ax.plot([0.0, 1.0], [1.0, 0.0], label="limit-a")

    helper = LegendHelper(ax)
    first = helper.apply(
        legend_options={"loc": "upper left"},
        post_renamer={"sample-a": "样本A"},
        include_labels=["sample-a"],
    )
    second = helper.add(
        legend_options={"loc": "lower right"},
        post_renamer={"limit-a": "限值A"},
        include_labels=["limit-a"],
    )

    assert [text.get_text() for text in first.get_texts()] == ["样本A"]
    assert [text.get_text() for text in second.get_texts()] == ["限值A"]
    legends = [artist for artist in ax.artists if isinstance(artist, matplotlib.legend.Legend)]
    assert len(legends) >= 1


def test_axis_helper_continuous_side_supports_waveform_style_padding() -> None:
    x = np.linspace(0.0, 10.0, 200)
    y = np.sin(x) * 0.02
    fig, ax = plt.subplots()
    (line,) = ax.plot(x, y, label="wave")
    original_y = np.asarray(line.get_ydata(orig=True), dtype=float).copy()

    helper = AxisHelper(ax)
    helper.format_side(
        side="left",
        mode="continuous",
        data=y,
        baseline=0.0,
        height_ratio=0.2,
        num_segments=4,
        scientific=False,
    )

    np.testing.assert_allclose(np.asarray(line.get_ydata(orig=True), dtype=float), original_y)
    lower, upper = ax.get_ylim()
    expected_extent = np.max(np.abs(y)) * 1.2
    assert lower == pytest.approx(-expected_extent)
    assert upper == pytest.approx(expected_extent)
    assert len(ax.get_yticks()) == 5


def test_axis_helper_continuous_side_height_ratio_changes_padding_extent() -> None:
    y = np.asarray([0.0, 0.01, -0.02, 0.015], dtype=float)
    fig, ax = plt.subplots()

    helper = AxisHelper(ax)
    helper.format_side(
        side="left",
        mode="continuous",
        data=y,
        baseline=0.0,
        height_ratio=0.5,
        num_segments=4,
        scientific=False,
    )
    wide_extent = max(abs(bound) for bound in ax.get_ylim())

    helper.format_side(
        side="left",
        mode="continuous",
        data=y,
        baseline=0.0,
        height_ratio=0.2,
        num_segments=4,
        scientific=False,
    )
    narrow_extent = max(abs(bound) for bound in ax.get_ylim())

    assert wide_extent > narrow_extent


def test_axis_helper_no_longer_exposes_format_waveform() -> None:
    fig, ax = plt.subplots()

    helper = AxisHelper(ax)

    assert not hasattr(helper, "format_waveform")


def test_plotter_supports_weak_ax_binding_and_explicit_ax_override() -> None:
    dataset = PlotDataset.from_axis_value(
        axis=[0.0, 1.0, 2.0],
        value=[1.0, 2.0, 3.0],
        name="sample-a",
        category=PlotCategory.SAMPLE,
    )
    fig, (ax1, ax2) = plt.subplots(1, 2)
    plotter = FramePlotter(ax=ax1)

    result1 = plotter.plot_dataset(dataset)
    result2 = plotter.plot_dataset(dataset, ax=ax2)

    assert result1.axes[0] is ax1
    assert result2.axes[0] is ax2
    assert len(ax1.lines) == 1
    assert len(ax2.lines) == 1


def test_one_third_octave_plotter_uses_equal_spaced_positions() -> None:
    accel = AccelSeries.from_data(np.random.randn(1200) * 0.01, dt=0.002)
    otovl = accel.eval_otovl(freq_range=(1.0, 80.0))
    dataset = PlotDataset.from_model(otovl)

    result = OneThirdOctavePlotter().plot_dataset(dataset)
    ax = result.axes[0]
    first_line = ax.lines[0]
    expected_positions = np.arange(dataset.to_dataframe().shape[0], dtype=float)

    assert ax.get_xscale() == "linear"
    np.testing.assert_allclose(first_line.get_xdata(), expected_positions)
    xtick_texts = [tick.get_text() for tick in ax.get_xticklabels()]
    assert any(text == "1" for text in xtick_texts)
    assert any(text == "80" for text in xtick_texts)


def test_plotter_preserves_existing_legend_unless_explicitly_overridden() -> None:
    dataset = PlotDataset.from_axis_value(
        axis=[0.0, 1.0, 2.0],
        value=[1.0, 2.0, 3.0],
        name="sample-a",
        category=PlotCategory.SAMPLE,
    )
    fig, ax = plt.subplots()
    ax.plot([0.0, 1.0], [0.0, 1.0], label="existing")
    ax.legend(loc="lower left")

    plotter = FramePlotter()
    result = plotter.plot_dataset(dataset, ax=ax)
    legend = result.axes[0].get_legend()
    assert legend is not None
    assert [text.get_text() for text in legend.get_texts()] == ["existing"]

    result = plotter.plot_dataset(dataset, ax=ax, legend_options={"loc": "upper right"})
    legend = result.axes[0].get_legend()
    assert legend is not None
    labels = [text.get_text() for text in legend.get_texts()]
    assert "sample-a" in labels


def test_axis_helper_formats_continuous_axis_with_scientific_offset() -> None:
    values = np.array([0.001, 0.002, 0.003], dtype=float)
    fig, ax = plt.subplots()
    ax.plot([0.0, 1.0, 2.0], values, label="sample-a")

    helper = AxisHelper(ax)
    helper.format_side(
        side="left",
        mode="continuous",
        data=values,
        ticks=values,
        scientific=True,
        decimals=1,
    )

    labels = [tick.get_text() for tick in ax.get_yticklabels() if tick.get_text()]
    assert labels == ["1.0", "2.0", "3.0"]
    offset_text = ax.yaxis.get_offset_text().get_text()
    assert "10^{" in offset_text
    assert ("\u22123" in offset_text) or ("-3" in offset_text)


def test_axis_helper_preserves_scientific_offset_after_canvas_draw() -> None:
    values = np.array([0.01, 0.02, 0.03], dtype=float)
    fig, ax = plt.subplots()
    ax.plot([0.0, 1.0, 2.0], values, label="sample-a")

    helper = AxisHelper(ax)
    helper.format_side(
        side="left",
        mode="continuous",
        data=values,
        ticks=values,
        scientific=True,
        decimals=1,
    )

    fig.canvas.draw()

    offset_text = ax.yaxis.get_offset_text().get_text()
    assert "10^{" in offset_text
    assert ("\u22122" in offset_text) or ("-2" in offset_text)


def test_axis_helper_scientific_fontsize_defaults_to_tick_label_size() -> None:
    values = np.array([0.01, 0.02, 0.03], dtype=float)
    fig, ax = plt.subplots()
    ax.plot([0.0, 1.0, 2.0], values)
    ax.tick_params(axis="y", labelsize=11)

    helper = AxisHelper(ax)
    helper.format_side(
        side="left",
        mode="continuous",
        data=values,
        ticks=values,
        scientific=True,
    )

    assert ax.yaxis.get_offset_text().get_fontsize() == 11


def test_axis_helper_scientific_fontsize_can_be_overridden() -> None:
    values = np.array([0.01, 0.02, 0.03], dtype=float)
    fig, ax = plt.subplots()
    ax.plot([0.0, 1.0, 2.0], values)
    ax.tick_params(axis="y", labelsize=11)

    helper = AxisHelper(ax)
    helper.format_side(
        side="left",
        mode="continuous",
        data=values,
        ticks=values,
        scientific=True,
        scientific_fontsize=14,
    )

    assert ax.yaxis.get_offset_text().get_fontsize() == 14


def test_axis_helper_can_force_scientific_exponent() -> None:
    values = np.array([0.01, 0.02, 0.03], dtype=float)
    fig, ax = plt.subplots()
    ax.plot([0.0, 1.0, 2.0], values)

    helper = AxisHelper(ax)
    helper.format_side(
        side="left",
        mode="continuous",
        data=values,
        ticks=values,
        scientific=True,
        scientific_exponent=-3,
        decimals=1,
    )

    labels = [tick.get_text() for tick in ax.get_yticklabels() if tick.get_text()]
    assert labels == ["10.0", "20.0", "30.0"]
    offset_text = ax.yaxis.get_offset_text().get_text()
    assert "10^{" in offset_text
    assert ("\u22123" in offset_text) or ("-3" in offset_text)


def test_axis_helper_formats_continuous_axis_with_num_segments_and_tick_bounds() -> None:
    values = np.array([0.0015, 0.0025, 0.0035], dtype=float)
    fig, ax = plt.subplots()
    ax.plot([0.0, 1.0, 2.0], values)

    helper = AxisHelper(ax)
    helper.format_side(
        side="left",
        mode="continuous",
        data=values,
        num_segments=4,
        tick_min=0.0,
        tick_max=0.004,
        include_zero=True,
        scientific=True,
    )

    ticks = ax.get_yticks()
    np.testing.assert_allclose(ticks, np.linspace(0.0, 0.004, 5))
    labels = [tick.get_text() for tick in ax.get_yticklabels() if tick.get_text()]
    assert labels[0] == "0"
    assert labels[-1] == "4"
    offset_text = ax.yaxis.get_offset_text().get_text()
    assert "10^{" in offset_text
    assert ("\u22123" in offset_text) or ("-3" in offset_text)


def test_axis_helper_uses_tick_range_for_ticks_and_height_ratio_for_display_bounds() -> None:
    values = np.array([0.0015, 0.0025, 0.0035], dtype=float)
    fig, ax = plt.subplots()
    ax.plot([0.0, 1.0, 2.0], values)

    helper = AxisHelper(ax)
    helper.format_side(
        side="left",
        mode="continuous",
        data=values,
        tick_min=0.0,
        tick_max=0.004,
        num_segments=4,
        height_ratio=0.2,
        scientific=False,
    )

    np.testing.assert_allclose(ax.get_yticks(), np.linspace(0.0, 0.004, 5))
    lower, upper = ax.get_ylim()
    assert lower == pytest.approx(-0.0008)
    assert upper == pytest.approx(0.0048)


def test_axis_helper_uses_baseline_to_symmetrize_tick_range_when_bounds_not_given() -> None:
    values = np.array([-0.033, -0.002, 0.004, 0.026], dtype=float)
    fig, ax = plt.subplots()
    ax.plot([0.0, 1.0, 2.0, 3.0], values)

    helper = AxisHelper(ax)
    helper.format_side(
        side="left",
        mode="continuous",
        data=values,
        baseline=0.0,
        num_segments=4,
        scientific=False,
    )

    ticks = ax.get_yticks()
    np.testing.assert_allclose(ticks, np.linspace(-0.033, 0.033, 5))


def test_axis_helper_auto_ticks_choose_readable_step() -> None:
    values = np.array([1.2, 4.8], dtype=float)
    fig, ax = plt.subplots()
    ax.plot([0.0, 1.0], values)

    helper = AxisHelper(ax)
    helper.format_side(
        side="left",
        mode="continuous",
        data=values,
    )

    ticks = ax.get_yticks()
    np.testing.assert_allclose(ticks, np.array([1.0, 2.0, 3.0, 4.0, 5.0]))


def test_axis_helper_auto_ticks_can_include_zero_with_cross_zero_data() -> None:
    values = np.array([-0.23, 0.47], dtype=float)
    fig, ax = plt.subplots()
    ax.plot([0.0, 1.0], values)

    helper = AxisHelper(ax)
    helper.format_side(
        side="left",
        mode="continuous",
        data=values,
        include_zero=True,
    )

    ticks = ax.get_yticks()
    assert any(abs(tick) < 1e-12 for tick in ticks)
    diffs = np.diff(ticks)
    assert np.allclose(diffs, diffs[0])


def test_axis_helper_auto_ticks_handles_degenerate_interval() -> None:
    values = np.array([5.0, 5.0, 5.0], dtype=float)
    fig, ax = plt.subplots()
    ax.plot([0.0, 1.0, 2.0], values)

    helper = AxisHelper(ax)
    helper.format_side(
        side="left",
        mode="continuous",
        data=values,
    )

    ticks = ax.get_yticks()
    assert ticks.size >= 2
    assert np.all(np.isfinite(ticks))
    assert not np.allclose(ticks, ticks[0])


def test_axis_helper_formats_discrete_bottom_axis() -> None:
    fig, ax = plt.subplots()
    positions = np.arange(5, dtype=float)
    labels = ["1", "1.25", "1.6", "2", "2.5"]

    helper = AxisHelper(ax)
    helper.format_side(
        side="bottom",
        mode="discrete",
        positions=positions,
        labels=labels,
        show_every=2,
    )

    np.testing.assert_allclose(ax.get_xticks(), positions)
    tick_texts = [tick.get_text() for tick in ax.get_xticklabels()]
    assert tick_texts == ["1", "", "1.6", "", "2.5"]


def test_axis_helper_formats_discrete_top_axis_with_rotation_and_fontsize() -> None:
    fig, ax = plt.subplots()
    positions = np.arange(3, dtype=float)
    labels = ["10", "12.5", "16"]

    helper = AxisHelper(ax)
    helper.format_side(
        side="top",
        mode="discrete",
        positions=positions,
        labels=labels,
        rotation=30,
        fontsize=9,
    )

    np.testing.assert_allclose(ax.get_xticks(), positions)
    tick_texts = [tick.get_text() for tick in ax.get_xticklabels()]
    assert tick_texts == labels


def test_axis_helper_can_style_existing_legend() -> None:
    fig, ax = plt.subplots()
    ax.plot([0.0, 1.0], [0.0, 1.0], label="sample-a")
    legend = ax.legend(loc="lower left")
    assert legend is not None

    helper = AxisHelper(ax)
    legend = helper.set_legend(
        legend_options={"loc": "upper right", "ncol": 2, "framealpha": 1.0, "edgecolor": "black"}
    )

    assert legend._loc == 1
    assert len(legend.get_texts()) == 1


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


def test_plotting_module_no_longer_exports_payload_types() -> None:
    assert not hasattr(dt_plotting, "PlotPayload")
    assert not hasattr(dt_plotting, "PlotLinePayload")
    assert not hasattr(dt_plotting, "FramePlotPayload")
    assert not hasattr(dt_plotting, "FramePanelPayload")
    assert not hasattr(dt_plotting, "OctavePlotPayload")
    assert not hasattr(dt_plotting, "StorySeriesPayload")
    assert not hasattr(dt_plotting, "StoryLimitPayload")
    assert not hasattr(dt_plotting, "StoryValuePayload")
