# AdvDynTool 文档中心

稳定性：`Public API`

AdvDynTool 文档按“先会使用，再看边界，最后查内部说明”的顺序组织。

当前版本线：`v1.2.0 RC / breaking`

## 当前正式公开面

- 顶层对象 API：常用模型、元数据、样本、样本集、结果对象和必要枚举
- 动作模块：`dyntool.storage`、`dyntool.plotting`、`dyntool.logging`、`dyntool.reporting`
- 支持模块：`dyntool.config`、`dyntool.resources`

## 版本线说明

- 当前文档目录对应 `v1.2.0` 的 breaking/RC 版本线。
- 主目录 `AdvDynTool` 的 `main` 分支继续承担稳定/兼容线角色。
- 会影响迁移路径的删除和正式口径变化，只在 `.worktrees/v1.2.0` ↔ `codex/v1.2.0` 中推进。

## 文档导航

- 用户路径：`docs/usage`
- 教程路径：`docs/workflows`
- 公开 API：`docs/api/public_api.md`
- 开发者说明：`docs/developer`

## 稳定性说明

- `Public API`：正式支持的对象与模块入口
- `Internal API`：可供维护者和扩展开发使用，但不承诺稳定
- `Private / implementation detail`：实现细节，不建议外部使用



