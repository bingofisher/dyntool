# 存储模式与读写规则

稳定性：`Public API`

## 这页解决什么问题？

这页说明标准 `storage` 链路的用法、模型/样本/样本集的标准持久化边界，以及批量读写时的筛选与并行参数。

## 最短可运行用法

```python
import dyntool.storage as dt_storage
from dyntool import AccelSeries, StorageScheme

accel = AccelSeries.from_data([0.0, 0.1, -0.03], dt=0.01)
dt_storage.save_model(accel, "accel.csv", scheme=StorageScheme.CSV)
```

## 关键代码片段

--8<-- "generated/snippets/storage_scheme_compare.py"

## 标准类型 / 枚举 / 参数契约

- `save_model(...)` / `load_model(...)`
- `save_sample_set(...)` / `load_sample_set(...)`
- `filter`
- `workers`
- `chunk_size`

## 常见误区

- 继续调用历史样本集入口 `to_h5()`、`from_h5()`、`to_csv()` 或旧目录导入快捷方法
- 误以为 `load(filter=...)` 会清空当前 `SampleSet`

## 相关示例

- 场景：[main.py](/D:/BaiduSyncdisk/13_CodeRepository/Projects/AdvDynTool/examples/10_scenarios/04_store_and_reload/main.py)
- 场景：[main.py](/D:/BaiduSyncdisk/13_CodeRepository/Projects/AdvDynTool/examples/10_scenarios/01_import_and_normalize/main.py)
- Recipe：[main.py](/D:/BaiduSyncdisk/13_CodeRepository/Projects/AdvDynTool/examples/90_recipes/sample_set_filter_parallel_io/main.py)
- Recipe：[main.py](/D:/BaiduSyncdisk/13_CodeRepository/Projects/AdvDynTool/examples/90_recipes/storage_scheme_selection/main.py)

## 相关 API

- `dyntool.storage`
- `StorageScheme`
- `SampleSet.from_storage`
