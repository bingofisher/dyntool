# 更新日志

稳定性：`Public API`

## v1.1.0 - 2026-03-19

### 公开面重整

- 完全移除 `DynTool`，正式入口统一为顶层对象 API 与正式模块 API。
- 顶层导出收紧，只保留核心对象、结果对象、限制对象与必要枚举。
- 正式模块固定为：
  - `dyntool.storage`
  - `dyntool.plotting`
  - `dyntool.logging`
  - `dyntool.config`
  - `dyntool.resources`

### 资源模块收口

- 正式资源模块从 `dyntool.resource` 统一为 `dyntool.resources`。
- 内置资源数据与正式资源 API 统一收口到 `src/dyntool/resources/`。
- `dyntool.resource` 已移除，不保留兼容别名。

### 绘图与日志

- plotting 正式固定为 `matplotlib` 静态绘图。
- 删除 `PlotBackend` 和公开 `backend=` 参数。
- logging 继续作为独立正式模块使用。

### 文档与规则

- 正式文档栈统一为 `MkDocs + Material + mkdocstrings`。
- 正式规则与正式文档不再把 `interfaces` 描述为当前实现层。
- 正式示例与正式门禁已同步到当前公开面。

### 迁移提示

- 将 `import dyntool.resource as dt_resource` 改为 `import dyntool.resources as dt_resources`
- 删除所有 `DynTool(...)` 用法，改为直接使用顶层对象 API 或正式模块 API
- 删除所有 `PlotBackend` 和 `backend=` 相关调用
