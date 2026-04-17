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

本例会输出原始曲线图、模型曲线图和箱型图；如果还需要 Matplotlib 级定制，继续从 `result.ax` 往下做即可。

补充说明：

- `PlotTheme.default()` 只是无外部模板时的回退，这个 recipe 的正式口径仍然是 `PlotTheme.from_file(...)`
- `PlotTheme` 只负责模板底座，不负责 payload 映射、图种语义或复杂 legend 策略
- 如需临时 rename/filter/order legend，请在本次绘图调用里显式传参，或直接操作 `ax.legend(...)`
- 不要再把 `configure_zh`、`AxisFrame`、`GridFrame`、`AxisHelper`、`LegendHelper` 或 `add()+plot()` 当作正式用法
