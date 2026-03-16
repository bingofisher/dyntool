# 存储与读写

- 稳定性：`Public API`
- 适用对象：需要可靠保存和回读模型、样本与样本集的使用者
- 对应示例：`examples/90_recipes/storage_scheme_selection/main.py`
- 对应测试：`tests/test_examples_workflows.py::test_recipe_storage_scheme_selection`

## 用途

正式读写统一通过 `dyntool.storage`，不要绕过正式入口直接调用基础设施层实现。
