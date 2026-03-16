# 数据模型

- 稳定性：`Public API`
- 适用对象：需要构造时程、频谱和反应谱对象的使用者
- 对应示例：`examples/90_recipes/structured_payload_roundtrip/main.py`
- 对应测试：`tests/test_examples_workflows.py::test_recipe_structured_payload_roundtrip`

## 用途

数据模型是整个项目的基础。`AccelSeries`、`FreqSpec`、`RespSpec` 等对象负责承载数值数据、字段语义和单位信息。
