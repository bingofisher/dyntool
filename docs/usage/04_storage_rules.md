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

## 自动识别与完整性验证

`dyntool.storage` 现在提供两类正式公开能力：

- `detect_storage_scheme(path, kind=...)`
  作用：根据路径和最小存储签名自动识别正式 `StorageScheme`
- `inspect_storage_repository(path, storage_scheme=None, level="quick" | "deep")`
  作用：检查样本或样本集存储仓库的结构与完整性，并返回 `StorageRepositoryReport`

推荐用法：

```python
import dyntool.storage as dt_storage

scheme = dt_storage.detect_storage_scheme("output/sample_set.h5", kind="sample_set")
report = dt_storage.inspect_storage_repository("output/sample_set.h5", level="deep")

print(scheme.value)
print(report.is_valid, report.sample_count)
```

检查层级固定为两层：

- `quick`
  仅检查路径存在性、最小结构签名和必需文件
- `deep`
  在 `quick` 基础上继续检查索引、payload 和样本级一致性

如果显式传入的 `storage_scheme` 与自动识别结果冲突，读路径会直接报中文错误，不会静默回退。

## H5 默认压缩

- 单模型 H5、单样本 H5、样本集 H5 现在默认都启用 `gzip`
- 默认压缩级别为 `4`
- 如果显式覆盖压缩配置，则以显式配置为准
- 未知键、错用范围或非法压缩参数会直接报中文错误，不再静默忽略

## `data_options` 正式契约

`data_options` 只用于样本和样本集存储入口。当前支持下列键：

- `attr_data_format`
  作用：控制 `StorageScheme.SET_ATTR_TABLE` 中属性槽位落盘为 `csv` 或 `npy`
  默认值：`csv`
  适用范围：仅 `SET_ATTR_TABLE`
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
- 对 `SET_ATTR_TABLE` 之外的方案传入 `attr_data_format` 会直接报错
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
- `StorageConnectOptions`
- `DefaultSample.save(...)`
- `DefaultSample.load(...)`
- `DefaultSampleSet.from_storage(...)`
- `DefaultSampleSet.save_all(...)`
- `DefaultSampleSet.load_all(...)`
- `dyntool.storage`
- `detect_storage_scheme(...)`
- `inspect_storage_repository(...)`
- `StorageRepositoryReport`

当你需要显式声明懒加载或只读视图时，应直接从 `dyntool.storage` 导入
`SampleLoadMode`、`StorageAccessMode` 与 `SampleSetViewOptions`，而不是依赖内部模块路径。

当你需要显式声明连接参数时，应优先直接使用 `StorageConnectOptions`，并继续搭配正式
`StorageScheme`、`StorageMode` 枚举；这些类型现在都属于稳定公开面。

## 批量读写进度条

- `DefaultSampleSet.load_all(...)`
- `DefaultSampleSet.save_all(...)`
- `DefaultSampleSet.convert_storage(...)`

以上批量操作现在都支持：

- `show_progress`
  作用：控制是否显示内置终端进度条
  允许值：`True`、`False`、`None`
- `progress_callback`
  作用：接收 `(completed, total)` 形式的标准进度回调

默认规则：

- `show_progress=True` 时强制显示
- `show_progress=False` 时强制关闭
- `show_progress=None` 时按当前 logging 配置自动判定
- `CONSOLE_ONLY` 默认显示
- `SINGLE_FILE` / `DIRECTORY` 且 `mirror_to_console=True` 默认显示
- 文件日志且不镜像到控制台时默认不显示

进度条正文固定为简洁版，只显示任务名、进度、百分比、速率、耗时和剩余时间；详细参数统一写入日志，不默认刷样本 UID。

## connect 参数与详细日志

- `connect_storage(...)` / `dyntool.storage.connect_sample_set(...)` 继续保持原有参数形状
- 显式 kwargs 优先于 `StorageConnectOptions`
- `mode` 与 `storage_scheme` 必须使用正式枚举
- `name_resolver` 必须是可调用对象
- `set_filename` 只对集合型存储方案生效
- `data_options` 继续早失败，未知键和不适用键不会静默忽略

连接开始与完成时会写详细日志，包含：

- 目标路径
- `mode`
- `storage_scheme`
- `set_filename`
- `name_resolver` 是否启用
- `data_options` 关键摘要

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

## 转换后的摘要对比

样本集转换完成后，推荐闭环是：

1. 通过 `detect_storage_scheme(...)` 自动识别目标存储
2. 通过 `inspect_storage_repository(..., level="quick" / "deep")` 做结构与深度检查
3. 重新读取目标样本集后，调用 `sample_set.compare_with(...)` 做结构与摘要级一致性对比

## 大数据样本集加载规则

