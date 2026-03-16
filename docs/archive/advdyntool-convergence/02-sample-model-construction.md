# 阶段 02：模型与样本构造入口收敛

## 阶段目标
- 将模型、sample、sampleset 的公开构造入口收敛到可读、可提示、可扩展的动作优先命名。

## 前置依赖
- `01-rules-and-api-freeze.md`

## 命中 skills
- `writing-plans`
- `planning-with-files`
- `software-architecture`

## 3-subagent 角色分工
- 规划协调：分解门面、builder 和文档同步步骤
- 架构评审：裁定 `tool.models`、`tool.sample.create.*`、`tool.sampleset.create/load.*`
- 数值评审：保证建模命名调整不改变加速度输入建模语义

## Subagent Proposals
### Planning Coordination
- 先整理模型工厂，再整理 sample 和 sampleset 构造入口。

### Architecture Review
- 删除 `tool.sample.vibration.from_accel.*` 一类语义不清路径，统一使用动作优先命名。

### Numerical Review
- 保留现有 `from_accel` 数值建模逻辑，只调整公开入口组织方式。

## Cross Review
### Planning Coordination
- 赞同 builder 分层，否决继续增加重载。

### Architecture Review
- 赞同 `sample_domain=` 显式参数，否决路径前缀领域名。

### Numerical Review
- 条件赞同构造入口重组，前提是不改变 `AccelSeries.from_data(...)` 的输入语义。

## Consensus
- 模型类型按类型优先，样本和样本集按动作优先。

## Files to modify
- `src/dyntool/application/model_service.py`
- `src/dyntool/application/sample_service.py`
- `src/dyntool/application/factory.py`
- `src/dyntool/application/facade.py`
- `src/dyntool/__init__.py`
- `README.md`
- `ARCHITECTURE.md`
- `tests/typing_public_api.py`

## Files to create
- 可选：`src/dyntool/application/sample_builders.py`
- 可选：`src/dyntool/application/sampleset_loaders.py`

## Files to verify
- `src/dyntool/domain/metadata/*`
- `src/dyntool/domain/samples/*`

## 文件级操作步骤
1. 目标文件：`src/dyntool/application/model_service.py`
   - 变更目的：整理 `tool.models.*` 命名空间
   - 预期影响：模型构造入口统一到类型优先结构
   - 验证：IDE 能直接发现 `tool.models.accel.from_data(...)`
2. 目标文件：`src/dyntool/application/sample_service.py`
   - 变更目的：引入 `tool.sample.create.*` 和 `tool.sampleset.create/load.*`
   - 预期影响：样本构造和样本集加载职责分明
   - 验证：不再暴露语义不清的领域前缀路径
3. 目标文件：`src/dyntool/application/factory.py`
   - 变更目的：清理兼容入口和旧命名桥接
   - 预期影响：公开入口只剩 canonical 路径
   - 验证：工厂函数与门面设计一致
4. 目标文件：`README.md`、`ARCHITECTURE.md`、`tests/typing_public_api.py`
   - 变更目的：同步新命名和 `sample_domain=`
   - 预期影响：文档、类型检查和示例不再混用旧路径
   - 验证：静态检索不再出现 `tool.sample.vibration.*`

## 测试步骤
- 运行 `pyright tests/typing_public_api.py`
- 新增或更新 sample/sampleset 构造 smoke 测试
- 验证 `tool.models.*`、`tool.sample.create.*`、`tool.sampleset.load.*` 能被 IDE 自动补全识别

## 完成定义
- 样本和样本集构造入口按动作优先命名收敛完成
- `sample_domain=` 成为统一公开参数名
- 无领域前缀路径残留在文档和主公开 API 中

## 回滚与风险
- 若 sampleset 的“创建”和“加载”边界不清，需要先在本阶段补一层明确 namespace，再推进下一阶段。

