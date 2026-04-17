# 绘图并导出

稳定性：`Public API`

任务目标：演示 plotting 的正式主链。示例会先通过 `PlotTheme.from_file(...)` 读取模板，再把原始数组和模型对象整理成 `PlotDataset`，最后交给 concrete plotter 绘图，并保留 `PlotResult.ax` 作为 Matplotlib 级微调出口。

运行命令：`uv run python -B examples/10_scenarios/05_plot_and_export/main.py`

本示例与 `examples._scenario_impls._scenario_plot_and_export(...)` 保持一致，真实流程如下：

1. 从 `src/dyntool/plotting/assets/plot_theme_report.toml` 读取 `PlotTheme`
2. 使用 `PlotDataset.from_axis_value(...)` 构造原始时程数据
3. 使用 `PlotDataset.from_model(...)` 构造模型对象数据
4. 使用 `FramePlotter(theme=theme).plot_dataset(dataset)` 绘制原始图和模型图
5. 使用 `BoxPlotter().plot_dataset(dataset, stats=[...])` 绘制箱型图
6. 通过 `PlotResult.ax` 继续微调，并导出 `raw_time.png`、`model_time.png` 和 `box_zvl.png`

关键 API：

- `PlotTheme.from_file()`
- `PlotDataset.from_axis_value()`
- `PlotDataset.from_model()`
- `FramePlotter(theme=theme).plot_dataset()`
- `BoxPlotter().plot_dataset()`
- `PlotResult.ax`

补充说明：

- `PlotTheme.default()` 只作为没有模板文件时的回退；本示例的正式口径以 `PlotTheme.from_file(...)` 为准
- v1.2.0 起，plotting compat / legacy 入口已删除，不再建议使用 `configure_zh`、`AxisFrame`、`GridFrame`、`LegendHelper`、`add()+plot()` 等旧路径

对应测试：`tests/test_examples_systems.py::test_scenario_plot_and_export`
