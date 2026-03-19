# 公开 API

稳定性：`Public API`

本文定义 AdvDynTool 当前正式公开面，并给出推荐的调用方式。

## 正式入口

- 顶层对象 API：`AccelSeries`、`Metadata`、`VibrationTestMetadata`、`Sample`、`SampleSet`
- 结果对象：`OperationResult`、`BatchOperationReport`
- 模块 API：`dyntool.storage`、`dyntool.plotting`、`dyntool.logging`
- 支持模块：`dyntool.config`、`dyntool.resources`

## 推荐闭环

```python
import dyntool.resources as dt_resources
from dyntool import Sample, SampleDomain, SampleSet, StorageScheme, VibrationTestMetadata

sample = Sample.from_accel_data(
    [0.0, 0.12, -0.03],
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
sample.eval_zvl(overwrite=True, freq_range=(2.0, 60.0))
sample_set = SampleSet.from_samples([sample], sample_domain=SampleDomain.VIBRATION_TEST)
sample_set.save("output/sample_set.h5", storage_scheme=StorageScheme.SET_H5)
freqs, _ = dt_resources.center_freqs((2.0, 80.0))
print(freqs[:3])
```

## 模块 API

- `dyntool.storage`：模型、样本、样本集存储
- `dyntool.plotting`：静态绘图
- `dyntool.logging`：日志配置与 logger 获取
- `dyntool.config`：通用配置加载
- `dyntool.resources`：内置资源读取

## 自动参考

::: dyntool
    options:
      show_root_heading: true
      show_source: false

::: dyntool.storage
    options:
      show_root_heading: true
      show_source: false

::: dyntool.plotting
    options:
      show_root_heading: true
      show_source: false

::: dyntool.logging
    options:
      show_root_heading: true
      show_source: false

::: dyntool.config
    options:
      show_root_heading: true
      show_source: false

::: dyntool.resources
    options:
      show_root_heading: true
      show_source: false
