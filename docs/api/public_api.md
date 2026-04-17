# 公开 API

稳定性：`Public API`

本文只描述 AdvDynTool 当前正式公开面。v1.2.0 起，`configure_zh`、`ZhPlotConfig`、`AxisFrame`、`GridFrame`、`AxisHelper`、`LegendHelper`、`PlotterBase`、`PlotterKind`、`axes.py` facade 以及 `add()+plot()` 旧路径已删除，不再作为正式依赖。

## 正式入口

- 顶层对象 API：`AccelSeries`、`Metadata`、`VibrationTestMetadata`、`DefaultSample`、`DefaultSampleSet`
- 结果对象：`OperationResult`、`BatchOperationReport`
- 模块 API：`dyntool.storage`、`dyntool.plotting`、`dyntool.logging`、`dyntool.reporting`
- 支持模块：`dyntool.config`、`dyntool.resources`

### 样本类命名

- `DefaultSample / DefaultSampleSet` 是当前唯一正式顶层样本对象
- `Sample / SampleSet` 顶层导入已移除
- 内部实现仍可能保留旧命名，但不再属于正式公开面

### structured payload 命名迁移

- 当前接受的正式类名包括 `DefaultSample`、`DefaultSampleSet`、`VibrationTestSample`、`VibrationTestSampleSet`
- 旧 payload 兼容类名 `Sample`、`SampleSet` 已移除
- 读取旧 payload 时会给出中文错误，并提示迁移到正式类名

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

### `dyntool.plotting`

稳定性：`Public API`

`dyntool.plotting` 的正式公开对象只保留新主链：

- `PlotDataset`
- `PlotTheme`
- `PlotResult`
- `PlotCategory`
- `PlotStatMetric`
- `PlotKind`
- `FramePlotter`
- `BoxPlotter`
- `OneThirdOctavePlotter`
- `StoryValuePlotter`

v1.2.0 起正式主链固定为：

1. `PlotDataset.from_* (...)`
2. `PlotTheme.from_file(path)` 或 `PlotTheme.default()`
3. `ConcretePlotter(...).plot_dataset(dataset, ax=ax, ...)`
4. `PlotResult.ax`

示例：

```python
from pathlib import Path
import dyntool.plotting as dt_plotting

theme_path = Path(dt_plotting.__file__).resolve().parent / "assets" / "plot_theme_report.toml"
theme = dt_plotting.PlotTheme.from_file(theme_path)
dataset = dt_plotting.PlotDataset.from_axis_value(
    axis=[0.0, 0.1, 0.2],
    value=[0.0, 0.1, -0.05],
    name="demo",
    category=dt_plotting.PlotCategory.SAMPLE,
)
result = dt_plotting.FramePlotter(theme=theme).plot_dataset(dataset)
print(result.ax is not None)
```

### `dyntool.storage`

稳定性：`Public API`

`dyntool.storage` 负责模型、样本、样本集持久化，公开的连接、检测与读取接口可直接在业务代码中使用。

正式契约名包括：

- `DataCategory`
- `SampleLoadMode`
- `SampleSetViewOptions`
- `StorageAccessMode`
- `AttrDataFormat`
- `ContainerFormat`
- `NameResolver`
- `StorageConnectOptions`
- `StorageMode`
- `StorageRepositoryReport`
- `StorageScheme`

### `dyntool.logging`

稳定性：`Public API`

`dyntool.logging` 负责日志配置和 logger 获取。

### `dyntool.reporting`

稳定性：`Public API`

`dyntool.reporting` 负责样本集统计导出和报告包导出。样本集对象的对象级稳定入口由 `SampleSetBase` 这一实现基类承载，具体导出实现通过薄委托进入该模块。

第一版正式函数包括：

- `export_scalar_frame(...)`
- `export_series_frame(...)`
- `export_peaks_frame(...)`
- `export_compare_report(...)`
- `export_report_package(...)`

推荐入口仍然是正式样本集对象方法：

- `sample_set.export_scalar_frame(...)`
- `sample_set.export_series_frame(...)`
- `sample_set.export_peaks_frame(...)`
- `sample_set.export_report_package(...)`

### `dyntool.config`

稳定性：`Public API`

`dyntool.config` 负责通用配置加载。

### `dyntool.resources`

稳定性：`Public API`

`dyntool.resources` 负责仓库内置资源读取。
