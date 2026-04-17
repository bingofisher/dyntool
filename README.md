# AdvDynTool

稳定性：`Public API`

AdvDynTool 是一个面向动力学计算、振动处理与评价的 Python 库。当前正式公开面采用“两层结构”：

- 顶层对象 API：`AccelSeries`、`Metadata`、`DefaultSample`、`DefaultSampleSet` 以及常用结果对象、限制对象和枚举
- 动作模块 API：`dyntool.storage`、`dyntool.plotting`、`dyntool.logging`、`dyntool.reporting`
- 正式支持模块：`dyntool.config`、`dyntool.resources`

当前版本线：

- 当前稳定发布线：`1.2.x`
- 当前合并后补丁分支：`codex/v1.2.0-postmerge`
- 已发布 RC：`v1.2.0-rc.1`
- 正式发布内容：`v1.2.0`

变更记录见 [CHANGELOG.md](CHANGELOG.md)。迁移说明见 [docs/developer/migration_1_2_0.md](docs/developer/migration_1_2_0.md)。发布检查清单见 [docs/developer/release_checklist.md](docs/developer/release_checklist.md)。

## 推荐入口

- 样本与样本集：`DefaultSample`、`DefaultSampleSet`
- 存储：`dyntool.storage`
- 绘图：`dyntool.plotting`
- 报告导出：`dyntool.reporting`
- 资源与配置：`dyntool.resources`、`dyntool.config`

## 快速开始

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

## 当前正式边界

- 顶层只保留对象、结果对象、限制对象和必要枚举
- `DefaultSample / DefaultSampleSet` 是正式样本对象主名
- plotting 正式主链固定为 `PlotDataset -> PlotTheme -> concrete plotter -> PlotResult.ax`
- reporting 正式用于统计表导出、比较报告导出与报告包导出
- `DynTool` 与历史 `tool.*` 入口不再恢复

## 存储约定

- `dyntool.storage` 的正式调用方式保持不变
- `StorageConnectOptions` 属于正式公开参数契约
- 样本/样本集 `data_options` 属于正式契约，未知键和非法值会直接报中文错误
- `DefaultSampleSet.load_all()`、`save_all()`、`convert_storage()` 支持 `show_progress` 与 `progress_callback`
- 当前大数据主链优先推荐 `StorageScheme.SET_SQLITE_H5`

## 文档入口

- [文档首页](docs/index.md)
- [公开 API](docs/api/public_api.md)
- [示例总览](docs/examples_overview.md)
- [教程总览](docs/workflow_guide.md)
- [架构说明](ARCHITECTURE.md)

## 文档与质量命令

```powershell
uv run python -B -m mkdocs build --strict --site-dir .pytest_tmp/mkdocs-site
uv run python -B scripts/check_text_quality.py
uv run python -B scripts/check_docstring_coverage.py
uv run python -B scripts/check_mkdocs_site.py
uv run python -B -m pytest -q --basetemp .pytest_tmp/pytest -p no:cacheprovider
```
