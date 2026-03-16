# API 设计

`Public API`

AdvDynTool 的正式公开面收口为类 API 与独立模块 API，不再恢复历史 `DynTool` 多入口门面。

## 公开边界

- 正式公开：`AccelSeries`、`Metadata`、`Sample`、`SampleSet`
- 正式公开：`dyntool.storage`、`dyntool.plotting`、`dyntool.logging`
- `DynTool` 只保留 `resource` 和 `options`

## 设计原则

- 对象负责表达领域语义
- 模块负责正式服务入口
- 运行时与基础设施实现不直接暴露给普通使用者
