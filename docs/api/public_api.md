# 公开 API

AdvDynTool 的正式公开面只保留两条主线：核心类 API 和独立模块 API。

## 正式入口

- 类 API：`AccelSeries`、`Metadata`、`Sample`、`SampleSet`
- 模块 API：`dyntool.storage`、`dyntool.plotting`、`dyntool.logging`
- 轻量门面：`DynTool.resource`、`DynTool.options`

## 典型路径

```python
from dyntool import AccelSeries, Sample, SampleDomain, SampleSet
import dyntool.storage as dt_storage

accel = AccelSeries.from_data([0.0, 0.12, -0.03], dt=0.01)
sample = Sample.from_models(
    sample_domain=SampleDomain.VIBRATION_TEST,
    accel=accel,
    case="demo",
    point="P1",
    instr="ACC-01",
    dir="Z",
    record="R1",
    timestamp="2026-03-08 12:00:00",
)
sample_set = SampleSet.from_samples([sample], sample_domain=SampleDomain.VIBRATION_TEST)
dt_storage.save_sample_set(sample_set, "output/samples.h5")
```

## 自动参考

::: dyntool
    options:
      show_root_heading: true
      show_source: false

::: dyntool.storage
    options:
      show_root_heading: true
      show_source: false
      members:
        - StorageMode
        - StorageScheme
        - save_model
        - load_model
        - inspect_model_units
        - save_metadata
        - load_metadata
        - save_sample
        - load_sample
        - connect_sample_set
        - save_sample_set
        - load_sample_set

::: dyntool.plotting
    options:
      show_root_heading: true
      show_source: false

::: dyntool.logging
    options:
      show_root_heading: true
      show_source: false
