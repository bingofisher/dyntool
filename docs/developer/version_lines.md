# 版本线与迁移策略

稳定性：`Internal API`

## 当前布局

- 主目录 `AdvDynTool`：当前正式稳定线工作目录
- `main`：当前正式稳定主线，对应 `v1.2.2` 发布后的持续维护线
- `v1.2.2`：当前正式稳定发布 tag
- 下一轮功能开发：从最新 `main` 新开主题分支，不再依赖历史整合分支

`codex/gui-skeleton` 已完成其作为 `v1.2.2` 整合来源分支的职责，不再作为长期活动版本线保留。

## 角色分工

- `main`：承接正式发布后的稳定维护、治理收口与后续补丁
- `v*` tag：记录正式发布事实
- 主题分支：承接单一功能、修复或实验任务
- worktree：只在高风险重构、跨层改动、性能对照实验等场景下使用

## GitHub 治理

- GitHub 正式 branch ruleset：`Protect main`
- GitHub 正式 tag ruleset：`Protect release tags`
- `main` 当前已经恢复 `CI / quality`
- `quality` 作为 required check 的规则接入属于下一阶段治理动作，启用后应与文档同步

## 硬规则

- 主目录 `AdvDynTool` 只承接 `main` 或明确的当前主题分支
- 不在同一工作树长期混放多个并行主题
- 影响公开 API、存储格式、单位语义、默认行为或迁移路径的变更，必须先得到用户确认
- 新版本线或新主题线应以新分支承接；必要时配套新 worktree

## 当前发布状态

- `v1.2.0`：已完成正式发布
- `v1.2.1`：已完成正式发布
- `v1.2.2` 已作为当前稳定基线正式发布
- `main`：当前对应 `v1.2.2` 发布后的正式稳定主线

## 相关材料

- [更新日志索引](../reference/changelog.md)
- [migration_1_2_0.md](migration_1_2_0.md)
- [release_checklist.md](release_checklist.md)
