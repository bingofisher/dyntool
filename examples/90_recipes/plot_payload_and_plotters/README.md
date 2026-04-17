# plot_payload_and_plotters

稳定性：`Private / implementation detail`

此目录仅保留为历史占位，不再是正式 plotting 示例，也不再维护 payload-first 的可运行入口。

当前正式 plotting 主链为：

1. `PlotTheme.from_file(...)`
2. `PlotDataset.from_axis_value(...)` 或 `PlotDataset.from_model(...)`
3. `FramePlotter`、`BoxPlotter`、`OneThirdOctavePlotter`、`StoryValuePlotter`
4. `PlotResult.ax`

结论：

- payload-first 方案已移除，不再作为 plotting 正式数据契约
- v1.2.0 起，`configure_zh`、`AxisFrame`、`GridFrame`、`AxisHelper`、`LegendHelper`、`add()+plot()` 等 compat / legacy 入口已删除
- 如需正式示例，请改看 `examples/10_scenarios/05_plot_and_export/` 或 `examples/90_recipes/plot_dataset_and_plotters/`

当前无正式可运行代码；请直接使用上述目录中的示例入口。
