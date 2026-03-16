# AdvDynTool 阶段审查与最终校核方案

## 目标
- 为架构重整和多阶段实施提供统一的执行程度校核机制。
- 将“阶段审查”和“最终审查”从口头约定固化为仓库内可持续维护的记录资产。
- 保证每个阶段都有记录、有命令、有结论，而不是只留下零散代码改动。

## 适用范围
- 所有需要规划、分阶段实施、跨多轮推进的任务。
- 所有涉及架构、公开接口、数据模型、I/O、日志、可视化、测试矩阵的中大型任务。
- 所有由 `using-superpowers` 协调并装配多个动态角色的任务。

## 阶段审查流程
### 1. 进入阶段前
- 更新 `task_plan.md` 中对应阶段的实施任务、阶段审查任务、持续执行动作和完成判据。
- 更新 `progress.md` 中对应阶段的状态、阻塞和下一步动作。
- 明确本阶段命中的 skills 与角色装配原因。

### 2. 阶段实施中
- 代码、文档、测试推进时，同步维护该阶段的执行程度。
- 发现分歧时，必须记录主要分歧、被否决方案和最终一致方案。
- 发现阻塞时，必须写回 `progress.md`，不能只在对话里说明。

### 3. 阶段实施完成后
- 先完成阶段审查，再进入下一阶段。
- 阶段审查至少记录：
  - 命中的 skills 与角色
  - 角色装配原因
  - 讨论过程摘要
  - 主要分歧
  - 被否决方案
  - 最终一致方案
  - 已完成项
  - 审查命令
  - 当前结论

## 最终审查流程
- 所有阶段都必须先有明确状态，才能进入最终审查。
- 最终审查至少覆盖：
  - 阶段记录完整性
  - 文档、示例、baseline 一致性
  - 质量门禁命令结果
  - 剩余风险与未完成项
- 最终审查失败时，必须在 `progress.md` 中明确失败项和回退点。

## 持续执行节奏
- 每次进入新阶段前，先运行 `python scripts/check_execution_review.py`。
- 每次阶段审查完成后，再运行一次 `python scripts/check_execution_review.py`，确认结构和记录未漂移。
- 每次准备宣称“已完成”“已通过”“已收尾”前，运行 `python scripts/check_execution_review.py --strict`。
- 若本轮未封板，`--strict` 失败是预期行为，但失败原因必须可解释。

## 记录文件分工
- `task_plan.md`
  - 维护总目标、阶段任务、审查任务、持续执行动作和完成判据。
- `progress.md`
  - 维护阶段状态总览、阶段审查记录和最终审查记录。
- `findings.md`
  - 维护阶段推进中识别出的关键问题、结构风险和剩余缺口。

## 命令清单
- 阶段结构校核：
  - `python scripts/check_execution_review.py`
- 最终严格校核：
  - `python scripts/check_execution_review.py --strict`
- 质量门禁：
  - `ruff check src/dyntool tests`
  - `ruff format --check src/dyntool tests`
  - `python scripts/check_layer_imports.py`
  - `python scripts/check_public_api_baseline.py`
  - `python scripts/check_text_quality.py`
  - `pyright src/dyntool`
  - `pyright tests/typing_public_api.py`
  - `pytest -q tests`

## 环境说明
- 当前仓库在 Windows 环境下优先使用仓库虚拟环境解释器执行命令。
- 如果 `python` 命中 WindowsApps 占位符并导致空失败，应改用：
  - `.\.venv\Scripts\python.exe`
  - `.\.venv\Scripts\ruff.exe`
  - `.\.venv\Scripts\pyright.exe`
  - `.\.venv\Scripts\pytest.exe`

## 角色职责
- `using-superpowers`
  - 负责阶段路由、角色装配、分歧仲裁和最终收敛。
- `writing-plans`
  - 负责将多阶段任务拆成可执行计划和阶段门禁。
- `planning-with-files`
  - 负责把阶段状态、审查记录和恢复点落到仓库文件。
- 其他动态角色
  - 负责各自专项判断，但都必须回流到统一的阶段审查记录。

## 通过标准
- `task_plan.md`、`progress.md` 和本文档的结构一致。
- 所有阶段在 `progress.md` 中都有明确状态和审查记录。
- 最终封板时，`python scripts/check_execution_review.py --strict` 通过。
