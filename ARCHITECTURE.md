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
- 元数据与样本：`Metadata`、`VibrationTestMetadata`、`DefaultSample`、`DefaultSampleSet`
- 结果与限制：`OperationResult`、`BatchOperationReport`、各类限制和评价对象
- 必要枚举与参数类型：`SampleDomain`、`UnitSystem`、`StorageScheme`、`StorageMode`、`StorageConnectOptions`、`LoggingMode`、`PlotKind`

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

存储相关的当前实现约束补充如下：

- `dyntool.storage` 保持公开薄门面，不直接承载大段流程编排
- 运行时拆分到 `storage._runtime_common`、`_model_runtime`、`_sample_runtime`、`_sample_set_runtime`
- 样本/样本集 `data_options` 契约与 H5 默认参数集中在 `infrastructure.storage_options`
- H5 默认写入策略统一为 `gzip`，默认级别为 `4`
- 样本集批量读写与 `convert_storage()` 的默认进度显示，按当前 logging 是否输出到控制台判定；实现兼容 `stdlib` 与 `loguru`
- `connect_storage()` / `dyntool.storage.connect_sample_set()` 保持原参数形状，但参数优先级、详细连接日志和正式枚举约束已收紧

这条链路负责把对象级 `save/load/connect_storage` 委托到正式存储实现，不再维护第二套平行门面。

样本 payload 恢复当前接受的正式类别名包括 `DefaultSample`、`DefaultSampleSet`、
`VibrationTestSample`、`VibrationTestSampleSet`；旧 payload 中的历史兼容类别名
`Sample` / `SampleSet` 已移除，并改为显式中文迁移报错。

当前顶层正式口径统一为 `DefaultSample / DefaultSampleSet`；`Sample / SampleSet`
仅允许作为内部实现命名存在，不再通过顶层公开入口导出。

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

## 大数据加载架构

- 样本集读取统一采用三层架构，而不是把 `LAZY` 仅理解为“按需重读整样本”：
  - 索引层：`uid`、`alias`、扁平 `metadata`、槽位存在性、payload 定位信息
  - 摘要层：高价值标量与采样摘要，例如 `pga/pgv/pgd`、`zvl`、`sample_count/dt/duration`
  - payload 层：真实数组和复合对象，按最小槽位或 `data_var/dataset` 粒度读取
- `METADATA_ONLY`、`LAZY`、`EAGER` 三种模式共用同一套内部框架：
  - `METADATA_ONLY` 只停在索引层
  - `LAZY` 首开停在索引层，访问时优先命中摘要层，仍不够时再读 payload 层
  - `EAGER` 先完成索引层，再批量执行摘要层和 payload 层
- 样本补载已从“整样本重建再拷回”收敛为“槽位级补载”。
- 三种样本集方案按统一口径落地：
  - `SET_SQLITE_H5`：SQLite 承担索引层和摘要层，H5 只负责 payload
  - `SET_H5`：补轻量快速路径和批量 reader 复用
  - `SET_DIR`：缓存目录布局与槽位存在性，按目标槽位文件直读
- `StorageScheme` 正式推荐口径统一为 `SET_DIR`、`SET_ATTR_TABLE`。
## 存储读路径自动识别

- `dyntool.storage` 的读路径现在支持自动识别 `storage_scheme`
- 自动识别优先按存储签名工作，再结合现有运行时连接逻辑完成读取
- 若显式传入的 `storage_scheme` 与检测结果冲突，会直接报中文错误，不做静默回退

## 仓库完整性验证分层

- 存储仓库完整性验证固定为两层：
  - `quick`：结构签名、必需文件和最小布局检查
  - `deep`：索引、payload 与样本级一致性核对
- 正式公开入口为 `inspect_storage_repository(...)`
- 正式返回对象为 `StorageRepositoryReport`

## DefaultSampleSet 结构与摘要对比

- `DefaultSampleSet.compare_with(...)` 属于正式公开对象方法
- v1 对比范围固定为：
  - 类型与 UID 集
  - metadata 扁平字段
  - 槽位存在性
  - 标量 `data_vars / features`
- 浮点摘要比较采用公开 `rtol + atol` 容差
- 本轮不引入时间历程或频谱 payload 的逐点 diff
## `SET_SQLITE_H5` 读写架构补充

- 仓库级并发规则固定为“多读单写”。
- reader session 负责复用 SQLite 只读连接与 `payload.h5` 只读句柄。
- writer session 负责复用 SQLite 写连接与 `payload.h5` 写句柄，并顺序提交样本。
- `save_all()` 在 writer session 内继续保持单样本 H5 顺序写入，但会把 `sample`、`sample_slot_presence` 与 `sample_summary_projection` 收敛为 chunk 级 SQLite 批量 flush。
- `load_many_fields()`、`load_all()`、`prefetch()`、`compare_with()` 的补载路径优先复用 reader session。
- 这条并发与吞吐规则当前只正式适用于 `SET_SQLITE_H5`。
- `sqlite_h5_v2` 的内部实验已收敛进正式 `SET_SQLITE_H5 v2`；当前正式实现不再维护独立实验分派路径。
## `SET_SQLITE_H5` v2 正式化说明

- 当前正式 `SET_SQLITE_H5` 已切换到 `v2` 存储布局。
- `v2` 只保留 `sample`、`sample_slot_presence` 和 `sample_summary_projection` 三类 SQLite 数据；完整 metadata 仅保存在 `sample.metadata_json` 中。
- 旧版 `v1` 仓库在连接时会自动迁移到 `v2`，迁移完成后继续以 `SET_SQLITE_H5` 身份工作。
- `metadata_frame()` 与 `summary_frame(metadata_fields=...)` 仍优先走 storage 快路径，但 `v2` 的快路径改为读取 `metadata_json` 后在 Python 侧展开。
- 这次升级的已知权衡是：写入与体积收益明显，但 metadata 表格读取速度低于旧版。
