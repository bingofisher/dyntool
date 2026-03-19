# 存储并回读

稳定性：`Public API`

- 适用对象：需要快速验证标准存储闭环的使用者
- 对应示例：`examples/10_scenarios/04_store_and_reload/main.py`
- 对应测试：`tests/test_examples_systems.py::test_scenario_store_and_reload`

重点是完成 `from_accel -> eval -> save/load -> plot` 的最小闭环。
