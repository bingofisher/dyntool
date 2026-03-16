# 阶段 04：处理与评估同构工作流

## 阶段目标
- 建立顶层、sample、sampleset 三层完全同构的 `processing/evaluation` 工作流和 flow/batch 语义。

## 前置依赖
- `03-sampling-and-units.md`

## 命中 skills
- `writing-plans`
- `planning-with-files`
- `software-architecture`
- `scipy-best-practices`

## 3-subagent 角色分工
- 规划协调：拆分 façade、对象级命名空间和 flow/batch 步骤
- 架构评审：主审命名空间同构与职责边界
- 数值评审：主审处理与评估入口在采样、单位和结果语义上的一致性

## Subagent Proposals
### Planning Coordination
- 先统一 façade 层命名，再落到 sample 和 sampleset 级门面。

### Architecture Review
- `processing` 与 `evaluation` 在三个层级保持镜像，不保留快捷别名。

### Numerical Review
- 在统一 workflow 的同时，处理和评估前置检查必须继承阶段 03 的采样和单位契约。

## Cross Review
### Planning Coordination
- 赞同同构门面，否决新旧 API 并行过长。

### Architecture Review
- 赞同复用 `ComputeFlow`，否决另起新 workflow 基类。

### Numerical Review
- 条件赞同链式 API，前提是数值前置条件不被隐藏。

## Consensus
- 以 `ComputeFlow` 为基础，统一 tool、sample、sampleset 三层的 processing/evaluation 工作流。

## Files to modify
- `src/dyntool/application/processing_service.py`
- `src/dyntool/application/evaluation_service.py`
- `src/dyntool/compute/flow.py`
- `src/dyntool/domain/samples/base.py`
- `src/dyntool/domain/samples/sets.py`
- `README.md`
- `ARCHITECTURE.md`
- `tests/typing_public_api.py`
- `tests/test_flow*.py`

## Files to create
- 可选：`src/dyntool/application/processing_namespace.py`
- 可选：`src/dyntool/application/evaluation_namespace.py`

## Files to verify
- `src/dyntool/application/facade.py`
- `src/dyntool/domain/models/time_series.py`

## 文件级操作步骤
1. 目标文件：`src/dyntool/application/processing_service.py`、`src/dyntool/application/evaluation_service.py`
   - 变更目的：统一 tool 层同构入口
   - 预期影响：顶层处理与评估结构镜像
   - 验证：公开方法命名和参数形状对齐
2. 目标文件：`src/dyntool/domain/samples/base.py`、`src/dyntool/domain/samples/sets.py`
   - 变更目的：挂载 `sample.processing/evaluation` 和 `sampleset.processing/evaluation`
   - 预期影响：对象级入口不再需要快捷别名
   - 验证：IDE 提示只保留命名空间式入口
3. 目标文件：`src/dyntool/compute/flow.py`
   - 变更目的：补齐 `then`、`checkpoint`、`restore`、`branch`、`commit`
   - 预期影响：同一 flow 支持链式处理、评估和回滚
   - 验证：批处理和单样本 workflow 行为一致

## 测试步骤
- 运行 `sample.processing.*` 和 `sample.evaluation.*` typing 测试
- 运行 `sampleset.batch(...)`、`ComputeFlow` 行为测试
- 验证处理与评估可以链式组合且回滚只影响内存态

## 完成定义
- `processing/evaluation` 在 tool、sample、sampleset 三层同构
- 快捷别名全部移除
- flow/batch/checkpoint/restore 语义统一

## 回滚与风险
- 若对象级门面实现侵入过大，可先用薄命名空间包装现有逻辑，再在阶段 06 做内部归位。

