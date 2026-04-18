# plot_and_export

稳定性：`Public API`

任务目标：演示 plotting 的正式主链。示例会先通过 `PlotTheme.from_file(...)` 读取模板，再把原始数组和模型对象整理成 `PlotDataset`，最后交给 concrete plotter 绘图，并保留 `PlotResult.ax` 作为 Matplotlib 级微调出口。

## 主链

1. 从 `src/dyntool/plotting/assets/plot_theme_report.toml` 读取 `PlotTheme`
2. 把原始数组或模型对象整理成 `PlotDataset`
3. 调用 `FramePlotter`、`BoxPlotter` 或 `OneThirdOctavePlotter`
4. 通过 `result.ax` 做最后微调

## 正式入口

- `PlotTheme.from_file()`
- `PlotDataset.from_axis_value()`
- `PlotDataset.from_model()`
- `FramePlotter.plot_dataset()`
- `BoxPlotter.plot_dataset()`
- `OneThirdOctavePlotter.plot_dataset()`
- `PlotResult.ax`

## 说明

- `PlotTheme.default()` 只作为没有模板文件时的回退；本示例的正式口径以 `PlotTheme.from_file(...)` 为准
- `PlotTheme` 只负责图模板底座，不负责 payload 映射、图种语义或复杂 legend 处理
- 若需要临时 rename / filter / order legend，请在本次绘图调用里显式传参，或直接操作 `ax.legend(...)`
- 运行时可以通过 `FramePlotter(..., axis_config=...)` 或 `plot_dataset(..., axis_config=...)` 覆盖 `PlotTheme.axis_config`
- 当前主题文件已经统一切到点层级 schema：网格走 `grid.x.major / grid.y.major`，标签走 `axis.x.label / axis.y.label`，轴语义走 `axis.x / axis.y`
