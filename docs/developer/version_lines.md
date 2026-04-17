# 版本线与迁移策略

稳定性：`Internal API`

## 当前布局

- 主目录 `AdvDynTool`：稳定/兼容线
- `.worktrees/v1.2.0`：正式 `1.2.0` 版本线
- 分支：`codex/v1.2.0`
- 目标标签：`v1.2.0`
- 当前稳定发布版本：`v1.1.2`
- 当前发布候选版本线：`v1.2.0`

## 角色分工

- 主目录继续服务现有外部项目与兼容调用
- `v1.2.0` 版本线用于承接 breaking 改动、compat 清理和内部结构收敛
- 会影响迁移路径的删除和正式口径变化，只在 `v1.2.0` 版本线中推进

## 硬规则

- 主目录 `AdvDynTool` 只对应 `main`
- `.worktrees/v1.2.0` 只对应 `codex/v1.2.0`
- 不在已有 worktree 内切换到其他 branch
- 后续如需新增版本线或专题线，必须新建对应 worktree，并保持目录名与分支名一一对应

## 当前默认约束

- 新版本线从干净 `main@d370bef` 建立
- 主目录中的未提交改动不会自动带入 `v1.2.0`
- 后续迁移只允许挑选已确认有价值的实现或设计重新落地
- 当前固定收敛顺序为：`plotting -> storage -> domain`

## 发布与迁移材料

- 变更记录见 [更新日志索引](../reference/changelog.md)
- `1.1.2 -> 1.2.0` 迁移说明见 [migration_1_2_0.md](migration_1_2_0.md)
- 发布前检查项见 [release_checklist.md](release_checklist.md)
