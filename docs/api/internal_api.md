# 内部代码说明

稳定性：`Internal API`

本页面向维护者和高级使用者，用于解释当前实现中的关键内部链路，而不是承诺长期稳定的导入路径。

## 关键链路

- 领域对象方法通过 `domain.runtime` 解析运行时绑定
- 默认对象运行时由 `application.runtime_binding` 统一组装
- 正式存储请求最终落到 `StorageRuntime` 与 `SampleSetStorage`
- `dyntool.storage.runtime` 现在仅保留薄门面，内部编排拆到
  `dyntool.storage._runtime_common`、`_model_runtime`、`_sample_runtime`、
  `_sample_set_runtime`
- 样本存储 `data_options` 校验与 H5 默认参数集中在
  `dyntool.infrastructure.storage_options`

## 阅读顺序

1. `dyntool.application.runtime_binding`
2. `dyntool.domain.runtime`
3. `dyntool.storage.runtime`
4. `dyntool.infrastructure.sample_set_storage`

## 自动参考

::: dyntool.application.runtime_binding
    options:
      show_root_heading: true
      show_source: false

::: dyntool.domain.runtime
    options:
      show_root_heading: true
      show_source: false

::: dyntool.infrastructure.sample_set_storage
    options:
      show_root_heading: true
      show_source: false
