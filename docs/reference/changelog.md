# 更新日志索引

稳定性：`Public API`

## 说明

本文用于提供版本变更索引与阅读入口。正式发布记录的事实源仍然是仓库根目录 `CHANGELOG.md`；发布时以仓库文件和对应 git tag 为准。

## 当前状态

- 当前稳定线：`1.2.x`
- 当前正式发布版本：`v1.2.2`
- 前一稳定版本：`v1.2.1`
- 正式发布日期：`2026-05-18`

## 主要版本节点

### `v1.2.2`

- GUI 正式收口为唯一项目壳，主导航固定为 `总览 / 导入与筛选 / 数据处理 / 图形绘制`
- Web 保留源码、测试、构建包与依赖组，但项目定位降级为实验线，不再作为正式主线叙事
- 主库 compute facade、样本与 plotting 内部结构继续收敛，正式公开 API 不变
- 仓库版本线、文档导航、发布口径与治理脚本同步对齐 `1.2.2`

### `v1.2.1`

- plotting 正式模板补齐 `grid`、`axis.label` 与 continuous `major/minor/scientific` 配置
- `OneThirdOctavePlotter` 正式接入 `axis.y = ContinuousAxisSpec`
- continuous `include_zero` 已移除，step 规划改为 `major_origin / minor_origin`
- reporting / storage / logging 内部结构继续收口，公开 API 不变

### `v1.2.0`

- plotting 正式主链固定为 `PlotDataset -> PlotTheme -> concrete plotter -> PlotResult.ax`
- `dyntool.reporting` 正式纳入公开面
- storage / runtime 内部边界进一步收敛

### `v1.1.2`

- 完成 `SET_SQLITE_H5` v2 正式化与样本集主链收口
- 同步测试、baseline、性能基线与仓库门禁
