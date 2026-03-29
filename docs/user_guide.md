# 使用总览

稳定性：`Public API`

AdvDynTool 的正式使用路径分为两步：

1. 先选“对象”：顶层对象 API，如 `AccelSeries`、`Metadata`、`DefaultSample`、`DefaultSampleSet`
2. 再选“动作”：正式模块 API，如 `dyntool.storage`、`dyntool.plotting`、`dyntool.logging`

## 正式模块

- `dyntool.storage`：存储与读写
- `dyntool.plotting`：静态绘图
- `dyntool.logging`：日志配置与 logger 获取
- `dyntool.config`：配置加载
- `dyntool.resources`：内置资源读取

## 推荐阅读顺序

- [数据输入与标准类型](usage/01_input_and_types.md)
- [样本与样本集组织](usage/02_samples_and_sets.md)
- [处理、评价与结果对象](usage/03_processing_and_results.md)
- [存储模式与读写规则](usage/04_storage_rules.md)
- [绘图、日志与资源](usage/05_plotting_logging_resources.md)
