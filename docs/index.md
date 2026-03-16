# AdvDynTool 文档中心

AdvDynTool 是面向动力学计算、振动处理与结果评价的 Python 工具库。本站不再按源码目录平铺，而是按“先会用，再查细节”的顺序组织。

稳定性：`Public API`

## 推荐阅读路径

### 路径一：第一次接入

1. [使用总览](user_guide.md)
2. [数据输入与标准类型](usage/01_input_and_types.md)
3. [样本与样本集组织](usage/02_samples_and_sets.md)
4. [最小闭环教程](workflows/01_minimal_roundtrip.md)

### 路径二：已经会建模，想跑完整闭环

1. [处理、评价与结果对象](usage/03_processing_and_results.md)
2. [存储模式与读写规则](usage/04_storage_rules.md)
3. [样本集批处理教程](workflows/04_sample_set_batch.md)

### 路径三：补图、补日志、补资源

1. [绘图、日志与资源](usage/05_plotting_logging_resources.md)
2. [资源驱动评价教程](workflows/06_resource_driven_eval.md)
3. [公开 API](api/public_api.md)

## 常用入口

- `AccelSeries.from_data(...)`
- `AccelSeries.from_csv(...)`
- `Sample.from_accel_data(...)`
- `SampleSet.from_samples(...)`
- `dyntool.storage.save_model(...)`
- `dyntool.storage.save_sample_set(...)`
- `accel.to_plot_payload(...)`
- `dyntool.plotting.render_payload(...)`
- `DynTool().resource`

## 常见关键词

`标准类型`、`样本域`、`数据类别`、`存储模式`、`存储方案`、`CSV 读取参数`、`样本集 H5`
