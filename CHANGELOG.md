# 更新日志

稳定性：`Public API`

## v1.2.0 - Unreleased / RC

### 版本线定位

- `v1.2.0` 是当前 breaking / RC 版本线。
- 主目录 `main` 继续承担 `1.1.x` 稳定线，不承接 `v1.2.0` 的 breaking 改动。
- 当前 worktree `.worktrees/v1.2.0` 只对应 `codex/v1.2.0`，用于收口 `1.2.0` 的正式发布内容。

### plotting 主链收敛

- 正式 plotting 主链固定为 `PlotDataset -> PlotTheme -> concrete plotter -> PlotResult.ax`。
- 删除旧的 plotting compat / legacy 主叙事，统一收口到正式公开面与模板主题入口。
- plotting 配置边界固定为 `locale / figure / axes / artist / legend`。

### reporting 正式纳入公开面

- 新增正式模块 `dyntool.reporting`，提供统计表导出、比较报告导出和报告包导出。
- `SampleSetBase` 新增薄对象方法，统一委托到 `dyntool.reporting`，保持对象主入口一致。
- 报告图件统一复用正式 plotting 主链，不再引入独立报告绘图系统。

### storage / infrastructure 收敛

- `SET_SQLITE_H5` 默认布局正式固定为 `v2`。
- 样本集读写、`summary_frame` 与报告导出链路已按当前正式实现收口。
- `StorageRuntime` 保留为 `Internal API` bridge，但不再作为正式公开门面的一部分。

### domain 内部收敛

- `SampleSetBase`、`TimeSeries` 主文件继续瘦身，内部 helper 结构与运行时委托链已收口到当前实现事实。
- 本轮收敛不改变对象类名、正式导入路径、单位语义与数值结果定义。

### 配套材料

- 迁移说明见 [docs/developer/migration_1_2_0.md](docs/developer/migration_1_2_0.md)
- 发布检查清单见 [docs/developer/release_checklist.md](docs/developer/release_checklist.md)

## v1.1.2 - 2026-04-04

### 当前阶段收口

- 完成 `SET_SQLITE_H5` v2 正式化、样本/样本集主链联动、自动识别、完整性校验与摘要对比相关收口。
- 同步测试、baseline、性能基线与仓库门禁，确保当前主目录中的单一集成主题具备可回归性。
- 收敛正式文档、开发者工作流与仓库卫生脚本，并建立本地补丁版本收口入口。

## v1.1.1 - 2026-03-30

### 公开口径回正

- 对齐 `README`、`ARCHITECTURE`、MkDocs 首页、使用总览与公开 API 页面，统一恢复 `DefaultSample / DefaultSampleSet` 为唯一正式顶层样本对象名。
- `Sample / SampleSet` 顶层导入已移除；这是一项针对公开口径不一致的破坏性修正。

### 存储与样本集主线说明补全

- 正式文档补充 `StorageConnectOptions`、`detect_storage_scheme(...)`、`inspect_storage_repository(...)` 的公开契约说明。
- 同步记录批量读写的 `show_progress` / `progress_callback`、`SET_SQLITE_H5` 大数据加载路径，以及 `compare_with(...)` 摘要级对比能力。
- README 与 API 页面明确 H5 默认 `gzip` 压缩、默认级别 `4` 以及 `data_options` 的早失败行为。

### 文档规则修正

- 修正文档规则页的编码约束文字，使其与当前测试守卫和资源 CSV 规则一致。

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
