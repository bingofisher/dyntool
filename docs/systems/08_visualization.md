# 可视化

- 适用对象：需要把对象输入归一化为 `PlotDataset` 并交给正式 plotter 渲染的使用者
- 对应示例：`examples/10_scenarios/05_plot_and_export/main.py`
- 对应测试：`tests/test_examples_systems.py::test_scenario_plot_and_export`

## 正式主链

v1.2.0 起，plotting 的正式主链固定为：

1. `PlotDataset.from_* (...)`
2. `PlotTheme.from_file(path)` 或 `PlotTheme.default()`
3. `ConcretePlotter(...).plot_dataset(dataset, ax=ax, ...)`
4. `PlotResult.ax`

旧的 `configure_zh`、`AxisFrame`、`GridFrame`、`AxisHelper`、`LegendHelper`、`add()+plot()` 和对象级 `.plot(...)` 入口已删除，不再作为正式依赖。

## 责任边界

### `PlotDataset`

`PlotDataset` 负责承载本次绘制的数据以及列级元数据，例如标签、类别、单位和样式。

### 具体 plotter

具体 plotter 负责图种语义、绘制流程、图种默认值以及 tick / label 自动兜底。

### `PlotResult`

`PlotResult` 是最终结果对象，正式应暴露 `figure`、`axes` 和 `ax`，并允许在 `result.ax` 上继续微调。

## 模板边界

`PlotTheme` 只负责图模板底座，不负责图种语义。DataFrame 到 `PlotDataset` 的映射也应单独放在数据构造阶段，而不是塞进模板配置主契约。
