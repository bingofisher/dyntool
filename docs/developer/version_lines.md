# 版本线与迁移策略

稳定性：`Internal API`

## 当前布局

- 主目录 `AdvDynTool`：当前正式稳定线，对应 `main`
- `main`：`v1.2.0` 已合入、待最终 tag 的主线
- `codex/v1.2.0-finalize-tag`：仅用于 `v1.2.0` 正式 tag 前的最后补丁修复
- 下一条功能开发线：待 `v1.2.0` 发布闭环完成后，再从最新 `main` 新开 `codex/v1.3.0`

## 角色分工

- `main` 承接正式发布后的稳定维护与补丁版本
- `codex/v1.2.0-finalize-tag` 只处理正式 tag 前发现的问题，不再承载新功能
- `1.1.x` 不常驻维护分支；如确需修旧版，从 `v1.1.2` tag 临时拉 hotfix 分支

## 硬规则

- 主目录 `AdvDynTool` 只允许挂 `main` 或当前合并后补丁分支
- 不在已有 worktree 里切换到无关 branch
- 新版本线或新特性线必须新建对应 worktree，并保持目录名与分支名一一对应
- 影响迁移路径的公开口径变化，必须先得到用户确认，再同步代码、文档、baseline 和测试

## 当前发布状态

- `v1.2.0-rc.1` 已在发布集成线打出
- `main` 已完成 `v1.2.0` 合并
- 当前正在执行正式 tag 前的最终审查与补丁收口
- `v1.2.0` 的最终发布事实以通过审查后的 `main` 提交和对应 git tag 为准

## 相关材料

- 变更记录见 [更新日志索引](../reference/changelog.md)
- `1.1.2 -> 1.2.0` 迁移说明见 [migration_1_2_0.md](migration_1_2_0.md)
- 发布检查项见 [release_checklist.md](release_checklist.md)
