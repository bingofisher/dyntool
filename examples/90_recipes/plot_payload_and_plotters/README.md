# plot_payload_and_plotters

稳定性：`Private / implementation detail`

该目录仅作为历史占位保留，不再是正式 plotting 示例。

- 正式 plotting 主链已经统一为 `PlotDataset + plotter + AxisFrame + AxisHelper`
- payload-first 方案已移除，不再维护可运行入口
- 如需正式示例，请改看 `examples/90_recipes/plot_dataset_and_plotters/`

## 适用场景

不再适用新的正式 plotting 工作流。本目录仅用于避免历史空目录破坏仓库示例结构检查。

## 最小代码

当前无正式可运行代码。请改用 `examples/90_recipes/plot_dataset_and_plotters/main.py`。

## 常见误区

- 不要再把 payload 当作 plotting 主数据结构。
- 不要再新增 `to_plot_payload()` 或 `plotting.payloads` 一类兼容入口。

## 关联场景

- `examples/10_scenarios/05_plot_and_export/`
- `examples/90_recipes/plot_dataset_and_plotters/`
