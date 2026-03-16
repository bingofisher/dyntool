# 标准资源

- 稳定性：`Public API`
- 适用对象：需要读取内置标准阈值、频带和资源索引的使用者
- 对应示例：`examples/10_scenarios/07_resource_driven_eval/main.py`
- 对应测试：`tests/test_examples_systems.py::test_scenario_resource_driven_eval`

## 用途

当流程依赖标准输入时，应通过 `DynTool.resource` 获取，而不是在脚本里复制常量。
