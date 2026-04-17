# AdvDynTool 文档中心

稳定性：`Public API`

AdvDynTool 文档按“先会使用，再看边界，最后查内部说明”的顺序组织。

当前版本线：

- 当前稳定发布线：`1.2.x`
- 当前补丁收口分支：`codex/v1.2.0-postmerge`
- 已发布 RC：`v1.2.0-rc.1`

## 当前正式公开面

- 顶层对象 API：常用模型、元数据、样本、样本集、结果对象和必要枚举
- 动作模块：`dyntool.storage`、`dyntool.plotting`、`dyntool.logging`、`dyntool.reporting`
- 支持模块：`dyntool.config`、`dyntool.resources`

## 版本线说明

- `main` 已承接 `v1.2.0` 合并，当前作为 `1.2.x` 稳定线
- `codex/v1.2.0-postmerge` 只处理合并后审查发现的问题
- 影响迁移路径的正式变化，必须同时反映到代码、文档、baseline 和测试

## 文档导航

- 用户路径：`docs/usage`
- 教程路径：`docs/workflows`
- 公开 API：`docs/api/public_api.md`
- 开发者说明：`docs/developer`

## 稳定性说明

- `Public API`：正式支持的对象与模块入口
- `Internal API`：可供维护者和扩展开发使用，但不承诺稳定
- `Private / implementation detail`：实现细节，不建议外部使用
