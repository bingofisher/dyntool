# 数据模型

稳定性：`Public API`

- 适用对象：需要构造时程、频谱和反应谱对象的使用者
- 对应示例：`examples/10_scenarios/01_import_and_normalize/main.py`
- 对应测试：`tests/test_examples_systems.py::test_scenario_import_and_normalize`

## 用途

数据模型是整个项目的基础。`AccelSeries`、`FreqSpec`、`RespSpec` 等对象负责承载数值数据、字段语义和单位信息。
