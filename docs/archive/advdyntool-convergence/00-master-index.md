# AdvDynTool 综合收敛总入口

## 阶段目标
- 建立综合方案的唯一执行入口、阶段顺序和文件使用规则。

## 前置依赖
- `task_plan.md`
- `findings.md`
- `progress.md`

## 命中 skills
- `writing-plans`
- `planning-with-files`

## 3-subagent 角色分工
- 规划协调：`writing-plans + planning-with-files`
- 架构评审：`software-architecture`
- 数值评审：`scipy-best-practices`

## Subagent Proposals
### Planning Coordination
- 采用“总控文件 + 阶段文件 + prompt 文件”的三层结构。

### Architecture Review
- 先冻结规则和公开入口，再安排内部拆分。

### Numerical Review
- 在涉及采样和单位的阶段前，不预设实现细节变更。

## Cross Review
### Planning Coordination
- 赞同按阶段收敛，反对单文件大计划长期膨胀。

### Architecture Review
- 赞同文件化执行，要求阶段边界明确。

### Numerical Review
- 赞同分阶段推进，要求采样和单位阶段独立成章。

## Consensus
- 采用 `00` 到 `06` 的顺序执行。
- 执行读取顺序固定为：`task_plan.md` -> 当前阶段文件 -> `findings.md` -> `progress.md`。

## 阶段索引
| 阶段 | 文件 | 依赖 | 完成定义 |
|---|---|---|---|
| 01 | `01-rules-and-api-freeze.md` | 00 | 规则、prompt、canonical API 和无快捷别名原则冻结 |
| 02 | `02-sample-model-construction.md` | 01 | `models/sample/sampleset` 构造入口完成命名收敛 |
| 03 | `03-sampling-and-units.md` | 02 | 采样契约和单位优先级固化 |
| 04 | `04-processing-evaluation-workflow.md` | 03 | `processing/evaluation` 同构和 flow/batch 统一 |
| 05 | `05-storage-logging-plotting.md` | 01,03,04 | 存储、日志、可视化门面和契约收敛 |
| 06 | `06-internal-split-and-regression.md` | 01-05 | 内部拆分完成，文档和测试封板 |

## 文件使用规则
- `task_plan.md`：只记录阶段状态、阻塞项和下一步。
- `findings.md`：只记录事实、决策、被否决方向和风险。
- `progress.md`：只记录会话执行流水和测试结论。
- 阶段文件：只记录该阶段的文件级步骤、测试和完成定义。

## 完成定义
- 6 个阶段全部完成
- 公开 API、文档和测试保持一致
- 质量门禁全部通过

## 回滚与风险
- 若某阶段发现前置假设错误，回退到最近已完成阶段重新修订阶段文件。
- 不允许跳过阶段直接做内部重构。

