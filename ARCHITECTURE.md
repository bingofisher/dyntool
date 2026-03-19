# AdvDynTool 架构说明

稳定性：`Public API`

## 目标

AdvDynTool 以数值结果正确、单位一致和结果可追溯为第一优先级。公开面遵循“对象在顶层，动作在模块，实现下沉内部”的原则。

## 实现层结构

- `domain`：对象、单位语义、样本与评价结果
- `compute`：数值计算、信号处理、评价流程
- `application`：默认运行时绑定和少量应用级编排
- `infrastructure`：持久化、日志 provider、内置资源文件、底层 I/O

依赖方向保持为：

- `application -> domain/compute`
- `domain -> compute`
- `infrastructure -> domain`

## 正式公开面

### 顶层对象层
- 常用模型：`AccelSeries`、`FreqSpec`、`RespSpec`
- 元数据与样本：`Metadata`、`VibrationTestMetadata`、`Sample`、`SampleSet`
- 结果与限制：`OperationResult`、`BatchOperationReport`、各类限制和评价对象
- 必要枚举：`SampleDomain`、`UnitSystem`、`StorageScheme`、`StorageMode`、`LoggingMode`、`PlotKind`

### 动作模块层
- `dyntool.storage`
- `dyntool.plotting`
- `dyntool.logging`

### 支持模块层
- `dyntool.config`
- `dyntool.resources`

### 内部实现层
以下路径属于 `Internal API`，不再在正式文档主路径中推荐：

- `application.runtime_binding`
- `domain.runtime`
- schema、registry、base、payload 和内部 helper

## 默认运行时主链

对象方法仍然保留，但只走一条默认主链：

- `src/dyntool/__init__.py`
- `src/dyntool/application/runtime_binding.py`
- `src/dyntool/domain/runtime/*`
- `src/dyntool/storage/runtime.py`

这条链路负责把对象级 `save/load/connect_storage` 委托到正式存储实现，不再维护第二套平行门面。

## 文档与示例策略

- 文档工程统一使用 `MkDocs + Material + mkdocstrings`
- `README.md` 只做入口摘要
- `docs/usage` 负责用户主路径
- `docs/api` 负责公开 API 说明
- `docs/developer` 负责内部规则和维护者手册
- `docs/reference` 负责自动模块参考
- 正式示例只展示顶层对象 API 和正式模块 API
- `custom_extension` 保留为 `Internal API` 示例，不进入正式导航和正式 smoke

## 文档同步规则

只要接口、行为或架构发生变化，至少同步更新：

- `README.md`
- `ARCHITECTURE.md`
- 正式文档站对应页面
- 至少一个示例
- 至少一个测试覆盖点
