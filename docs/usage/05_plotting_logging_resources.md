# 绘图、日志与资源

稳定性：`Public API`

这一页说明三条正式入口：`dyntool.plotting`、`dyntool.logging` 和 `dyntool.resources`。它们分别负责静态绘图、独立日志配置和内置资源读取。

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

## 正式能力

- `dyntool.plotting.PlotDataset`
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
