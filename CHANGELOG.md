# 更新日志

稳定性：`Public API`

## v1.2.0 - 待打正式 tag

### 版本线定位

- `v1.2.0` 已经合并到 `main`，当前处于正式 tag 前的最终审查阶段
- 当前 `main` 承接 `v1.2.0` 的最终收口与正式发布前验证
- 当前补丁分支 `codex/v1.2.0-finalize-tag` 仅用于正式 tag 前的最后修复
- 最终发布事实以通过审查后的 `main` 提交和对应 `v1.2.0` git tag 为准

### plotting 正式主链收口

- plotting 正式主链固定为 `PlotDataset -> PlotTheme -> concrete plotter -> PlotResult.ax`
- 删除旧的 plotting compat / legacy 主叙事，统一收口到正式公开面与模板主题入口
- plotting 配置边界固定为 `locale / figure / axes / artist / legend`

### reporting 正式纳入公开面

- 新增正式模块 `dyntool.reporting`，提供统计表导出、比较报告导出和报告包导出
- `SampleSetBase` 新增对象级薄委托，统一把统计导出与报告包导出交给 `dyntool.reporting`
- 报告图件统一复用正式 plotting 主链，不再引入独立报告绘图系统

### storage / infrastructure 收口

- `SET_SQLITE_H5` 默认布局正式固定为 `v2`
- 样本集读写、`summary_frame` 与报告导出链按当前正式实现收口
- `StorageRuntime` 保留为 `Internal API` bridge，但不再作为正式公开门面的一部分

### domain 内部收口

- `SampleSetBase`、`TimeSeries` 主文件继续瘦身，内部 helper 结构与运行时委托链已收口到当前实现事实
- 本轮收口不改变对象类名、正式导入路径、单位语义与数值结果定义

### 证明层与迁移验证

- 补齐 `dyntool.reporting` 的 public API、typing、示例、baseline 与文档
- 增加工程项目迁移验证，覆盖 `P-R2-5`、`P-R2-6`、`P-R2-7`
- 增加吞吐基线与 storage/reporting 热路径回归

### 配套材料

- 迁移说明见 [docs/developer/migration_1_2_0.md](docs/developer/migration_1_2_0.md)
- 发布检查清单见 [docs/developer/release_checklist.md](docs/developer/release_checklist.md)

## v1.1.2 - 2026-04-04

- 完成 `SET_SQLITE_H5` v2 正式化、样本/样本集主链联动、自动识别、完整性校验与摘要对比相关收口
- 同步测试、baseline、性能基线与仓库门禁，确保当前主目录中的单一集成主题具备可回归性
- 收口正式文档、开发者工作流与仓库卫生脚本，并建立本地补丁版本收口入口

## v1.1.1 - 2026-03-30

- 公开口径回正，统一恢复 `DefaultSample / DefaultSampleSet` 为唯一正式顶层样本对象名
- 补齐 `StorageConnectOptions`、`detect_storage_scheme(...)`、`inspect_storage_repository(...)` 的正式契约说明
- 记录批量读写的 `show_progress` / `progress_callback`、`SET_SQLITE_H5` 大数据加载路径与 `compare_with(...)` 能力

## v1.1.0 - 2026-03-19

- 完成公开面重整
- 资源模块统一为 `dyntool.resources`
- plotting 固定为 `matplotlib` 静态绘图路径
