# 样本集

- 稳定性：`Public API`
- 适用对象：需要批量管理、筛选、计算和导出样本的使用者
- 对应示例：`examples/10_scenarios/02_build_and_manage_samples/main.py`
- 对应测试：`tests/test_examples_systems.py::test_scenario_build_and_manage_samples`

## 用途

`DefaultSampleSet` 是正式批量入口，适合统一保存、加载、筛选、计算和表格导出。

## 查询主线

- `find_many(...)`
- `find_one(...)`
- `count()`
- `exists(...)`
- `distinct_metadata(...)`
- `project_metadata(...)`

`filter(...)` 仍保留，但它是原位过滤；正式非原位查询主线是 `find_many(...)`。

## 表格导出主线

- `metadata_frame()`：返回 metadata 表格
- `data_map(...)`：返回指定槽位的数据映射
- `scalar_frame(...)`：组合 metadata、标量 data_var 和派生特征
- `series_frame(...)`：按公共索引外连接同一 data_var 的多样本序列表
- `peaks_frame(...)`：按峰序号聚合多峰检测结果并补齐 `NaN`

`series_frame(...)` 的列为 `MultiIndex`，层级顺序固定为：

- `uid`
- `alias`
- 显式选择的 metadata 字段
- 各数据模型自行定义的数据键

## 存储查询

样本集挂接到存储后，可通过 `sample_set.storage` 查询存储事实：

- `summary()`
- `metadata_frame()`
- `presence_frame()`

其中 `presence_frame()` 可直接查看 `metadata / accel / vel / disp / force / freqspec / ...` 的存在情况。