- 样本集读取统一采用三层加载架构：
  - 索引层：`uid`、`alias`、扁平 `metadata`、槽位存在性、payload 定位信息
  - 摘要层：高价值标量与采样摘要，例如 `pga/pgv/pgd`、`zvl`、`sample_count/dt/duration`
  - payload 层：真实数组与复合对象，按最小槽位粒度读取
- `SampleLoadMode` 的正式语义保持不变，但内部执行路径已统一：
  - `METADATA_ONLY` 只停在索引层
  - `LAZY` 首开停在索引层，访问时按目标槽位补载
  - `EAGER` 在索引层之后批量预热目标槽位
- 对大数据样本集，优先推荐 `StorageScheme.SET_SQLITE_H5`：
  - SQLite 负责索引层和摘要层
  - H5 负责真实 payload
  - `metadata_frame()` 与可由摘要层回答的 `scalar_frame()` 不再隐式触发 payload 读取
- `SET_H5` 与 `SET_DIR` 也按相同口径优化：
  - `SET_H5` 走集合文件内的槽位级直读
  - `SET_DIR` 走目录布局缓存与槽位文件直读

## StorageScheme 命名迁移说明

- 正式推荐名称：`SET_DIR`、`SET_ATTR_TABLE`
- 旧名字 `SAMPLE_DIR`、`ATTR_TABLE` 已移除。
## `SET_SQLITE_H5` 并发与吞吐优化

稳定性：`Public API`

- `SET_SQLITE_H5` 当前正式并发语义为“跨进程多读单写”。
- 任意时刻只允许一个 writer 会话写入仓库。
- 无 writer 时允许多个 reader 并发读取。
- 当 writer 已持有仓库写锁时，新 reader 会阻塞等待写入完成后再继续读取。
- 这条规则只正式适用于 `SET_SQLITE_H5`；`SET_H5` 本轮不承诺同等级别的跨进程并发安全。

当前实现同时做了两类内部优化：

- 读路径为 `SET_SQLITE_H5` 增加 reader session，复用单个 SQLite 连接和单个 `payload.h5` 只读句柄。
- 写路径为 `SET_SQLITE_H5` 继续使用单 writer session，复用单个 SQLite 连接和单个 `payload.h5` 句柄顺序提交写入。
- `save_all()` 的内部实现已进一步收敛为“单 writer session + artifact 缓冲 + chunk 级 SQLite 批量 flush”；这属于 `Private / implementation detail`，不改变公开 API 和存储格式。

因此，在以下主链中，重复打开 H5 文件的开销已被显著收敛：

- `load_many_fields(...)`
- `prefetch(...)`
- `load_all(..., load_mode=EAGER, categories=[...])`
- `compare_with(...)` 的标量摘要补载

如果你需要检查当前仓库是否符合静态结构要求，应继续使用：

- `detect_storage_scheme(...)`
- `inspect_storage_repository(..., level="quick" | "deep")`

需要注意，锁冲突属于运行时占用问题，不属于仓库静态完整性问题。

## `SET_SQLITE_H5` Benchmark

稳定性：`Internal API`

仓库提供了正式 benchmark 脚本，用于量化 `SET_SQLITE_H5` 的读写吞吐提升：

```powershell
uv run python -B scripts/benchmark_set_sqlite_h5_io.py
```

当前脚本覆盖三条典型主链：

- `load_many_fields()`
- `load_all(..., load_mode=EAGER, categories=["accel"])`
- `save_all()`

这组基线用于证明两个结论：

- `connect -> save_all -> load_all -> summary_frame` 的阶段链仍然存在
- `scalar_frame()` / `compare_with()` 依赖的摘要路径不会回退到 payload 直读

当前 proof 层只要求阶段命中和功能一致，不要求固定毫秒阈值；性能优劣应由基准脚本输出和真实仓库 A/B 结果判断。

脚本会输出：

- 基准样本规模
- 优化前耗时
- 优化后耗时
- 加速倍率
## `SET_SQLITE_H5` v2 格式升级说明

- 当前正式 `SET_SQLITE_H5` 默认格式已经升级为 `v2`。
- `v2` 仅保留 `sample.metadata_json` 作为完整 metadata 源，不再维护 `sample_metadata_flat`。
- 旧版 `v1` 仓库在首次连接时会自动迁移到 `v2`。
- `inspect_storage_repository(..., level="deep")` 会同时接受：
  - 旧版 `v1` 仓库仍然带有 `sample_metadata_flat`
  - 新版 `v2` 仓库不再要求 `sample_metadata_flat`
- 当前已知权衡：
  - metadata 写入速度、SQLite 体积和总仓库体积显著改善
  - `metadata_frame()` 与 `summary_frame(metadata_fields=...)` 会比旧版更慢，但结果保持准确
- 旧代码不保证继续读取已迁移到 `v2` 的仓库。
