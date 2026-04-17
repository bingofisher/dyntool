# 绘图、日志与资源

稳定性：`Public API`

本页说明 `dyntool.plotting`、`dyntool.logging` 与 `dyntool.resources` 的正式用法。v1.2.0 起，plotting 的 compat/legacy 入口已删除，正式主链只保留 `PlotDataset.from_* -> PlotTheme.from_file/default -> ConcretePlotter.plot_dataset(..., ax=ax, ...) -> PlotResult.ax`。

## 最小可运行示例

```python
from pathlib import Path

import dyntool.logging as dt_logging
import dyntool.plotting as dt_plotting
import dyntool.resources as dt_resources

freqs, _ = dt_resources.center_freqs((2.0, 80.0))
logger = dt_logging.get_logger("demo")
logger.info("loaded %s frequencies", len(freqs))

theme_path = Path(dt_plotting.__file__).resolve().parent / "assets" / "plot_theme_report.toml"
theme = dt_plotting.PlotTheme.from_file(theme_path)
dataset = dt_plotting.PlotDataset.from_axis_value(
    axis=[0.0, 0.1, 0.2],
    value=[0.0, 0.1, -0.05],
    name="demo",
    category=dt_plotting.PlotCategory.SAMPLE,
)
result = dt_plotting.FramePlotter(theme=theme).plot_dataset(dataset)
print(result.ax is not None)
```

## 正式绘图

- 正式绘图只接受 `PlotDataset`
- 图模板由 `PlotTheme.default()` 或 `PlotTheme.from_file(...)` 提供
- 最终微调回到 `result.ax`
- 旧的 `configure_zh`、`AxisFrame`、`GridFrame`、`AxisHelper`、`LegendHelper` 不再作为正式入口

箱型图与普通曲线图都遵循同一主链，只是 `PlotDataset` 中的数据组织方式不同。

## 主题模板

`PlotTheme.from_file(...)` 只负责图模板底座，不负责图种语义、DataFrame 映射或复杂 legend 处理。模板文件建议直接从仓库资产读取。

## 正式能力

- `dyntool.plotting.PlotDataset`
- `dyntool.plotting.PlotTheme`
- `dyntool.plotting.PlotResult`
- `dyntool.plotting.FramePlotter`
- `dyntool.plotting.BoxPlotter`
- `dyntool.plotting.OneThirdOctavePlotter`
- `dyntool.plotting.StoryValuePlotter`
- `dyntool.logging.configure_logging(...)`
- `dyntool.logging.get_logger(...)`
- `dyntool.resources.keys()`
- `dyntool.resources.csv(...)`
- `dyntool.resources.center_freqs(...)`
