# 公开 API

稳定性：`Public API`

本文只描述 AdvDynTool 当前正式公开面。v1.2.0 起，`configure_zh`、`ZhPlotConfig`、`AxisFrame`、`GridFrame`、`AxisHelper`、`LegendHelper`、`PlotterBase`、`PlotterKind`、`axes.py` facade 以及 `add()+plot()` 旧路径已删除，不再作为正式依赖。

## 正式入口

力学时程 `ForceSeries`、`MomentSeries`、`StressSeries`、`StrainSeries` 均从 `dyntool` 顶层公开导入，继承 `TimeSeries` 的 `from_data()`、CSV/H5、单位转换、处理和模型频谱入口。`DefaultSample` 通过 `force/moment/stress/strain` 槽位持有它们，并通过 `update_data()` 更新。`UnitSystem` 对应字段为 `force/moment/stress/strain`；详细用法见[样本与样本集中的力学时程槽位](../usage/02_samples_and_sets.md)。

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
sample.eval_zvl(overwrite=True, freq_range=(2.0, 60.0), time_windows=-1)
sample_set = DefaultSampleSet.from_samples([sample], sample_domain=SampleDomain.VIBRATION_TEST)
sample_set.save("output/sample_set.h5", storage_scheme=StorageScheme.SET_H5)
freqs, _ = dt_resources.center_freqs((2.0, 80.0))
print(freqs[:3])
```

## 规范限值对象

`FDMVLLimit` 是分频最大振级标量阈值，沿用 `ZVLLimit`、`FPVDVLimit` 的标量合同。正式标准枚举成员为 `FDMVLLimitStandard.JGJ_T_170_2009`。通过 `supported_standards()` 和 `supported_scenes(standard)` 查询，通过 `from_standard(standard, scene=...)` 取得单个阈值，`float(limit.fdmvl)` 读取当前单位下的数值。

原 FDMVL 曲线占位的 `from_data(freq=..., fdmvl=...)` 已调整为 `from_data(fdmvl=..., standard=..., scene=..., clause=..., resource_key=...)`，不含频率轴。绘图使用现有 `PlotDataset.add_limit(limit, axis=...)`。规范来源、适用条件与迁移见 [限值模型说明](../developer/limit_models.md)。

四种限值的标准枚举按评价类型独立校验；成员名使用下划线，`.value` 只接受规范编号。`ZVLLimitStandard.GB_10070_1988.value` 为 `GB 10070-1988`，历史 `GB_10070-1988` 明确拒绝。限值 `to_pandas()` / `to_xarray()` 在独立 `attrs` 中记录规范来源和可选追溯，沿原恢复接口往返；标量限值须恰好一个值、表须恰好一行。

::: dyntool.FDMVLLimit

::: dyntool.FDMVLLimitStandard

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
- `PlotPanel`
- `SubplotLayout`
- `SubplotFigurePlotter`
- `FramePlotter`
- `BoxPlotter`
- `OneThirdOctavePlotter`
- `StoryValuePlotter`

v1.2.0 起正式主链固定为：

1. `PlotDataset.from_* (...)`
2. `PlotTheme.from_file(path)` 或 `PlotTheme.default()`
3. `ConcretePlotter(...).plot_dataset(dataset, ax=ax, ...)`
4. `PlotResult.ax`

多子图组合使用同一条数据和图种主链，只在外层增加：

1. `PlotPanel(dataset, plotter, ...)`
2. `SubplotLayout(rows, cols, ...)`
3. `SubplotFigurePlotter(...).plot_panels(...)`
4. `PlotResult.axes`

若只需要快速把全局默认字体切到仓库内置 `SongTNR`，可以直接调用 `PlotTheme.apply_songtnr()`。

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

多子图示例：

```python
import dyntool.plotting as dt_plotting

dataset_a = dt_plotting.PlotDataset.from_axis_value(
    axis=[0.0, 0.1, 0.2],
    value=[0.0, 0.1, -0.05],
    name="accel",
    category=dt_plotting.PlotCategory.SAMPLE,
)
dataset_b = dt_plotting.PlotDataset.from_axis_value(
    axis=[2.0, 2.5, 3.15, 4.0],
    value=[60.0, 61.0, 62.0, 63.0],
    name="otovl",
    category=dt_plotting.PlotCategory.SAMPLE,
)
result = dt_plotting.SubplotFigurePlotter(
    layout=dt_plotting.SubplotLayout(rows=2, cols=1, height_ratios=(1.0, 1.2)),
).plot_panels(
    [
        dt_plotting.PlotPanel(
            dataset=dataset_a,
            plotter=dt_plotting.FramePlotter(),
            title="加速度时程",
        ),
        dt_plotting.PlotPanel(
            dataset=dataset_b,
            plotter=dt_plotting.OneThirdOctavePlotter(),
            title="1/3 倍频程",
        ),
    ]
)
print(len(result.axes))
```

字体快捷入口示例：

```python
import dyntool.plotting as dt_plotting

