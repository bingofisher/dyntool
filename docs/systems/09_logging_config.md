# 日志配置

- 稳定性：`Public API`
- 适用对象：需要在脚本、批处理和存储流程中统一控制日志输出的使用者
- 对应示例：`examples/90_recipes/logging_providers_and_modes/main.py`
- 对应测试：`tests/test_examples_workflows.py::test_recipe_logging_providers_and_modes`

## 口径

`dyntool.logging` 是唯一正式日志入口。默认 provider 为 `loguru`；若未安装 `loguru`，默认配置会自动回退到 `stdlib`，并记录一次 `WARNING` 日志。
