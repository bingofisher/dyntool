# 可视化

- 稳定性：`Public API`
- 适用对象：需要把对象输入归一化为 `PlotDataset` 并交给正式 plotter 渲染的使用者
- 对应示例：`examples/10_scenarios/05_plot_and_export/main.py`
- 对应测试：`tests/test_examples_systems.py::test_scenario_plot_and_export`

## 用途

正式绘图采用 `PlotDataset + plotter` 结构：对象输入先归一化为 `PlotDataset`，再由 `dyntool.plotting` 中的 plotter 负责渲染。

当前正式约定如下：

- plotter 采用弱绑定 `Axes` 模型，可以保存默认 `Axes`，也可以在单次 `plot(..., ax=...)` 或 `plot_dataset(..., ax=...)` 时显式指定目标轴。
- `AxisFrame` 是独立于 `Axes` 生命周期的样式配置对象，按 `frame + top/bottom/left/right` 结构解析，并在真正绘制到目标轴时应用。
- `configure_zh(path)` 只消费统一 plotting 配置文件中的 `[zh]`，负责中文字体和 rcParams。
- `AxisFrame` 是轴外观层；`GridFrame` 是网格样式层；两者可共用同一配置文件，但不是同一个对象。
- `AxisHelper` 是公开轴行为层，负责连续轴格式化、离散轴标签与刻度规划。
- 波形图不再使用单独的 helper；统一走 `format_side(..., mode="continuous")`，其中 `height_ratio` 表示上下留白比例，`num_segments` 表示纵向分段数。
- `LegendHelper` 是公开图例后处理层，负责收集、筛选、重命名和多 legend。
- `AxisHelper` 内部进一步分为连续轴刻度规划、连续轴文本格式化与离散轴标签应用几部分；其中 `TickPlanner` 只属于内部实现细节。
- `OneThirdOctavePlotter` 使用等距频段轴：真实频率值保存在 `PlotDataset` 中，绘图时映射到等距位置，刻度文本显示真实频率。
- legend 默认由 plotter 按类型生成，但用户手工 legend 或显式 `legend_options` 拥有更高优先级。
