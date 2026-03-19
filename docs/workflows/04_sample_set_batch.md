# 样本集批处理

稳定性：`Public API`

- 适用对象：需要对一批样本统一保存、加载和评价的使用者
- 对应示例：`examples/90_recipes/sample_set_filter_parallel_io/main.py`
- 对应测试：`tests/test_examples_workflows.py::test_recipe_sample_set_filter_parallel_io`

重点参数包括 `strict`、`workers`、`chunk_size` 和 `filter`。
