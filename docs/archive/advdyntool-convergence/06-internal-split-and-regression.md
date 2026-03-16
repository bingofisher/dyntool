# 阶段 06：内部拆分、文档封板与全量回归

## 阶段目标
- 在前面规则和公开契约冻结后，完成内部模块拆分、纯计算 kernel 提取、文档封板和全量回归。

## 前置依赖
- `01-rules-and-api-freeze.md`
- `02-sample-model-construction.md`
- `03-sampling-and-units.md`
- `04-processing-evaluation-workflow.md`
- `05-storage-logging-plotting.md`

## 命中 skills
- `writing-plans`
- `planning-with-files`
- `software-architecture`
- `scipy-best-practices`

## 3-subagent 角色分工
- 规划协调：拆分模块、测试封板和文档更新顺序
- 架构评审：主审服务拆分、模块边界和依赖方向
- 数值评审：主审 kernel 提取后的数值等价与回归基线

## Subagent Proposals
### Planning Coordination
- 先补回归基线，再拆厚文件。

### Architecture Review
- `sample_service.py`、`model_service.py`、`compute/solvers.py` 只在前置接口冻结后拆分。

### Numerical Review
- `compute.metrics` 先抽纯计算 kernel，再由 application 包装为现有评估结果模型。

## Cross Review
### Planning Coordination
- 赞同先回归后拆分，否决边拆边改行为。

### Architecture Review
- 赞同职责拆分，否决跨层绕行。

### Numerical Review
- 赞同 kernel 提取，否决顺手重写算法公式。

## Consensus
- 以行为冻结和回归基线为前提做内部拆分。

## Files to modify
- `src/dyntool/application/sample_service.py`
- `src/dyntool/application/model_service.py`
- `src/dyntool/compute/solvers.py`
- `src/dyntool/compute/metrics.py`
- `src/dyntool/compute/signals.py`
- `README.md`
- `ARCHITECTURE.md`
- `docs/examples_overview.md`
- `tests/*`

## Files to create
- 可选：`src/dyntool/compute/solvers/`
- 可选：`src/dyntool/application/sample_namespaces/`
- 可选：`src/dyntool/application/model_namespaces/`

## Files to verify
- `scripts/check_layer_imports.py`
- `scripts/check_text_quality.py`

## 文件级操作步骤
1. 目标文件：测试目录与基线数据
   - 变更目的：冻结当前行为和数值结果
   - 预期影响：后续拆分时能快速识别行为回归
   - 验证：关键闭环和真实输入测试通过
2. 目标文件：`src/dyntool/application/sample_service.py`、`src/dyntool/application/model_service.py`
   - 变更目的：按职责拆分 namespace/builder/loader
   - 预期影响：公开门面更薄、实现更聚焦
   - 验证：服务文件规模明显下降且职责更清晰
3. 目标文件：`src/dyntool/compute/solvers.py`、`src/dyntool/compute/metrics.py`
   - 变更目的：抽纯计算 kernel，清理重复逻辑
   - 预期影响：compute 层更纯，application 层负责编排
   - 验证：重构前后关键数值等价
4. 目标文件：`README.md`、`ARCHITECTURE.md`、`docs/examples_overview.md`
   - 变更目的：完成对外文档封板
   - 预期影响：文档与代码状态一致
   - 验证：示例与 smoke 测试覆盖一致

## 测试步骤
- `ruff check src/dyntool tests`
- `ruff format --check src/dyntool tests`
- `python scripts/check_layer_imports.py`
- `python scripts/check_text_quality.py`
- `pyright src/dyntool`
- 关键闭环：`from_accel -> eval -> save/load -> plot`
- 真实输入：`tests/input_data`
- 数值等价：ZVL、OTOVL、FDMVL、FPVDV、响应谱、频谱

## 完成定义
- 厚文件拆分完成
- 分层依赖仍正确
- 文档、示例、类型检查和回归测试全部通过

## 回滚与风险
- 若某次拆分导致数值回归，应先回退到最近通过基线的拆分点，再重新分解文件边界。

