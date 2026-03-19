# plot_dataset_and_plotters

适用场景：需要把显式 `axis/value`、数据模型和限值统一整理成 `PlotDataset`，再交给 plotter 绘制。  
最小代码：运行 `main.py`，查看 `PlotDataset + plotter` 主链下的原始曲线绘图和模型绘图，并在后处理阶段叠加 `AxisHelper`、`GridFrame` 或 `LegendHelper`。
常见误区：继续把 payload 当成 plotting 的正式主数据结构；当前正式主线是 `PlotDataset + plotter + AxisHelper`，统一 plotting 配置文件中的 `[zh]` 只由 `configure_zh()` 消费。
关联场景：`05_plot_and_export`
