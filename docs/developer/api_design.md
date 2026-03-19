# API 设计

稳定性：`Internal API`

AdvDynTool 当前正式公开面遵循“两层公开面 + 内部实现下沉”的设计：

- 顶层对象层：负责回答“你在操作什么对象”
- 模块动作层：负责回答“你要执行什么动作”

当前正式模块为：

- 动作模块层：`storage / plotting / logging`
- 支持模块层：`config / resources`

以下内容已明确移出正式公开面：

- 旧门面对象
- 旧绘图后端枚举
- 旧后端选择参数
- schema、registry、structured payload 和其他内部 helper 的顶层导出
