# 自定义扩展

`Internal API`

本页面向需要扩展元数据、数据模型、样本或样本集的开发者。

## 建议路径

1. 先阅读 `examples/11_custom_extension/custom_domain_extension.py`
2. 再阅读 `domain.metadata`、`domain.models`、`domain.samples` 的基类和注册入口
3. 最后确认扩展对象如何进入 `dyntool.storage`

## 约束

- 扩展对象优先复用正式 `storage` 和 `plotting` 入口
- 不要把基础设施细节直接暴露给使用者
