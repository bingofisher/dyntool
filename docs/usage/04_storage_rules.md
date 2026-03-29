# 存储模式与读写规则
稳定性：`Public API`

## 这一页解决什么问题
这一页说明模型、样本和样本集的正式持久化规则，以及 `data_options`、`categories`、`strict`、`workers` 等关键参数的公开语义。

## 最短可运行用法

```python
from dyntool import DefaultSample, DefaultSampleSet, SampleDomain, VibrationTestMetadata
from dyntool.storage import StorageScheme

sample = DefaultSample.from_accel_data(
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
sample_set = DefaultSampleSet.from_samples([sample], sample_domain=SampleDomain.VIBRATION_TEST)
sample_set.save("output/sample_set.h5", storage_scheme=StorageScheme.SET_H5)
loaded = DefaultSampleSet.from_storage("output/sample_set.h5", storage_scheme=StorageScheme.SET_H5)
print(loaded.count())
```

## H5 默认压缩

- 单模型 H5、单样本 H5、样本集 H5 现在默认都启用 `gzip`
- 默认压缩级别为 `4`
- 如果显式覆盖压缩配置，则以显式配置为准
- 未知键、错用范围或非法压缩参数会直接报中文错误，不再静默忽略

## `data_options` 正式契约

`data_options` 只用于样本和样本集存储入口。当前支持下列键：

- `attr_data_format`
  作用：控制 `StorageScheme.ATTR_TABLE` 中属性槽位落盘为 `csv` 或 `npy`
  默认值：`csv`
  适用范围：仅 `ATTR_TABLE`
- `decimal_round`
  作用：保存前对浮点载荷执行统一小数位收敛
  默认值：`None`
  适用范围：样本/样本集全部正式方案
- `float_dtype`
  作用：保存前把浮点数组收敛到 `float32` 或 `float64`
  默认值：`None`
  适用范围：样本/样本集全部正式方案
- `h5_compression`
  作用：控制 H5 样本存储压缩算法
  默认值：`gzip`
  适用范围：`SAMPLE_H5`、`SET_H5`
  允许值：`gzip`、`lzf`、`None`
- `h5_compression_level`
  作用：控制 `gzip` 压缩级别
  默认值：`4`
  适用范围：仅 `gzip`
  允许值：`0` 到 `9`
- `h5_dataset_options`
  作用：高级 H5 dataset 参数映射
  默认值：`{"compression": "gzip", "compression_opts": 4}`
  适用范围：`SAMPLE_H5`、`SET_H5`
  允许键：`compression`、`compression_opts`、`shuffle`、`fletcher32`、`chunks`

## 覆盖优先级

- 先应用正式单项配置，例如 `h5_compression` 和 `h5_compression_level`
- 再应用 `h5_dataset_options`
- 如果二者冲突，以 `h5_dataset_options` 中的显式值为准
- 对 `ATTR_TABLE` 之外的方案传入 `attr_data_format` 会直接报错
- 对非 H5 样本方案传入 `h5_*` 键会直接报错

## 单模型 H5 的说明

- 单模型 `CSV/H5` 读写仍通过 `io_options` 控制
- 单模型 H5 的高级覆盖键仍是 `dataset_options`
- 即使不传 `dataset_options`，单模型 H5 现在也默认启用 `gzip` 和级别 `4`

## 关键代码片段

--8<-- "generated/snippets/storage_scheme_compare.py"

## 标准类型 / 枚举 / 参数契约

- `DataCategory`
- `SampleDomain`
- `SampleLoadMode`
- `SampleSetViewOptions`
- `StorageAccessMode`
- `AttrDataFormat`
- `ContainerFormat`
- `NameResolver`
- `StorageMode`
- `StorageScheme`
- `DefaultSample.save(...)`
- `DefaultSample.load(...)`
- `DefaultSampleSet.from_storage(...)`
- `DefaultSampleSet.save_all(...)`
- `DefaultSampleSet.load_all(...)`
- `dyntool.storage`

当你需要显式声明懒加载或只读视图时，应直接从 `dyntool.storage` 导入
`SampleLoadMode`、`StorageAccessMode` 与 `SampleSetViewOptions`，而不是依赖内部模块路径。

## 常见误区

- 误以为计算派生对象会自动持久化
- 在非 H5 样本方案上继续传 `h5_compression`
- 把内部字段名当成正式 `categories` 入口
- 在不需要显式参数控制时，不必额外导入 `SampleLoadMode` 或 `DataCategory`
- 不要从 `dyntool.domain.*` 或 `dyntool.infrastructure.*` 导入存储契约类型

## 相关示例

- `examples/10_scenarios/04_store_and_reload/main.py`
- `examples/90_recipes/sample_set_filter_parallel_io/main.py`
- `examples/90_recipes/storage_scheme_selection/main.py`

## 相关 API

- `DefaultSample`
- `DefaultSampleSet`
- `dyntool.storage`
- `StorageScheme`
