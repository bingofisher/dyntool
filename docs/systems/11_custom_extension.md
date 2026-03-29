# 自定义扩展
- 稳定性：`Internal API`
- 适用对象：需要扩展元数据、样本和样本集的维护者
- 对应示例：`examples/10_scenarios/08_custom_extension/main.py`
- 对应测试：`tests/test_examples_workflows.py::test_internal_custom_extension_compare_with_vibtest`

## 用途

这条路径用于说明如何在仓库外部实现与 `vibtest` 对标的自定义领域对象，并继续复用：

- `compute` 主链
- `storage` 持久化
- `StructuredPayload` roundtrip
- `plotting` 绘图链路

## 当前口径

- 推荐主路径：`compute`
- 兼容实现层：`calc_*`、`eval_*`
- bridge 方式：consumer 侧 registry patch
- 非目标：公共 `SampleDomain` 扩展协议
