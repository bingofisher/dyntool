# 存储模式与读写规则

稳定性：`Public API`

## 这一页解决什么问题

这一页说明模型、样本和样本集的正式持久化规则，以及 `categories`、`strict`、`workers` 等关键参数的公开语义。

## 最短可运行用法

```python
from dyntool import Sample, SampleDomain, SampleSet, VibrationTestMetadata
from dyntool.storage import StorageScheme

sample = Sample.from_accel_data(
    [0.0, 0.1, -0.03],
    dt=0.01,
    sample_domain=SampleDomain.VIBRATION_TEST,
    metadata_cls=VibrationTestMetadata,
    case="demo",
    point="P1",
    instr="ACC-01",
    dir="Z",
    record="R1",
    timestamp="2026-03-08 12:00:00",
)
sample_set = SampleSet.from_samples([sample], sample_domain=SampleDomain.VIBRATION_TEST)
sample_set.save("output/sample_set.h5", storage_scheme=StorageScheme.SET_H5)
loaded = SampleSet.from_storage("output/sample_set.h5", storage_scheme=StorageScheme.SET_H5)
print(loaded.count())
```

## 关键代码片段

--8<-- "generated/snippets/storage_scheme_compare.py"

## 标准类型 / 枚举 / 参数契约

- `Sample.save(...)`
- `Sample.load(...)`
- `SampleSet.from_storage(...)`
- `SampleSet.save_all(...)`
- `SampleSet.load_all(...)`
- `StorageScheme`
- `dyntool.storage`

## 常见误区

- 误以为计算派生对象会自动持久化
- 把内部枚举或内部字段名当成正式 `categories` 入口
- 在正式文档中直接导入 `SampleLoadMode` 或 `DataCategory`

## 相关示例

- `examples/10_scenarios/04_store_and_reload/main.py`
- `examples/90_recipes/sample_set_filter_parallel_io/main.py`
- `examples/90_recipes/storage_scheme_selection/main.py`

## 相关 API

- `Sample`
- `SampleSet`
- `dyntool.storage`
- `StorageScheme`
