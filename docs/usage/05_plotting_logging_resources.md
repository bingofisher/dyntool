# 绘图、日志与资源

稳定性：`Public API`

本页说明 `dyntool.plotting`、`dyntool.logging` 与 `dyntool.resources` 的正式用法。  
v1.2.0 起，plotting 的 compat/legacy 入口已删除，正式主链固定为：

`PlotDataset.from_* -> PlotTheme.from_file/default -> ConcretePlotter.plot_dataset(..., ax=ax, ...) -> PlotResult.ax`

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
- 运行时最终微调统一回到 `result.ax`
- `configure_zh`、`AxisFrame`、`GridFrame`、`AxisHelper`、`LegendHelper` 不再作为正式入口

## plotting 轴语义配置

`dyntool.plotting` 当前正式公开以下轴配置对象：

- `AxisConfig`
- `ContinuousAxisSpec`
- `OctaveAxisSpec`

使用规则：

- `PlotTheme.axes` 只负责轴框和 tick 外观
- `PlotTheme.grid` 只负责网格策略与样式
- TOML 中的标签入口是 `axis.x.label` / `axis.y.label`
- TOML 中的轴语义入口是 `axis.x` / `axis.y`
- `plot_dataset(..., axis_config=...)` 可在单次绘图时覆盖 theme 默认值

示例：

```python
import dyntool.plotting as dt_plotting

dataset = dt_plotting.PlotDataset.from_axis_value(
    axis=[2.0, 2.5, 3.15, 4.0, 5.0, 6.3],
    value=[60.0, 61.0, 62.0, 63.0, 64.0, 65.0],
    name="otovl",
    category=dt_plotting.PlotCategory.SAMPLE,
)
axis_config = dt_plotting.AxisConfig(
    x=dt_plotting.OctaveAxisSpec(show_every=2),
    y=dt_plotting.ContinuousAxisSpec(major_step=10.0, minor_step=5.0),
)
result = dt_plotting.OneThirdOctavePlotter(axis_config=axis_config).plot_dataset(dataset)
```

主题文件对应写法：

```toml
[grid.x.major]
enabled = true
color = "#b3b3b3"
linestyle = ":"
linewidth = 0.6

[grid.x.minor]
enabled = false

[grid.y.major]
enabled = false

[grid.y.minor]
enabled = false

[axis.x.label]
text = "频率 / Hz"
pad = 1.0

[axis.x]
kind = "octave"

[axis.x.formatter]
show_every = 2

[axis.y]
kind = "continuous"

[axis.y.ticks.major]
step = 10.0

[axis.y.ticks.minor]
step = 5.0
```

如果项目里存在 `C1 / C2 / C3 / C4` 这类“大同小异”的绘图差异，推荐保持 `AxisConfig` 仍只描述单轴语义，在项目层采用“base TOML + variant patch + `deep_update(...)`”模式选择变体，而不要把业务分支直接写进正式 schema。

## logging

`dyntool.logging` 的正式能力包括：

- `configure_logging(...)`
- `get_logger(...)`
- provider 注册与切换能力

推荐做法是先在应用入口统一配置日志，再在业务代码中按名称取 logger。

## resources

`dyntool.resources` 负责仓库内置资源读取。常用入口包括：

- `keys()`
- `csv(...)`
- `center_freqs(...)`

涉及频带、限值或其他内置资源时，优先复用 `dyntool.resources`，不要在项目层复制静态表。 
