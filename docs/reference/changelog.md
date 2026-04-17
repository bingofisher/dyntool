# 更新日志索引

稳定性：`Public API`

## 说明

文档站内的本页用于提供版本变更索引与阅读入口。正式版本记录的真源仍然是仓库根级 `CHANGELOG.md`；发布时以仓库文件和对应 git tag 为准。

## 当前状态

- 当前主线状态：`main` 已合入 `v1.2.0` 候选内容，正在做正式 tag 前的最终审查
- 当前候选补丁线：`codex/v1.2.0-finalize-tag`
- 已发布 RC：`v1.2.0-rc.1`
- 待发布正式 tag：`v1.2.0`

## 主要版本节点

### `v1.2.0`（待打正式 tag）

- plotting 正式主链固定为 `PlotDataset -> PlotTheme -> concrete plotter -> PlotResult.ax`
- `dyntool.reporting` 正式纳入公开面
- storage / runtime 内部边界进一步收紧
- domain helper 结构继续收口，但不改变正式对象 API

### `v1.1.2`

- 完成 `SET_SQLITE_H5` v2 正式化与样本集主链收口
- 同步测试、baseline、性能基线与仓库门禁

### `v1.1.1`

- 公开口径回正，统一 `DefaultSample / DefaultSampleSet`
- 补齐 storage 主链说明与文档规则修正

### `v1.1.0`

- 完成公开面重整
- 资源模块统一到 `dyntool.resources`
- plotting 固定为 `matplotlib` 静态绘图路径
