# AdvDynTool

## `SET_SQLITE_H5` v2 升级提示

- 当前正式 `SET_SQLITE_H5` 默认格式已经升级为 `v2`。
- `v2` 仅保留 `sample.metadata_json` 作为完整 metadata 源，不再维护 `sample_metadata_flat`。
- 旧版 `v1` 仓库会在首次连接时自动迁移到 `v2`。
- 当前已知权衡是 metadata 写入更快、SQLite 体积更小，但 `metadata_frame()` 与 `summary_frame(metadata_fields=...)` 会比旧版更慢。
- 旧代码不保证继续读取已升级到 `v2` 的仓库。

稳定性：`Public API`

AdvDynTool 是一个面向动力学计算、振动处理与评价的 Python 库。当前正式公开面采用“两层结构”：

- 顶层对象 API：`AccelSeries`、`Metadata`、`DefaultSample`、`DefaultSampleSet` 以及常用结果对象、限制对象和枚举
- 动作模块 API：`dyntool.storage`、`dyntool.plotting`、`dyntool.logging`
- 正式支持模块：`dyntool.config`、`dyntool.resources`

当前发布版本：`v1.1.1`

更新记录见 [CHANGELOG.md](CHANGELOG.md)。

## 推荐入口

## 存储补充约定

- `dyntool.storage` 的公开调用方式保持不变
- `StorageConnectOptions` 现在属于正式公开参数契约，可直接从 `dyntool` 或 `dyntool.storage` 导入
- 单模型 H5、单样本 H5、样本集 H5 默认启用 `gzip` 压缩
- 默认压缩级别为 `4`
- 样本/样本集 `data_options` 现在是正式契约，未知键、错用范围和非法压缩参数会直接报中文错误
- `DefaultSampleSet.load_all()`、`save_all()`、`convert_storage()` 现在支持 `show_progress` 与 `progress_callback`
- 当当前 logging 会输出到控制台时，批量读写默认自动显示简洁进度条；文件日志模式且不镜像到控制台时默认静默

`DefaultSample / DefaultSampleSet` 是当前唯一正式顶层样本对象名；`Sample / SampleSet` 顶层导入已移除。

```python
import dyntool.resources as dt_resources
import dyntool.storage as dt_storage
from dyntool import DefaultSample, SampleDomain, VibrationTestMetadata

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
dt_storage.save_sample(sample, "output/sample.h5")
freqs, _ = dt_resources.center_freqs((2.0, 80.0))
print(freqs[:3])
```

- structured payload 恢复当前接受的正式类别名包括 `DefaultSample`、`DefaultSampleSet`、`VibrationTestSample`、`VibrationTestSampleSet`
- 旧 payload 中的历史类别名 `Sample` / `SampleSet` 已移除；读取旧 payload 时会给出中文迁移提示

## 当前正式边界

- 顶层只保留对象、结果对象、限制对象和必要枚举
- `DefaultSample / DefaultSampleSet` 是正式主名
- `Sample / SampleSet` 顶层导入已移除，不再保留兼容别名
- 动作统一走模块，不再恢复 `DynTool` 门面
- plotting 正式固定为 `matplotlib` 静态路径
- `custom_extension` 只作为 `Internal API` 示例保留

## 文档入口

- [文档首页](docs/index.md)
- [公开 API](docs/api/public_api.md)
- [示例总览](docs/examples_overview.md)
- [架构说明](ARCHITECTURE.md)

## 文档与质量命令

```powershell
uv run python -B -m mkdocs build --strict --site-dir .pytest_tmp/mkdocs-site
uv run python -B scripts/check_text_quality.py
uv run python -B scripts/check_docstring_coverage.py
uv run python -B scripts/check_mkdocs_site.py
uv run python -B -m pytest -q --basetemp .pytest_tmp/pytest -p no:cacheprovider
```

## 大数据样本集读取优化

- 样本集读取现在统一收敛为“三层加载架构”：
  - 索引层：`uid`、`alias`、扁平 `metadata`、槽位存在性和 payload 定位
  - 摘要层：高价值标量与采样摘要，优先用于报表和筛选
  - payload 层：真实数组与复合对象，按最小槽位粒度读取
- `SampleLoadMode` 的公开语义保持不变：
  - `METADATA_ONLY` 只停在索引层
  - `LAZY` 首开停在索引层，访问时按槽位补载
  - `EAGER` 在索引层之后批量预热目标槽位
- 当前大数据主线优先推荐 `StorageScheme.SET_SQLITE_H5`：
  - SQLite 负责索引层与摘要层
  - H5 负责真实 payload
  - `scalar_frame()`、`metadata_frame()` 等可在可回答时绕过 payload 读取
- `StorageScheme` 命名已收敛为正式推荐口径：
  - `SET_DIR`
  - `SET_ATTR_TABLE`

## Storage 自动识别与完整性验证

- `dyntool.storage` 在读取和连接路径上支持 `storage_scheme` 自动识别
- 可通过 `detect_storage_scheme(path, kind=...)` 获取检测结果
- 可通过 `inspect_storage_repository(path, level="quick" | "deep")` 做仓库完整性验证
- `quick` 用于结构签名、必需文件和最小布局检查
- `deep` 用于索引、payload 和样本级一致性核对

```python
import dyntool.storage as dt_storage

scheme = dt_storage.detect_storage_scheme("output/sample_set.h5", kind="sample_set")
report = dt_storage.inspect_storage_repository("output/sample_set.h5", level="deep")
print(scheme, report.is_valid, report.sample_count)
```

## DefaultSampleSet 摘要对比

- `DefaultSampleSet.compare_with(...)` 提供结构与摘要级对比
- 默认比较 UID、metadata、槽位存在性，以及标量 `data_vars / features`
- 浮点数比较通过公开 `rtol + atol` 容差控制
- 推荐闭环为：`convert_storage(...) -> detect_storage_scheme(...) -> inspect_storage_repository(...) -> compare_with(...)`
## `SET_SQLITE_H5` 并发与吞吐

- 当前正式并发语义为“跨进程多读单写”。
- 读路径新增 reader session，复用 SQLite 连接与 `payload.h5` 只读句柄。
- 写路径保持单 writer session，复用 SQLite 连接与 `payload.h5` 句柄顺序落盘。
- `save_all()` 在 `SET_SQLITE_H5` 下已收敛为“单 writer session + artifact 缓冲 + chunk 级 SQLite 批量 flush”。
- 正式 benchmark 脚本：`uv run python -B scripts/benchmark_set_sqlite_h5_io.py`
