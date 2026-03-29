# 公开 API

稳定性：`Public API`

本文定义 AdvDynTool 当前正式公开面，并给出推荐的调用方式。

## 正式入口

- 顶层对象 API：`AccelSeries`、`Metadata`、`VibrationTestMetadata`、`DefaultSample`、`DefaultSampleSet`
- 结果对象：`OperationResult`、`BatchOperationReport`
- 模块 API：`dyntool.storage`、`dyntool.plotting`、`dyntool.logging`
- 支持模块：`dyntool.config`、`dyntool.resources`

### structured payload 类别名迁移说明

- 当前样本 payload 恢复接受的正式类别名包括 `DefaultSample`、`DefaultSampleSet`、`VibrationTestSample`、`VibrationTestSampleSet`
- 历史兼容类别名 `Sample`、`SampleSet` 已移除
- 读取旧 payload 时会抛出中文错误，并明确提示迁移到 `DefaultSample` / `DefaultSampleSet`

## 推荐闭环

```python
import dyntool.resources as dt_resources
from dyntool import DefaultSample, DefaultSampleSet, SampleDomain, StorageScheme, VibrationTestMetadata

sample = DefaultSample.from_accel_data(
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
sample_set = DefaultSampleSet.from_samples([sample], sample_domain=SampleDomain.VIBRATION_TEST)
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

### `dyntool.storage` 正式参数类型

以下名称属于 `dyntool.storage` 正式公开契约，允许在业务代码中直接导入并作为参数类型使用：

- 存储方案与容器类型：`StorageScheme`、`StorageMode`、`ContainerFormat`、`AttrDataFormat`
- 样本集读取 / 视图配置：`SampleLoadMode`、`StorageAccessMode`、`SampleSetViewOptions`
- 领域 / 分类与命名解析：`SampleDomain`、`DataCategory`、`NameResolver`

推荐导入方式：

```python
from dyntool.storage import (
    DataCategory,
    NameResolver,
    SampleDomain,
    SampleLoadMode,
    SampleSetViewOptions,
    StorageAccessMode,
    StorageMode,
    StorageScheme,
)
```

## 计算主线与保留快捷方法

- 正式主线是 `sample.compute.*` 与 `sample_set.compute.*`
- 为兼顾高频闭环，保留 `eval_*` / `calc_*` 快捷方法
- 以下历史重复入口不再属于正式公开面：
  - `processing` / `evaluation`
  - `get_sample` / `get_samples`
  - `get_data_dict` / `get_uid_by_alias`
  - `update_metadata`

## 存储默认行为

- `dyntool.storage` 的公开调用方式保持不变
- 单模型 H5、单样本 H5、样本集 H5 默认启用 `gzip`
- 默认压缩级别为 `4`
- 样本/样本集 `data_options` 现在是正式契约，未知键和错用范围会立即报错

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
