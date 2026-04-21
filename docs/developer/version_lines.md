# 版本线与迁移策略

稳定性：`Internal API`

## 当前布局

- 主目录 `AdvDynTool`：当前正式稳定线，对应 `main`
- `main`：当前正式稳定主线，对应 `v1.2.1`
- `codex/v1.2.1-patch`：`v1.2.1` 发布收口分支，已用于完成 plotting patch 与文档治理收口
- 下一条功能开发线：后续如需新功能，再从最新稳定主线新开 `codex/v1.3.0`

## 角色分工

- `main` 承接正式发布后的稳定维护与补丁版本
- `codex/v1.2.1-patch` 只承接 `v1.2.1` 的发布收口，不承载新功能
- `1.1.x` 不常驻维护；如确需修旧版，从 `v1.1.2` tag 临时拉 hotfix 分支

## 硬规则

- 主目录 `AdvDynTool` 只允许挂 `main` 或当前合并后补丁分支
- 不在已有 worktree 里切换到无关 branch
- 新版本线或新特性线必须新建对应 worktree，并保持目录名与分支名一一对应
- 影响迁移路径的公开口径变化，必须先得到用户确认，再同步代码、文档、baseline 和测试

## 当前发布状态

- `v1.2.0` 已作为上一稳定版本完成发布
- `v1.2.1` 已作为当前稳定基线正式发布
- 后续如仍存在问题，下一补丁目标进入 `1.2.2`

## 相关材料

- 变更记录见 [更新日志索引](../reference/changelog.md)
- `1.1.2 -> 1.2.0` 迁移说明见 [migration_1_2_0.md](migration_1_2_0.md)
- 发布检查项见 [release_checklist.md](release_checklist.md)
