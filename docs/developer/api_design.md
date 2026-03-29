# API 设计

稳定性：`Internal API`

AdvDynTool 当前正式公开面遵循“两层公开面 + 内部实现下沉”的设计：

- 顶层对象层：负责回答“你在操作什么对象”
- 模块动作层：负责回答“你要执行什么动作”

正式对象类名已经收敛为 `DefaultSample / DefaultSampleSet`。
文档中出现“样本 / 样本集”时，如无特别说明，表示概念层对象，不表示可稳定导入的类名。

当前正式模块为：

- 动作模块层：`storage / plotting / logging`
- 支持模块层：`config / resources`

其中 `storage` 既承担动作入口，也承担正式契约类型入口；业务侧如需显式声明存储方案、
加载模式或视图选项，应从 `dyntool.storage` 导入，而不是从内部实现层导入。

计算能力的正式主线是 `compute`：

- 推荐使用 `sample.compute.*` 与 `sample_set.compute.*`
- 保留 `eval_* / calc_*` 作为高频快捷方法
- 不再把 `processing`、`evaluation`、`get_sample`、`get_samples`、
  `get_uid_by_alias`、`get_data_dict`、`update_metadata` 视为正式公开面

以下内容已明确移出正式公开面：

- 旧门面对象
- 旧绘图后端枚举
- 旧后端选择参数
- schema、registry、structured payload 和其他内部 helper 的顶层导出
