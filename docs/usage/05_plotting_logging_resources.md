# 绘图、日志与资源

稳定性：`Public API`

这一页说明三条正式入口：`dyntool.plotting`、`dyntool.logging` 和 `dyntool.resources`。它们分别负责静态绘图、独立日志配置和内置资源读取。对连续轴或离散轴做后处理时，正式主路径是 `AxisHelper.format_axis(...)`。

## 最短可运行用法

```python
import dyntool.logging as dt_logging
import dyntool.plotting as dt_plotting
import dyntool.resources as dt_resources

freqs, _ = dt_resources.center_freqs((2.0, 80.0))
logger = dt_logging.get_logger("demo")
logger.info("loaded %s frequencies", len(freqs))

dataset = dt_plotting.PlotDataset.from_axis_value(
    axis=[0.0, 0.1, 0.2],
    value=[0.0, 0.1, -0.05],
    name="demo",
    category=dt_plotting.PlotCategory.SAMPLE,
)
result = dt_plotting.FramePlotter().plot_dataset(dataset)
print(result.figure is not None)
```

箱型图同样走 `PlotDataset + plotter` 主链，只是把每个 `SAMPLE` 列解释为一组样本分布，把每个 `LIMIT` 列解释为一条水平限值线。

```python
box_dataset = dt_plotting.PlotDataset.from_axis_value(
    axis=[0.0, 1.0, 2.0],
    value=[64.0, 66.0, 65.0],
    name="point-a",
    category=dt_plotting.PlotCategory.SAMPLE,
    label="A点",
)
box_dataset.add_axis_value(
    axis=[0.0, 1.0, 2.0],
    value=[68.0, 69.0, 70.0],
    name="point-b",
    category=dt_plotting.PlotCategory.SAMPLE,
    label="B点",
)
box_result = dt_plotting.BoxPlotter().plot_dataset(
    box_dataset,
    stats=[dt_plotting.PlotStatMetric.MEAN],
    style_defaults={"box.facecolor": "#dddddd"},
    legend_options={"loc": "upper right"},
)
print(box_result.figure is not None)
```

线型 plotter 的 `style` 一般直接贴近 `matplotlib.axes.Axes.plot()` 常用参数，例如 `color`、`linewidth`、`linestyle`、`marker`。

`BoxPlotter` 的样式协议单独固定为列级 `PlotDataset.style -> BoxPlotter 解析 -> Axes.boxplot(*props)`：

```python
box_dataset.set_style(
    dt_plotting.PlotCategory.SAMPLE,
    "point-a",
    {
        "box.facecolor": "#dddddd",
        "mean.color": "blue",
        "flier.markerfacecolor": "red",
    },
)

result = dt_plotting.BoxPlotter().plot_dataset(
    box_dataset,
    stats=[dt_plotting.PlotStatMetric.MEAN, dt_plotting.PlotStatMetric.MEDIAN],
    style_defaults={"whisker.linestyle": "--"},
)
```

如果需要把限值叠加到箱型图上，正式推荐在同一 `Axes` 上再调用 `FramePlotter` 或其他线型 plotter，而不是把限值直接放进 `BoxPlotter` 的数据集。

`BoxPlotter` 正式支持的样式键如下：

- `box.facecolor`、`box.edgecolor`、`box.linewidth`、`box.linestyle`
- `whisker.color`、`whisker.linewidth`、`whisker.linestyle`
- `cap.color`、`cap.linewidth`、`cap.linestyle`
- `median.color`、`median.linewidth`、`median.linestyle`
- `mean.color`、`mean.linewidth`、`mean.linestyle`
- `flier.marker`、`flier.markerfacecolor`、`flier.markeredgecolor`、`flier.markersize`

## 正式能力

- `dyntool.plotting.PlotDataset`
- `dyntool.plotting.BoxPlotter`
- `dyntool.plotting.FramePlotter`
- `dyntool.plotting.PlotResult`
- `dyntool.logging.configure_logging(...)`
- `dyntool.logging.get_logger(...)`
- `dyntool.resources.keys()`
- `dyntool.resources.csv(...)`
- `dyntool.resources.center_freqs(...)`

## 相关 API

- `dyntool.plotting`
- `dyntool.logging`
- `dyntool.resources`
