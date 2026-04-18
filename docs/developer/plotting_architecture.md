# plotting 架构（v1.2.0）

稳定性：`Internal API`

## 说明

本页记录已经在 `v1.2.0` 合并到 `main` 的 plotting 收口结果。

当前 `main` 正处于正式 tag 前的最终审查阶段，因此本页描述的是已经落地的正式 plotting 主链与内部边界，而不是待实施的 breaking 方案。

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

## 与当前主线的关系

本页描述的 plotting 正式边界已经进入当前 `main`。

后续若继续演进 plotting，应从新的版本线或专题分支推进，而不是回退到旧的 compat / legacy 口径。
## 轴配置补充

`v1.2.0` 当前主线已把轴语义正式提升为独立公共对象：

- `AxisConfig`
- `ContinuousAxisSpec`
- `OctaveAxisSpec`

内部结构约束如下：

- `PlotTheme.axes` 继续只负责外观
- `PlotTheme.grid` 独立承载网格策略与样式，TOML 入口固定为 `grid.x.major / grid.x.minor / grid.y.major / grid.y.minor`
- 轴标签 TOML 入口固定为 `axis.x.label / axis.y.label`
- 轴语义 TOML 入口固定为 `axis.x / axis.y`
- `PlotTheme.axis_config` 只负责主题级默认轴语义
- plotting 正式 TOML schema 只使用 `grid.x.major / ...`、`axis.x.label / axis.y.label`、`axis.x / axis.y`
- 项目级 variant patch 仍属于项目层策略，不进入 `dyntool.plotting` 正式 schema
- plotting 内部适配层负责把公共 `AxisConfig` 转成 `AxisHelper.format_axis(...)` 所需参数；continuous 轴会在这一层统一处理 `ticks / major_step / minor_step / scientific_*`
- `AxisHelper`、`AxisFrame` 仍然只是 `Internal API`

运行时优先级固定为：

1. `plot_dataset(..., axis_config=...)`
2. plotter 构造参数 `axis_config`
3. `PlotTheme.axis_config`
4. plotter 内建默认行为

## 模块布局说明

当前 plotting 内部实现同时遵循仓库的 helper 聚合规则和模块内定义顺序规则，目标是让公开入口和底层细节的阅读路径分开。

推荐的阅读顺序与组织方式如下：

1. 模块常量与类型别名
2. 私有聚合对象，例如 parser / runtime / adapter / resolver
3. 对外公开类
4. 对外公开函数
5. 私有薄包装
6. 底层转换、校验和 `coerce` 细节
7. `__all__`

在 plotting 中，这条规则有两个直接例子：

- `_ThemeSchemaParser` 放在 `PlotTheme` 之前是合理的，因为 `PlotTheme.from_file(...)` 直接依赖它完成 schema 校验与负载组装。
- 不应在 `PlotTheme` 前后再散落一串自由 `_normalize_*` / `_coerce_*` helper；这类细节要么收进 parser 对象，要么后置到明确的内部实现层。

这条布局规则不要求所有 plotting 文件完全同构，但要求公开入口尽量连续，且不要被一组无关私有 helper 打断主流程。
