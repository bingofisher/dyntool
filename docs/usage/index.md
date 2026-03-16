# 入门与使用总览

稳定性：`Public API`

本分组是 AdvDynTool 的主学习路径。阅读顺序建议如下：

1. [数据输入与标准类型](01_input_and_types.md)
2. [样本与样本集组织](02_samples_and_sets.md)
3. [处理、评价与结果对象](03_processing_and_results.md)
4. [存储模式与读写规则](04_storage_rules.md)
5. [绘图、日志与资源](05_plotting_logging_resources.md)

## 适合谁

- 初次接触项目、需要先把正式公开对象和最小调用方式跑通的使用者
- 已经会用对象 API，但需要确认参数语义、模式差异或返回值边界的使用者
- 正在根据示例脚本接入自己数据流、希望知道哪些写法是正式推荐路径的使用者

## 常用入口

- `AccelSeries.from_data(...)` / `AccelSeries.from_csv(...)`
- `Sample.from_accel_data(...)`
- `SampleSet.from_samples(...)`
- `dyntool.storage.save_model(...)` / `load_model(...)` / `save_sample_set(...)`
- `accel.to_plot_payload(...)`
- `dyntool.plotting.render_payload(...)`
- `DynTool().resource`

## 常见关键词

`标准类型`、`样本域`、`数据类别`、`存储模式`、`存储方案`、`CSV 读取参数`、`样本集 H5`
