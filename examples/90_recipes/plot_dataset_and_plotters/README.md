# plot_dataset_and_plotters

稳定性：`Public API`

适用场景：需要把显式 `axis/value` 数据或模型对象统一整理成 `PlotDataset`，再沿 `PlotTheme.from_file(...) -> concrete plotter -> PlotResult.ax` 的正式主链输出图形。  
运行命令：`uv run python -B examples/90_recipes/plot_dataset_and_plotters/main.py`

当前 recipe 与 `examples._scenario_impls._recipe_plot_dataset_and_plotters(...)` 对齐，真实主链如下：

1. `theme = PlotTheme.from_file(Path(dt_plotting.__file__).resolve().parent / "assets" / "plot_theme_report.toml")`
2. `raw_dataset = PlotDataset.from_axis_value(...)`
3. `model_dataset = PlotDataset.from_model(...)`
4. `FramePlotter(theme=theme).plot_dataset(...)` 或 `BoxPlotter().plot_dataset(...)`
5. `result.ax`

补充说明：

- `PlotTheme.default()` 只是在没有模板文件时的回退；这个 recipe 的正式口径仍然是 `PlotTheme.from_file(...)`
- `PlotTheme` 只负责模板底座，不负责 payload 映射、图种语义或复杂 legend 策略
- 如需临时 rename / filter / order legend，请在本次绘图调用里显式传参，或直接操作 `ax.legend(...)`
- continuous 轴的正式语义统一走 `AxisConfig`
- 倍频程图当前正式支持 `x = OctaveAxisSpec` 与 `y = ContinuousAxisSpec`

推荐模板写法：

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
text = "时间 / s"
pad = 1.0
fontsize = 10.0

[axis.y.label]
text = '$a_{\mathrm{max}}$ / (m/s$^2$)'
pad = 1.0
fontsize = 11.0

[axis.x]
kind = "continuous"

[axis.x.ticks]
fontsize = 8.0

[axis.x.ticks.major]
step = 2.0
origin = 0.0

[axis.x.ticks.minor]
step = 1.0
origin = 0.0

[axis.y]
kind = "continuous"

[axis.y.formatter.scientific]
enabled = true
exponent = 3
```

补充口径：
- continuous 轴只要给了 `step`，对应 `origin` 默认按 `0` 起算；显式写出时用于改变步进锚点
- continuous 轴默认不开科学计数法；只有显式写 `formatter.scientific.enabled = true` 才启用
- `axis.<side>.label.fontsize` 控制轴标签字号，`axis.<side>.ticks.fontsize` 控制 ticklabel 字号

如果项目内只有 `C1 / C2` 这类轻微差异，推荐保留一份 base plotting TOML，再通过 variant patch 使用 `dyntool.config.read_config_file(...) + deep_update(...)` 合并，而不要把业务键直接写进 `AxisConfig`。  
不要再把 `configure_zh`、`AxisFrame`、`GridFrame`、`AxisHelper`、`LegendHelper` 或 `add()+plot()` 当作正式用法。 
