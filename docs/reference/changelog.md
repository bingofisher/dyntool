# 更新日志索引

稳定性：`Public API`

## 说明

本文用于提供版本变更索引与阅读入口。正式版本记录的真源仍然是仓库根级 `CHANGELOG.md`；发布时以仓库文件和对应 git tag 为准。

## 当前状态

- 当前稳定线：`1.2.x`
- 当前稳定线：`1.2.x`
- 当前正式发布版本：`v1.2.1`
- 前一稳定版本：`v1.2.0`
- 正式发布日期：`2026-04-21`

## 主要版本节点

### `v1.2.1`

- plotting 正式模板补齐 `grid`、`axis.label`、continuous `major/minor/scientific` 配置
- `OneThirdOctavePlotter` 正式接入 `axis.y = ContinuousAxisSpec`
- continuous `include_zero` 已移除，step 规划改用 `major_origin / minor_origin`，且默认按 `0` 起算
- continuous 轴默认不开科学计数法，只有显式开启时才启用
- reporting / storage / logging 内部聚合收口，公开 API 不变
- 新增仓库治理与 helper 结构检查，文档和示例同步收口

### `v1.2.0`

- plotting 正式主链固定为 `PlotDataset -> PlotTheme -> concrete plotter -> PlotResult.ax`
- `dyntool.reporting` 正式纳入公开面
- storage / runtime 内部边界进一步收紧

### `v1.1.2`

- 完成 `SET_SQLITE_H5` v2 正式化与样本集主链收口
- 同步测试、baseline、性能基线与仓库门禁
