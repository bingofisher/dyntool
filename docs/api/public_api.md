# 公开 API

稳定性：`Public API`

本文定义 AdvDynTool 当前正式公开面，并给出推荐的调用方式。

## 正式入口

- 顶层对象 API：`AccelSeries`、`Metadata`、`VibrationTestMetadata`、`DefaultSample`、`DefaultSampleSet`
- 结果对象：`OperationResult`、`BatchOperationReport`
- 模块 API：`dyntool.storage`、`dyntool.plotting`、`dyntool.logging`
- 支持模块：`dyntool.config`、`dyntool.resources`

### 样本类名口径

- `DefaultSample / DefaultSampleSet` 是当前唯一正式顶层样本对象名
- `Sample / SampleSet` 顶层导入已移除
- 内部实现仍可保留 `Sample` / `SampleSet` 命名，但不再属于正式公开面

### structured payload 类别名迁移说明

- 当前样本 payload 恢复接受的正式类别名包括 `DefaultSample`、`DefaultSampleSet`、`VibrationTestSample`、`VibrationTestSampleSet`
- 旧 payload 中的历史兼容类别名 `Sample`、`SampleSet` 已移除
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
- 连接参数类型：`StorageConnectOptions`
- 仓库检查与自动识别：`StorageRepositoryReport`、`detect_storage_scheme(...)`、`inspect_storage_repository(...)`
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
    StorageRepositoryReport,
    StorageConnectOptions,
    StorageAccessMode,
    detect_storage_scheme,
    inspect_storage_repository,
    StorageMode,
    StorageScheme,
)
```

### `dyntool.storage` 批量进度与连接日志

- `DefaultSampleSet.load_all(...)`、`save_all(...)`、`convert_storage(...)` 支持 `show_progress` 和 `progress_callback`
- 默认是否显示进度条，按当前 logging 是否输出到控制台判定
- 该规则同时兼容 `stdlib` 与 `loguru`
- `connect_storage(...)` 与 `dyntool.storage.connect_sample_set(...)` 保持原参数形状，但现在会记录更详细的连接开始/完成日志，并严格要求 `mode` / `storage_scheme` 使用正式枚举

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

## 大数据加载说明

- `SampleLoadMode` 的公开语义没有变化，但样本集内部已经统一到三层加载架构：
  - 索引层：`uid`、`alias`、扁平 `metadata`、槽位存在性、payload 定位信息
  - 摘要层：高价值标量与采样摘要
  - payload 层：真实数组与复合对象
- 因此在 `SET_SQLITE_H5` 下：
  - `metadata_frame()` 直接走索引层
  - `scalar_frame()` 在可回答时优先走摘要层
  - `LAZY` 首次访问只补载目标槽位，不再回退为整样本重建
- `SET_H5` 与 `SET_DIR` 也已经支持槽位级补载；这属于实现优化，不改变公开 API 形状。

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

## StorageScheme 命名迁移

- 正式推荐名称：`SET_DIR`、`SET_ATTR_TABLE`
- 旧名字 `SAMPLE_DIR`、`ATTR_TABLE` 已移除。
## 存储自动识别与完整性验证

- `detect_storage_scheme(...)`：按存储签名自动识别单样本或样本集存储方案
- `inspect_storage_repository(...)`：按 `quick / deep` 两层做仓库完整性验证
- `StorageRepositoryReport`：承载检测方案、校验层级、问题列表、告警和样本计数
- 这些能力默认服务于读路径、连接和迁移后的自检闭环，不改变现有保存接口形状

## DefaultSampleSet 对比

- `DefaultSampleSet.compare_with(...)`：提供结构与摘要级对比
- 默认比较 UID、metadata、槽位存在性和标量摘要
- 浮点标量比较通过 `rtol` 与 `atol` 控制容差
- 本轮不包含时间历程、频谱等 payload 的逐点差异比对
