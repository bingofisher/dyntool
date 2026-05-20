# 开发工作流与 Git / 项目管理约定

稳定性：`Internal API`

## 目标

本页定义 AdvDynTool 当前阶段的轻量开发工作流。目标不是追求“永远零改动”，而是保证高频改动仍然具备：

- 可判断
- 可回退
- 可集成

当前仓库已经恢复到 GitHub PR + ruleset 治理模式，因此正式主线治理以 GitHub 规则为准，而不是本地口头约束。

## 当前阶段原则

- `main` 只承接最近可用的稳定集成结果
- 新的高风险实验不直接堆到 `main`
- 一个主题固定一条 branch
- 跨层重构、大实验和高风险改动默认使用 worktree 隔离
- GitHub 正式主线治理以 `Protect main`、`Protect release tags` 与 `CI / quality` 为准

## 三层 Git 模型

### `main`

- 定位：正式稳定主线
- 用途：
  - 承接已验证的稳定集成改动
  - 作为后续主题开发的共同基线
- GitHub 约束：
  - 通过 Pull Request 合并
  - 至少 `1` 个 review
  - require conversation resolution
  - require linear history
  - 当前由仓库拥有者持有 bypass，以支持单维护者仓库收口

### `branch`

- 定位：单主题开发线
- 规则：
  - 一个主题一条 branch
  - 一个完整想法形成一批可识别 commit
- 建议命名：
  - `feature/<topic>`
  - `fix/<topic>`
  - `exp/<topic>`

### `worktree`

- 定位：高风险主题的物理隔离工作区
- 规则：
  - worktree 依附 branch 使用，不替代 branch
  - 只在需要显著隔离上下文时启用，不要求每次都使用
- 典型场景：
  - 公开 API 变化
  - 存储格式变化
  - 默认行为变化
  - benchmark / 性能对照实验
  - 跨层重构

## 项目管理文件职责

以下文件属于本地项目管理面：

### `TODO.md`

- 只放候选事项
- 不放执行事实
- 不放长文设计

### `task_plan.md`

- 只放当前已经承诺推进的主题
- 同一时间尽量只保留少量活跃主题

### `progress.md`

- 只记录执行事实：
  - 当前在哪条分支或 worktree 上工作
  - 本轮完成了什么
  - 下一步是什么
  - 当前阻塞是什么

## 提交与验证节奏

- 一个主题一条 branch
- 一个完整想法一组 commit
- 一个阶段结束至少跑一次对应门禁
- 以下改动必须形成可识别的独立提交段：
  - 存储格式变化
  - 公开 API 变化
  - 正式文档口径变化
  - benchmark 与性能结论变化

## 与仓库规则的关系

- 本页不替代 `AGENTS.md`
- `AGENTS.md` 负责仓库总规则、门禁与必须先问用户的事项
- 本页只负责当前仓库 Git 使用边界与开发工作流落地