dt_plotting.PlotTheme.apply_songtnr()
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
## plotting 轴配置补充

`dyntool.plotting` 新增以下正式公开对象：

- `AxisConfig`
- `ContinuousAxisSpec`
- `OctaveAxisSpec`

推荐主链现在可以写成：

1. `PlotDataset.from_* (...)`
2. `PlotTheme.from_file(path)` 或 `PlotTheme.default()`
3. `ConcretePlotter(..., axis_config=...).plot_dataset(dataset, ax=ax, axis_config=...)`
4. `PlotResult.ax`

边界保持不变：

- `PlotTheme.axes` 继续只负责轴框、刻度和网格的外观
- `PlotTheme.axis_config` 负责主题级默认轴语义
- `AxisConfig` 负责连续轴 major/minor ticks、科学计数法与倍频程标签策略
- `ContinuousAxisSpec` 当前还支持 `major_step`、`minor_step`、`scientific_fontsize`、`scientific_offset_x`、`scientific_offset_y`，用于控制连续轴刻度和科学计数法 offset 文本

最小示例：

```python
import dyntool.plotting as dt_plotting

dataset = dt_plotting.PlotDataset.from_axis_value(
    axis=[0.0, 2.0, 4.0, 6.0],
    value=[0.0, 1.2, 1.5, 0.8],
    name="demo",
    category=dt_plotting.PlotCategory.SAMPLE,
)
axis_config = dt_plotting.AxisConfig(
    x=dt_plotting.ContinuousAxisSpec(
        major_step=2.0,
        major_origin=0.0,
        minor_step=1.0,
        minor_origin=0.0,
        tick_min=0.0,
        tick_max=6.0,
    ),
    y=dt_plotting.ContinuousAxisSpec(scientific=True),
)
result = dt_plotting.FramePlotter(axis_config=axis_config).plot_dataset(dataset)
```

补充说明：

- TOML 配置层当前已经统一切到 `grid.x.major / grid.x.minor / grid.y.major / grid.y.minor`
- 轴标签正式入口是 `axis.x.label / axis.y.label`
- 轴语义正式入口是 `axis.x / axis.y`
- `PlotTheme.axes` 继续只负责轴框和 tick 外观
- `PlotTheme.grid` 负责网格策略与样式
- `PlotTheme.axis_config` 负责主题级默认轴语义
- `OneThirdOctavePlotter` 当前正式支持 `x = OctaveAxisSpec` 与 `y = ContinuousAxisSpec`
- continuous 轴默认不开科学计数法，只有显式 `scientific=True` 或 TOML 写 `formatter.scientific.enabled = true` 才启用
- `major_origin / minor_origin` 只在对应 `major_step / minor_step` 存在时生效，默认都按 `0` 起算
- `axis.<side>.label.fontsize` 控制轴标签字号，`axis.<side>.ticks.fontsize` 控制 ticklabel 字号
- `formatter.scientific.fontsize` 只控制科学计数法 offset 文本字号
- 若项目内存在轻微变体，推荐在项目层读取基础 TOML 后用 `dyntool.config.deep_update(...)` 合并 variant patch，再把合并后的结果交给 `PlotTheme` / `axis_config` 主链

`PlotTheme.axis_labels` 是运行时对象上的主题级标签默认值；正式 TOML 入口是 `axis.x.label / axis.y.label`。标签文本会原样交给 Matplotlib；若需要数学公式，请按 Matplotlib 习惯写 `$...$`，推荐在 TOML 中优先使用单引号字面量字符串。

`OneThirdOctavePlotter` 当前正式支持 `x = OctaveAxisSpec` 与 `y = ContinuousAxisSpec` 的组合，因此倍频程图也可以通过 `axis_config.y` 使用 `major_step`、`minor_step` 与 `scientific_*`。

`AxisConfig` 继续只表达单张图的 `x / y` 轴语义，不直接承载 `C1 / C2 / C3 / C4` 这类业务分支。若项目内存在轻微变体，推荐在项目层读取基础 TOML 后用 `dyntool.config.deep_update(...)` 合并 variant patch，再把合并后的结果交给 `PlotTheme` / `axis_config` 主链。

## 核心数值与保存合同

核心计算参数和返回对象类型保持。FFT 长度、窗口前提、SI 比较容差和单样本提交语义见 [核心库迁移说明](../developer/core_correctness_migration.md)。FDMVL 限值占位接口的标量化调整见上文规范限值对象。

核心对象读取、查询视图权限、报告 SI 单位与追溯扩展合同见 [核心架构整改](../developer/core_architecture_remediation.md)。这些行为继续沿当前 Public API，迁移工具属于 Private / implementation detail。

后续计算合同：传递函数 `fs` 接受浮点 Hz，二维输入拒绝；组合谱分量要求同一物理轴。xarray 返回原有 Dataset/DataArray 类型并保留可选追溯，单位声明冲突报错；样本流分支显式提交遵循原样本槽位合同，见 [处理与结果](../usage/03_processing_and_results.md)。
