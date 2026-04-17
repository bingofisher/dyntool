# `1.1.2` 到 `1.2.0` 迁移说明

稳定性：`Internal API`

## 适用范围

本页用于说明从 `1.1.2` 稳定线迁移到 `1.2.0` breaking / RC 版本线时，需要关注的正式变化与建议路径。

当前版本线分工：

- `1.1.2`：稳定发布线
- `1.2.0`：breaking / RC 版本线

## 总体原则

本轮迁移不改变以下正式契约：

- 存储格式
- 单位语义
- `DefaultSample` / `DefaultSampleSet` 对象主入口
- 数值结果与评价结果定义

本轮迁移主要集中在：

- plotting 正式主链收口
- reporting 正式纳入公开面
- storage / runtime 内部边界收紧

## plotting 迁移

### 新的正式主链

`1.2.0` 中，正式 plotting 主链固定为：

1. `PlotDataset.from_* (...)`
2. `PlotTheme.default()` 或 `PlotTheme.from_file(...)`
3. `ConcretePlotter(...).plot_dataset(dataset, ax=ax, ...)`
4. 通过 `PlotResult.ax` 做最终微调

### 不再推荐的旧路径

以下入口不再属于 `1.2.0` 的正式主叙事：

- `configure_zh()`
- `AxisFrame.from_file()`
- `GridFrame.from_file()`
- `LegendHelper.from_file()`
- `add()+plot()`

如果旧项目仍依赖这些入口，建议继续停留在 `1.1.x` 稳定线，或在迁移时统一改到 `PlotTheme + PlotDataset + concrete plotter`。

### 主题配置

正式模板入口固定为 `PlotTheme`，并统一采用五块结构：

- `locale`
- `figure`
- `axes`
- `artist`
- `legend`

## reporting 新增公开面

`1.2.0` 正式新增 `dyntool.reporting`，用于工程交付导出：

- 统计表导出
- 比较报告导出
- 报告包导出

同时，`SampleSetBase` 提供对应的薄对象方法委托。

推荐迁移方式：

- 原先手写 `frame.to_excel(...)`、`frame.to_csv(...)` 的项目，优先切换到 `dyntool.reporting`
- 需要完整项目交付目录时，直接使用 `export_report_package(...)`

## storage / runtime 说明

### 保持不变的部分

- `dyntool.storage` 仍是正式公开门面
- `StorageScheme`、`StorageMode`、`StorageConnectOptions` 的正式契约保持不变
- `SET_H5` / `SET_SQLITE_H5` / `SET_DIR` 的正式语义保持不变

### 内部变化

- `StorageRuntime` 继续存在，但定位为 `Internal API` bridge
- 样本集批量读写、`summary_frame`、报告导出链路优先走优化后的底层路径
- 这些变化不要求用户修改正式调用方式

## 迁移建议

### 如果你的项目主要依赖稳定对象 API

可以先保持：

- `DefaultSample`
- `DefaultSampleSet`
- `dyntool.storage`
- `dyntool.logging`

只在需要时逐步接入新的 plotting / reporting 主链。

### 如果你的项目依赖旧 plotting helper

建议一次性完成迁移，不要在同一项目里长期混用：

- 旧 helper / compat 口径
- 新的 `PlotTheme + PlotDataset + concrete plotter` 口径

### 如果你的项目需要报告交付

优先迁移到：

- `dyntool.reporting`
- `SampleSetBase.export_*`

不要继续在项目脚本中维护第二套统计真源和报告目录拼装逻辑。

## 配套材料

- 变更记录见 [更新日志索引](../reference/changelog.md)
- 版本线规则见 [version_lines.md](version_lines.md)
- 发布前检查项见 [release_checklist.md](release_checklist.md)
