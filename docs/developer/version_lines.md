# 版本线与迁移策略

稳定性：`Internal API`

## 当前布局

- 主目录 `AdvDynTool`：当前正式稳定线，对应 `main`
- `main`：当前正式稳定主线，对应 `v1.2.2`
- `codex/gui-skeleton`：本轮 `v1.2.2` 收口与整合来源分支，合并完成后不再长期保留
- 下一条功能开发线：后续如需新功能，再从最新稳定主线新开对应功能分支

## 角色分工

- `main` 承接正式发布后的稳定维护与补丁版本
- `codex/gui-skeleton` 只承担 `v1.2.2` 的整合与收口，不承载后续长期开发
- `1.1.x` 不常驻维护；如确需修旧版，从 `v1.1.2` tag 临时拉 hotfix 分支

## GitHub 治理

- GitHub 正式 branch ruleset 固定为 `Protect main`，目标为 `refs/heads/main`
- GitHub 正式 tag ruleset 固定为 `Protect release tags`，目标为 `refs/tags/v*`
- `main` 的 required check 在 CI 稳定后固定为 `quality`
- 正式发布事实一律以 `v*` tag 为准，不再用长期 `release/*` branch 充当发布事实源

## 硬规则

- 主目录 `AdvDynTool` 只允许挂 `main` 或当前合并后补丁分支
- 不在已有 worktree 里切换到无关 branch
- 新版本线或新特性线必须新建对应 worktree，并保持目录名与分支名一一对应
- 影响迁移路径的公开口径变化，必须先得到用户确认，再同步代码、文档、baseline 和测试

## 当前发布状态

- `v1.2.0` 已作为上一稳定版本完成发布
- `v1.2.1` 已作为上一稳定版本完成发布
- `v1.2.2` 已作为当前稳定基线正式发布

## 相关材料

- 变更记录见 [更新日志索引](../reference/changelog.md)
- `1.1.2 -> 1.2.0` 迁移说明见 [migration_1_2_0.md](migration_1_2_0.md)
- 发布检查项见 [release_checklist.md](release_checklist.md)
