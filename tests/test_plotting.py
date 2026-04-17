"""独立绘图模块测试。"""

from __future__ import annotations

import warnings
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pytest

matplotlib.use("Agg")

import dyntool.plotting as dt_plotting
from dyntool import (
    AccelSeries,
    DefaultSample,
    DefaultSampleSet,
    OTOVLEval,
    OTOVLLimit,
    OTOVLLimitStandard,
    SampleDomain,
    VibrationTestMetadata,
    ZVLLimit,
    ZVLLimitStandard,
)
from dyntool.plotting import (
    BoxPlotter,
    FramePlotter,
    OneThirdOctavePlotter,
    PlotCategory,
    PlotDataset,
    PlotResult,
    PlotStatMetric,
    PlotTheme,
    StoryValuePlotter,
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

    frame = dataset.to_dataframe()
    assert isinstance(frame, pd.DataFrame)
    assert frame.index.ndim == 1
    assert isinstance(frame.columns, pd.MultiIndex)
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
    axis = np.array([1.0, 2.0, 4.0, 8.0], dtype=float)
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


def test_plot_category_exposes_single_limit_only() -> None:
    values = {member.value for member in PlotCategory}

    assert values == {
        PlotCategory.SAMPLE.value,
        PlotCategory.ENVELOPE.value,
        PlotCategory.LIMIT.value,
        PlotCategory.STAT.value,
    }
    assert not hasattr(PlotCategory, "LIMIT_UPPER")
    assert not hasattr(PlotCategory, "LIMIT_LOWER")


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


def test_frame_plotter_can_plot_dataset_and_filter_by_category_and_name() -> None:
    dataset = PlotDataset.from_axis_value(
        axis=[0.0, 0.1, 0.2],
        value=[0.0, 0.2, -0.1],
        name="sample-a",
        category=PlotCategory.SAMPLE,
    )
    dataset.add_axis_value(
        axis=[0.0, 0.1, 0.2],
        value=[0.1, 0.15, 0.12],
        name="envelope-a",
        category=PlotCategory.ENVELOPE,
    )

    result = FramePlotter().plot_dataset(dataset, categories=[PlotCategory.SAMPLE], names=["sample-a"])
    assert isinstance(result, PlotResult)
    assert len(result.axes[0].lines) == 1
    assert result.axes[0].lines[0].get_label() == "sample-a"


def test_frame_plotter_uses_plot_dataset_from_model_and_preserves_result_ax() -> None:
    accel = AccelSeries.from_data(np.random.randn(64) * 0.01, dt=0.002)
    dataset = PlotDataset.from_model(
        accel,
        category=PlotCategory.SAMPLE,
        name="accel-sample",
    )
    result = FramePlotter().plot_dataset(dataset)

    assert isinstance(dataset, PlotDataset)
    assert isinstance(result, PlotResult)
    np.testing.assert_allclose(result.axes[0].lines[0].get_xdata(), accel.get_axis())
    assert result.ax is result.axes[0]


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


def test_box_plotter_consumes_plot_dataset_sample_columns_and_namespaced_styles() -> None:
    axis = [0.0, 1.0, 2.0, 3.0]
    dataset = PlotDataset.from_axis_value(
        axis=axis,
        value=[64.0, 66.0, 65.0, np.nan],
        name="point-b1",
        category=PlotCategory.SAMPLE,
        value_unit="decibel",
        label="B1\n地下车库\n中心",
        style={"box.facecolor": "#dddddd", "median.color": "purple"},
    )
    dataset.add_axis_value(
        axis=axis,
        value=[68.0, 69.0, 70.0, 71.0],
        name="point-b2",
        category=PlotCategory.SAMPLE,
        value_unit="decibel",
        label="B2\n隔振层\n中心",
        style={"box.facecolor": "#cccccc", "unknown.value": "ignored"},
    )

    result = BoxPlotter().plot_dataset(
        dataset,
        stats=[PlotStatMetric.MEAN, PlotStatMetric.MEDIAN],
        style_defaults={
            "box.facecolor": "#bbbbbb",
            "mean.color": "blue",
            "mean.linewidth": 1.5,
            "flier.markerfacecolor": "red",
            "whisker.linestyle": "--",
        },
        legend_options={"loc": "upper right"},
    )

    assert isinstance(result, PlotResult)
    assert result.figure is not None
    assert len(result.axes[0].patches) >= 2
    assert len(result.axes[0].lines) >= 4
    assert [tick.get_text() for tick in result.axes[0].get_xticklabels()] == [
        "B1\n地下车库\n中心",
        "B2\n隔振层\n中心",
    ]
    facecolors = [patch.get_facecolor()[:3] for patch in result.axes[0].patches[:2]]
    assert facecolors[0] == pytest.approx(matplotlib.colors.to_rgb("#dddddd"))
    assert facecolors[1] == pytest.approx(matplotlib.colors.to_rgb("#cccccc"))
    legend = result.axes[0].get_legend()
    assert legend is not None
    legend_labels = [text.get_text() for text in legend.get_texts()]
    assert "均值" in legend_labels
    assert "中位数" in legend_labels


def test_box_plotter_style_defaults_can_be_overridden_by_dataset_style() -> None:
    dataset = PlotDataset.from_axis_value(
        axis=[0.0, 1.0, 2.0],
        value=[64.0, 66.0, 65.0],
        name="point-b1",
        category=PlotCategory.SAMPLE,
        style={"mean.color": "green"},
    )

    result = BoxPlotter().plot_dataset(
        dataset,
        stats=[PlotStatMetric.MEAN],
        style_defaults={"mean.color": "blue"},
    )

    mean_lines = [line for line in result.axes[0].lines if line.get_color() == "green"]
    assert mean_lines


def test_story_value_plotter_supports_auto_stat_metrics() -> None:
    dataset = PlotDataset.from_axis_value(
        axis=[-1.0, 0.0, 1.0],
        value=[1.0, 3.0, 5.0],
        name="sample-a",
        category=PlotCategory.SAMPLE,
    )
    dataset.add_axis_value(
        axis=[-1.0, 0.0, 1.0],
        value=[3.0, 5.0, 7.0],
        name="sample-b",
        category=PlotCategory.SAMPLE,
    )

    result = StoryValuePlotter().plot_dataset(
        dataset,
        stats=[PlotStatMetric.MEAN],
        legend_options={"loc": "upper right"},
    )

    stat_lines = [line for line in result.axes[0].lines if line.get_label() == "均值"]
    assert len(stat_lines) == 1
    np.testing.assert_allclose(stat_lines[0].get_xdata(), np.array([2.0, 4.0, 6.0], dtype=float))
    np.testing.assert_allclose(stat_lines[0].get_ydata(), np.array([-1.0, 0.0, 1.0], dtype=float))


def test_frame_plotter_supports_auto_stat_metrics() -> None:
    dataset = PlotDataset.from_axis_value(
        axis=[0.0, 1.0, 2.0],
        value=[1.0, 3.0, 5.0],
        name="sample-a",
        category=PlotCategory.SAMPLE,
    )
    dataset.add_axis_value(
        axis=[0.0, 1.0, 2.0],
        value=[3.0, 5.0, 7.0],
        name="sample-b",
        category=PlotCategory.SAMPLE,
    )

    result = FramePlotter().plot_dataset(
        dataset,
        stats=[PlotStatMetric.MEAN],
        legend_options={"loc": "upper right"},
    )

    stat_lines = [line for line in result.axes[0].lines if line.get_label() == "均值"]
    assert len(stat_lines) == 1
    np.testing.assert_allclose(stat_lines[0].get_ydata(), np.array([2.0, 4.0, 6.0], dtype=float))


def test_box_plotter_rejects_dataset_without_valid_sample_values() -> None:
    dataset = PlotDataset.from_axis_value(
        axis=[0.0, 1.0, 2.0],
        value=[np.nan, np.nan, np.nan],
        name="point-b1",
        category=PlotCategory.SAMPLE,
    )

    with pytest.raises(ValueError, match="箱型图至少需要一组非空样本。"):
        BoxPlotter().plot_dataset(dataset)


def test_plotting_module_no_longer_exports_function_dispatchers() -> None:
    fig, ax = plt.subplots()
    dataset = PlotDataset.from_axis_value(
        axis=[0.0, 0.1, 0.2],
        value=[0.0, 0.1, -0.05],
        name="sample-a",
        category=PlotCategory.SAMPLE,
    )
    result = FramePlotter(ax=ax).plot_dataset(dataset)

    assert isinstance(result, PlotResult)
    assert result.figure is fig
    assert result.axes[0] is ax
    assert not hasattr(dt_plotting, "render_payload")
    assert not hasattr(dt_plotting, "render_plotter")
    assert not hasattr(dt_plotting, "normalize_payload")
    assert not hasattr(FramePlotter, "render_input")
    assert not hasattr(FramePlotter, "render")


def test_new_plotter_types_are_exposed_from_plotting_module() -> None:
    assert BoxPlotter.__module__ == "dyntool.plotting.plotters"
    assert FramePlotter.__module__ == "dyntool.plotting.plotters"
    assert OneThirdOctavePlotter.__module__ == "dyntool.plotting.plotters"
    assert StoryValuePlotter.__module__ == "dyntool.plotting.plotters"


def test_object_level_plotting_api_is_removed() -> None:
    accel = AccelSeries.from_data([0.0, 0.1, -0.05], dt=0.01)
    sample = DefaultSample.from_accel_data(
        [0.0, 0.1, -0.02],
        dt=0.01,
        sample_domain=SampleDomain.VIBRATION_TEST,
        metadata_cls=VibrationTestMetadata,
        **_make_vibration_kwargs(),
    )
    sample_set = DefaultSampleSet.from_samples([sample], sample_domain=SampleDomain.VIBRATION_TEST)

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


def test_plot_result_exposes_primary_ax_property() -> None:
    fig, ax = plt.subplots()

    result = PlotResult.from_raw(ax)

    assert result.figure is fig
    assert result.axes == (ax,)
    assert result.ax is ax


def test_plot_theme_default_exposes_minimal_template_contract() -> None:
    theme = PlotTheme.default()

    assert theme.locale["font_family"] == "sans-serif"
    assert theme.locale["unicode_minus"] is False
    assert theme.figure["width_cm"] > 0
    assert theme.figure["height_cm"] > 0
    assert theme.figure["dpi"] > 0
    assert isinstance(theme.figure["add_axes_rect"], tuple)
    assert theme.axes["tick_direction"] == "in"
    assert theme.legend["frameon"] is False
    assert theme.artist_options("plot")["linewidth"] > 0


def test_plot_theme_from_file_supports_new_minimal_schema(tmp_path) -> None:
    config_path = tmp_path / "plot_theme.toml"
    config_path.write_text(
        """
[locale]
font_family = "sans-serif"
sans_serif = ["SongTNR", "Microsoft YaHei"]
math_fontset = "stix"
unicode_minus = false

[figure]
width_cm = 15.0
height_cm = 9.0
dpi = 180
add_axes_rect = [0.1, 0.2, 0.7, 0.6]

[axes]
spine_top = false
spine_bottom = true
spine_left = true
spine_right = false
spine_linewidth = 1.1
tick_length = 4.0
tick_width = 0.9
minor_tick_length = 2.5
minor_tick_width = 0.7
tick_direction = "out"
grid_linewidth = 0.4

[artist.plot]
linewidth = 2.0
linestyle = "--"
markersize = 5.0
color = "green"
marker = "s"
alpha = 0.8

[legend]
loc = "upper right"
fontsize = 10
frameon = true
ncol = 2
        """.strip(),
        encoding="utf-8",
    )

    theme = PlotTheme.from_file(config_path)

    assert theme.figure["width_cm"] == 15.0
    assert theme.figure["height_cm"] == 9.0
    assert theme.figure["dpi"] == 180
    assert theme.figure["add_axes_rect"] == (0.1, 0.2, 0.7, 0.6)
    assert theme.axes["spine_linewidth"] == 1.1
    assert theme.axes["tick_direction"] == "out"
    assert theme.legend["loc"] == "upper right"
    assert theme.legend["ncol"] == 2
    assert theme.artist_options("plot")["linewidth"] == 2.0
    assert theme.artist_options("plot")["marker"] == "s"


def test_plot_theme_from_file_rejects_unknown_top_level_block(tmp_path) -> None:
    config_path = tmp_path / "plot_theme_invalid.toml"
    config_path.write_text(
        """
[locale]
font_family = "sans-serif"
sans_serif = ["SongTNR"]
math_fontset = "stix"
unicode_minus = false

[figure]
width_cm = 14.0
height_cm = 10.0
dpi = 150
add_axes_rect = [0.12, 0.14, 0.82, 0.78]

[unknown]
enabled = true
        """.strip(),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="PlotTheme 配置存在未支持的顶层块"):
        PlotTheme.from_file(config_path)


def test_plot_theme_from_file_rejects_invalid_figure_field_type(tmp_path) -> None:
    config_path = tmp_path / "plot_theme_invalid_type.toml"
    config_path.write_text(
        """
[locale]
font_family = "sans-serif"
sans_serif = ["SongTNR"]
math_fontset = "stix"
unicode_minus = false

[figure]
width_cm = "wide"
height_cm = 10.0
dpi = 150
add_axes_rect = [0.12, 0.14, 0.82, 0.78]
        """.strip(),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="figure.width_cm 必须为数字。"):
        PlotTheme.from_file(config_path)


def test_frame_plotter_can_consume_plot_theme_defaults(tmp_path) -> None:
    config_path = tmp_path / "plot_theme.toml"
    config_path.write_text(
        """
[locale]
font_family = "sans-serif"
sans_serif = ["SongTNR"]
math_fontset = "stix"
unicode_minus = false

[figure]
width_cm = 14.0
height_cm = 10.0
dpi = 150
add_axes_rect = [0.12, 0.14, 0.82, 0.78]

[axes]
spine_top = false
spine_bottom = true
spine_left = true
spine_right = false
spine_linewidth = 1.2
tick_length = 3.5
tick_width = 0.9
minor_tick_length = 2.5
minor_tick_width = 0.7
tick_direction = "in"
grid_linewidth = 0.6

[artist.plot]
linewidth = 2.5
linestyle = "--"
markersize = 6.0
color = "purple"
marker = "o"
alpha = 0.7

[legend]
loc = "upper right"
fontsize = 9
frameon = false
ncol = 1
        """.strip(),
        encoding="utf-8",
    )
    theme = PlotTheme.from_file(config_path)
    dataset = PlotDataset.from_axis_value(
        axis=[0.0, 1.0, 2.0],
        value=[1.0, 2.0, 3.0],
        name="sample-a",
        category=PlotCategory.SAMPLE,
    )

    result = FramePlotter(theme=theme).plot_dataset(dataset)

    ax = result.ax
    assert ax is not None
    line = ax.lines[0]
    assert line.get_linewidth() == pytest.approx(2.5)
    assert line.get_linestyle() == "--"
    assert line.get_marker() == "o"
    assert line.get_alpha() == pytest.approx(0.7)
    assert ax.spines["left"].get_linewidth() == pytest.approx(1.2)
    assert ax.spines["top"].get_visible() is False


def test_frame_plotter_dataset_style_overrides_theme_defaults(tmp_path) -> None:
    config_path = tmp_path / "plot_theme.toml"
    config_path.write_text(
        """
[locale]
font_family = "sans-serif"
sans_serif = ["SongTNR"]
math_fontset = "stix"
unicode_minus = false

[figure]
width_cm = 14.0
height_cm = 10.0
dpi = 150
add_axes_rect = [0.12, 0.14, 0.82, 0.78]

[axes]
spine_top = false
spine_bottom = true
spine_left = true
spine_right = false
spine_linewidth = 1.2
tick_length = 3.5
tick_width = 0.9
minor_tick_length = 2.5
minor_tick_width = 0.7
tick_direction = "in"
grid_linewidth = 0.6

[artist.plot]
linewidth = 2.5
linestyle = "--"
markersize = 6.0
color = "purple"
marker = "o"
alpha = 0.7

[legend]
loc = "upper right"
fontsize = 9
frameon = false
ncol = 1
        """.strip(),
        encoding="utf-8",
    )
    theme = PlotTheme.from_file(config_path)
    dataset = PlotDataset.from_axis_value(
        axis=[0.0, 1.0, 2.0],
        value=[1.0, 2.0, 3.0],
        name="sample-a",
        category=PlotCategory.SAMPLE,
        style={"color": "green", "linewidth": 3.0},
    )

    result = FramePlotter(theme=theme).plot_dataset(dataset)

    line = result.ax.lines[0]
    assert line.get_color() == "green"
    assert line.get_linewidth() == pytest.approx(3.0)
    assert line.get_linestyle() == "--"
    assert line.get_marker() == "o"
    assert line.get_alpha() == pytest.approx(0.7)


def test_frame_plotter_runtime_legend_options_override_theme_defaults(tmp_path) -> None:
    config_path = tmp_path / "plot_theme.toml"
    config_path.write_text(
        """
[locale]
font_family = "sans-serif"
sans_serif = ["SongTNR"]
math_fontset = "stix"
unicode_minus = false

[figure]
width_cm = 14.0
height_cm = 10.0
dpi = 150
add_axes_rect = [0.12, 0.14, 0.82, 0.78]

[axes]
spine_top = false
spine_bottom = true
spine_left = true
spine_right = false
spine_linewidth = 1.2
tick_length = 3.5
tick_width = 0.9
minor_tick_length = 2.5
minor_tick_width = 0.7
tick_direction = "in"
grid_linewidth = 0.6

[legend]
loc = "lower left"
fontsize = 8
frameon = false
ncol = 1
        """.strip(),
        encoding="utf-8",
    )
    theme = PlotTheme.from_file(config_path)
    dataset = PlotDataset.from_axis_value(
        axis=[0.0, 1.0, 2.0],
        value=[1.0, 2.0, 3.0],
        name="sample-a",
        category=PlotCategory.SAMPLE,
    )

    result = FramePlotter(theme=theme).plot_dataset(
        dataset,
        legend_options={"loc": "upper right", "ncol": 2, "frameon": True},
    )

    legend = result.ax.get_legend()
    assert legend is not None
    assert legend._loc == 1
    assert legend._ncols == 2
    assert legend.get_frame_on() is True


def test_frame_plotters_can_overlay_on_same_axes_with_theme_defaults() -> None:
    theme = PlotTheme.default()
    dataset_a = PlotDataset.from_axis_value(
        axis=[0.0, 1.0, 2.0],
        value=[1.0, 2.0, 3.0],
        name="sample-a",
        category=PlotCategory.SAMPLE,
    )
    dataset_b = PlotDataset.from_axis_value(
        axis=[0.0, 1.0, 2.0],
        value=[3.0, 2.0, 1.0],
        name="sample-b",
        category=PlotCategory.SAMPLE,
    )

    fig, ax = plt.subplots()
    result_a = FramePlotter(theme=theme).plot_dataset(dataset_a, ax=ax)
    result_b = FramePlotter(theme=theme).plot_dataset(dataset_b, ax=ax)

    assert result_a.ax is ax
    assert result_b.ax is ax
    assert len(ax.lines) == 2


def test_plot_theme_asset_templates_are_loadable() -> None:
    theme_dir = Path(dt_plotting.__file__).resolve().parent / "assets"

    report_theme = PlotTheme.from_file(theme_dir / "plot_theme_report.toml")
    octave_theme = PlotTheme.from_file(theme_dir / "plot_theme_one_third_octave.toml")

    assert report_theme.figure["width_cm"] > 0
    assert octave_theme.figure["width_cm"] > 0
    assert report_theme.legend["loc"]
    assert octave_theme.artist_options("plot")


def test_plotting_module_exports_match_stage_c_public_surface() -> None:
    assert set(dt_plotting.__all__) == {
        "BoxPlotter",
        "FramePlotter",
        "OneThirdOctavePlotter",
        "PlotCategory",
        "PlotDataset",
        "PlotKind",
        "PlotResult",
        "PlotStatMetric",
        "PlotTheme",
        "StoryValuePlotter",
    }


def test_plotting_module_no_longer_exports_compat_entries() -> None:
    for name in (
        "AxisFrame",
        "AxisHelper",
        "GridFrame",
        "LegendHelper",
        "PlotterBase",
        "PlotterKind",
        "ZhPlotConfig",
        "configure_zh",
    ):
        assert not hasattr(dt_plotting, name)


def test_plotting_module_no_longer_exports_payload_types() -> None:
    assert not hasattr(dt_plotting, "PlotPayload")
    assert not hasattr(dt_plotting, "PlotLinePayload")
    assert not hasattr(dt_plotting, "FramePlotPayload")
    assert not hasattr(dt_plotting, "FramePanelPayload")
    assert not hasattr(dt_plotting, "OctavePlotPayload")
    assert not hasattr(dt_plotting, "StorySeriesPayload")
    assert not hasattr(dt_plotting, "StoryLimitPayload")
    assert not hasattr(dt_plotting, "StoryValuePayload")
