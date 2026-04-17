# plotting 配置参考

稳定性：`Public API`

本页描述 `PlotTheme` 的正式模板契约。v1.2.0 起，兼容入口 `configure_zh`、`ZhPlotConfig`、`AxisFrame`、`GridFrame`、`LegendHelper.from_file(...)` 等已删除，不再作为正式推荐路径。

## 正式入口

1. `PlotDataset.from_* (...)`
2. `PlotTheme.from_file(path)` 或 `PlotTheme.default()`
3. `ConcretePlotter(...).plot_dataset(dataset, ax=ax, ...)`
4. `PlotResult.ax`

`PlotTheme` 只负责图模板底座，不负责图种语义、数据映射或复杂 legend 规则。

## 最小模板结构

当前正式模板建议只保留以下块：

- `locale`
- `figure`
- `axes`
- `artist`
- `legend`

## `locale`

用于字体与负号显示。

## `figure`

用于整张图尺寸、分辨率和 `add_axes_rect`。

## `axes`

用于图框、刻度和网格的基础外观。

## `artist`

用于按 Matplotlib 方法名配置常见 artist 默认参数，例如 `artist.plot`、`artist.scatter`、`artist.axhline`、`artist.fill_between`。

## `legend`

用于图例默认样式。复杂 rename/filter/order/group 仍应在绘图阶段显式处理，或者直接调用 `ax.legend(...)`。

## 当前状态

- v1.2.0 已删除 plotting compat / legacy 入口
- 旧的 `[zh]`、`axis_frame.*`、`grid_frame.*`、`legend.*` 兼容模板不再作为正式口径
- 若需要更新模板文件，请直接沿 `PlotTheme.from_file(...)` 的正式 schema 调整
