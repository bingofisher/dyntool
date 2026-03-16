# 阶段 05：存储、日志、可视化收敛

## 阶段目标
- 统一存储门面、日志 provider 和 plotting 双通道接口。

## 前置依赖
- `01-rules-and-api-freeze.md`
- `03-sampling-and-units.md`
- `04-processing-evaluation-workflow.md`

## 命中 skills
- `writing-plans`
- `planning-with-files`
- `software-architecture`

## 3-subagent 角色分工
- 规划协调：拆分 I/O、日志、可视化三块并同步文档
- 架构评审：主审门面收敛、层边界和 provider 组织
- 数值评审：复核存储和绘图过程中的单位、采样和结果语义

## Subagent Proposals
### Planning Coordination
- 先收敛公开契约，再落地内部实现。

### Architecture Review
- 存储采用 `model/sample/sampleset/metadata` 同构门面，日志保留稳定外壳，plotting 提供 `preview` 和 `render` 两条路径。

### Numerical Review
- 存储和 plotting 要保留单位与采样信息的可追溯性。

## Cross Review
### Planning Coordination
- 赞同门面统一，否决先做后端重写。

### Architecture Review
- 赞同 provider registry，否决 `domain` 继续直接依赖第三方 logger。

### Numerical Review
- 条件赞同 plotting 双通道，前提是结果对象保留 figure/axes 等可复用句柄。

## Consensus
- 先定存储、日志、plotting 公开契约，再做内部整理。

## Files to modify
- `src/dyntool/application/storage_service.py`
- `src/dyntool/application/plot_service.py`
- `src/dyntool/application/plot_types.py`
- `src/dyntool/application/logging_service.py`
- `src/dyntool/application/options.py`
- `src/dyntool/infrastructure/config_logging.py`
- `src/dyntool/infrastructure/storage_types.py`
- `src/dyntool/domain/samples/sets.py`
- `README.md`
- `ARCHITECTURE.md`

## Files to create
- 可选：`src/dyntool/infrastructure/logging_registry.py`
- 可选：`src/dyntool/application/storage_namespaces.py`

## Files to verify
- `src/dyntool/infrastructure/storage.py`
- `src/dyntool/infrastructure/persistence.py`

## 文件级操作步骤
1. 目标文件：`src/dyntool/application/storage_service.py`、`src/dyntool/infrastructure/storage_types.py`
   - 变更目的：统一 `StorageConnectOptions` 和存储门面
   - 预期影响：`tool.storage.model/sample/sampleset/metadata` 对称
   - 验证：保存和加载路径结构一致
2. 目标文件：`src/dyntool/infrastructure/config_logging.py`、`src/dyntool/application/logging_service.py`
   - 变更目的：保留公开外壳，引入 provider registry
   - 预期影响：stdlib/loguru 都能通过统一 provider 接入
   - 验证：`domain` 层不再直接依赖第三方 logger
3. 目标文件：`src/dyntool/application/plot_service.py`、`src/dyntool/application/plot_types.py`
   - 变更目的：增加 `preview_*`、`render_*` 和 `PlotResult`
   - 预期影响：既可快速看图，也可复用 axes/figure
   - 验证：sample、sampleset、model 都能便捷调用

## 测试步骤
- 运行真实输入保存/加载 round-trip 测试
- 运行日志三模式测试
- 运行 plotting smoke 测试，覆盖默认建图和传入 `ax/fig`

## 完成定义
- 存储、日志、可视化公开门面稳定
- 单位与采样信息在 I/O 和 plotting 中可追溯
- 文档和示例统一使用新入口

## 回滚与风险
- 若日志 provider registry 引入过多复杂度，可先保留 stdlib provider 和 loguru provider 两个内置实现，不先开放更多扩展点。

