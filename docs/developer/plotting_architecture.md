# plotting 架构（v1.2.0）

稳定性：`Internal API`

## 说明

本页描述 `v1.2.0` 版本线中的 plotting 正式边界。

`v1.2.0` 是 breaking 版本线，因此本页以新正式主链为准，不再保留主目录兼容线中的 plotting compat 入口口径。

## 正式主链

`v1.2.0` 的 plotting 正式主链固定为：

1. `PlotDataset.from_* (...)`
2. `PlotTheme.from_file(path)` 或 `PlotTheme.default()`
3. `ConcretePlotter(...).plot_dataset(dataset, ax=ax, ...)`
4. `PlotResult.ax`

约束：

- plotter 正式输入只允许 `PlotDataset`
- 不再支持 `add()+plot()` 状态式旧路径
- 不再支持 `DataFrame / ndarray / model / limit` 直接送入 plotter
- 最终微调统一回到 `result.ax`

## 正式公开面

`dyntool.plotting` 顶层正式公开面只保留：

- `PlotTheme`
- `PlotDataset`
- `PlotCategory`
- `PlotKind`
- `PlotResult`
- `PlotStatMetric`
- `FramePlotter`
- `BoxPlotter`
- `OneThirdOctavePlotter`
- `StoryValuePlotter`

以下对象在 `v1.2.0` 中不再属于正式公开面：

- `configure_zh`
- `ZhPlotConfig`
- `AxisFrame`
- `GridFrame`
- `AxisHelper`
- `LegendHelper`
- `PlotterBase`
- `PlotterKind`
- `axes.py`

## 职责边界

### `PlotTheme`

`PlotTheme` 只负责图模板底座：

- `locale`
- `figure`
- `axes`
- `artist`
- `legend`

不负责：

- 图种语义
- 每条数据参数
- DataFrame 映射
- 领域不变量

### `PlotDataset`

`PlotDataset` 负责这次要绘制的数据，以及每条数据的列级元数据，例如：

- `label`
- `category`
- `axis_unit`
- `value_unit`
- `style`
- `source_type`

### concrete plotter

具体 plotter 负责：

- 图种语义
- 图种默认值
- 绘制阶段的 tick / label 自动兜底
- 将 `PlotTheme`、`PlotDataset` 和运行时参数合并成最终绘图行为

### `PlotResult`

`PlotResult` 是正式结果对象，最关键的稳定出口是：

- `figure`
- `axes`
- `ax`

其中 `ax` 是最终手工微调出口。

## 样式优先级

`v1.2.0` 固定如下优先级：

1. 运行时显式参数
2. `PlotDataset.style`
3. `PlotTheme`
4. plotter 内置回退默认值

plotter 只负责补缺失项，不覆盖用户已经通过运行时、dataset 或 theme 显式给出的值。

## 内部实现边界

以下模块可以继续存在，但仅作为内部实现细节：

- `src/dyntool/plotting/_axes_frame.py`
- `src/dyntool/plotting/_axes_helpers.py`
- `src/dyntool/plotting/_axes_formatters.py`
- `src/dyntool/plotting/plotters.py` 内部骨架

它们不再承载兼容 facade，也不再作为文档推荐入口。

## 模板契约

`PlotTheme` 模板契约固定为五块：

- `locale`
- `figure`
- `axes`
- `artist`
- `legend`

详细字段白名单见：

- [绘图配置说明](../usage/06_plotting_config_reference.md)

## 与主目录的关系

主目录 `AdvDynTool` 继续承担稳定/兼容线职责。

本页只描述 `.worktrees/v1.2.0` 上 `codex/v1.2.0` 分支的 breaking 口径，不应回写到主目录的兼容叙事中。
