# 内部 API

稳定性：`Internal API`

本文面向维护者，说明当前实现层的边界。v1.2.0 起，plotting 的 compat facade 与旧式 helper/frame 公开口径已经删除，不再作为正式依赖。

## 关键边界

- `application -> domain/compute`
- `domain -> compute`
- `infrastructure -> domain`
- `compute -> domain` 明确禁止

## plotting 内部实现

`dyntool.plotting` 的正式公开面只保留 `PlotDataset`、`PlotTheme`、`PlotResult`、`PlotCategory`、`PlotStatMetric`、`PlotKind` 和四类 concrete plotter。

以下模块属于当前 plotting 的内部实现细节，不再作为正式推荐路径：

- `dyntool.plotting._axes_formatters`
- `dyntool.plotting._axes_frame`
- `dyntool.plotting._axes_helpers`
- `dyntool.plotting._plotters_base`
- `dyntool.plotting._plotters_common`
- `dyntool.plotting._plotters_frame`
- `dyntool.plotting._plotters_box`
- `dyntool.plotting._plotters_octave`
- `dyntool.plotting._plotters_story_value`

当前 plotting 的内部约束是：

- `PlotTheme` 只公开模板契约，不再公开 `axis_frame()` / `grid_frame()` 桥接方法
- concrete plotter 的正式构造签名只保留 `ax` / `theme`
- `AxisFrame`、`GridFrame`、`LegendHelper` 只供 plotting 内部组合使用

## storage 内部实现

`dyntool.storage` 的正式入口固定在顶层模块。`StorageRuntime` 在 v1.2.0 中继续保留，但定位已经收窄为 internal bridge。

当前 storage 运行时桥接位于：

- `dyntool.storage.runtime`
- `dyntool.storage._runtime_common`
- `dyntool.storage._model_runtime`
- `dyntool.storage._sample_runtime`
- `dyntool.storage._sample_set_runtime`

当前 SQLite/H5 样本集基础设施已拆分为多个内部模块：

- `dyntool.infrastructure.sample_storage_sqlite_h5`
- `dyntool.infrastructure.sample_storage_sqlite_h5_types`
- `dyntool.infrastructure.sample_storage_sqlite_h5_schema`
- `dyntool.infrastructure.sample_storage_sqlite_h5_projection`
- `dyntool.infrastructure.sample_storage_sqlite_h5_payload`
- `dyntool.infrastructure.sample_storage_sqlite_h5_sessions`
- `dyntool.infrastructure.sample_storage_sqlite_h5_strategy`

当前收敛原则是：

- 顶层 `dyntool.storage` 只保留正式门面
- 样本集 `connect/save/load` 的编排真源收敛到 runtime 内部 helper
- `StorageRuntime` 继续服务 `application.runtime_binding` 和对象方法运行时绑定，但不再作为正式推荐扩展点
- `sample_storage_sqlite_h5.py` 仅作为 umbrella 入口；legacy / experimental helper 不再占据正式实现中心

## domain 内部实现

v1.2.0 已开始把超大主文件中的纯内部逻辑外提为 support 模块，但不改变对象 API、单位语义和数值结果。

当前已落地的 internal support 包括：

- `dyntool.domain.models._time_series_compute`
- `dyntool.domain.models._time_series_io`
- `dyntool.domain.models._time_series_motion`
- `dyntool.domain.models._time_series_transforms`
- `dyntool.domain.samples._sample_set_compare`
- `dyntool.domain.samples._sample_set_storage`
- `dyntool.domain.samples._sample_set_views`

当前主文件的定位是：

- `dyntool.domain.samples.sets` 保留正式类定义、薄委托和必要编排
- `dyntool.domain.models.time_series` 保留正式类定义、薄委托和必要编排
- 旧实现块应持续从主文件移除，避免再次形成双实现源

## 阅读顺序

1. `dyntool.application.runtime_binding`
2. `dyntool.domain.runtime`
3. `dyntool.storage.runtime`
4. `dyntool.infrastructure.sample_set_storage`

## 稳定性说明

- `Public API` 只出现在正式公开面文档和 API 入口页
- `Internal API` 仅用于维护者和高级使用者
- `Private / implementation detail` 仅用于当前实现参考，不承诺稳定
