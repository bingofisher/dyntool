# 自定义扩展

稳定性：`Internal API`

本文只面向需要扩展自定义模型、元数据、样本或样本集的维护者。它不是正式公开 API 教程。

## 参考入口

1. 阅读 `examples/10_scenarios/08_custom_extension/main.py`
2. 阅读 `domain.metadata`、`domain.models`、`domain.samples` 的基础类型
3. 最后确认如何接入 `dyntool.storage`

## 约束

- 扩展对象优先复用正式 `storage` 和 `plotting` 入口
- 不要把基础设施实现细节直接暴露给最终用户
- 任何扩展都不应修改正式示例口径
