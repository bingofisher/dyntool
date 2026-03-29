# 自定义扩展
稳定性：`Internal API`

`custom_extension` 用于演示如何在仓库外部实现自定义 metadata、样本与样本集类型，并与当前
`AdvDynTool` 主链对接。内置正式对象类名仍是 `DefaultSample / DefaultSampleSet`；本页关注的是
扩展实现方式，而不是新增一套正式公开类名。它面向维护者和扩展开发者，不属于正式 `Public API`。

## 对应示例

- `examples/10_scenarios/08_custom_extension/main.py`
- `examples/10_scenarios/08_custom_extension/README.md`

## 当前推荐路径

- 主入口优先使用 `sample.compute.*` 与 `sample_set.compute.*`
- 兼容便捷方法只保留 `calc_*` 与 `eval_*`
- 不再建议围绕 `preprocess()`、`processing/evaluation` 命名空间或 command 风格入口扩展

## 示例覆盖的内容

- 外部定义 `ExternalVibrationMetadata`
- 外部定义 `ExternalVibrationSample`
- 外部定义 `ExternalVibrationSampleSet`
- 通过 consumer 侧 registry bridge 接入 payload 恢复
- 对比 `compute` 路径与 `eval_*` 路径结果一致性
- 对比 external 领域与内置 `vibtest` 领域的结果一致性
- 验证 payload / storage / plotting 闭环

## 使用边界

- 可以引用内部模块与内部 registry
- 不进入正式公开扩展承诺
- 不提供稳定的 `SampleDomain` 公共分派扩展协议
- 若后续要升级为 `Public API`，需要单独设计 registry / factory / 文档契约
