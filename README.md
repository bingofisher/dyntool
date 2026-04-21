# AdvDynTool

稳定性：`Public API`

AdvDynTool 是一个面向动力学计算、振动处理与评价的 Python 库。当前正式公开面采用“两层结构”：

- 顶层对象 API：`AccelSeries`、`Metadata`、`DefaultSample`、`DefaultSampleSet` 以及常用结果对象、限制对象和枚举
- 动作模块 API：`dyntool.storage`、`dyntool.plotting`、`dyntool.logging`、`dyntool.reporting`
- 正式支持模块：`dyntool.config`、`dyntool.resources`

当前版本线：

- 当前稳定线：`1.2.x`
- 当前稳定线：`1.2.x`
- 当前正式发布版本：`v1.2.1`
- 前一稳定版本：`v1.2.0`
- 正式发布日期：`2026-04-21`

变更记录见 [CHANGELOG.md](CHANGELOG.md)。迁移说明见 [docs/developer/migration_1_2_0.md](docs/developer/migration_1_2_0.md)。发布检查清单见 [docs/developer/release_checklist.md](docs/developer/release_checklist.md)。

## 推荐入口

- 样本与样本集：`DefaultSample`、`DefaultSampleSet`
- 存储：`dyntool.storage`
- 绘图：`dyntool.plotting`
- 报告导出：`dyntool.reporting`
- 资源与配置：`dyntool.resources`、`dyntool.config`

## GUI 骨架

- 项目层桌面骨架位于 `src/dyntool_gui/`
- 该 GUI 不属于 `dyntool` 库级 `Public API`
- 首轮只固定窗口布局、模块页、dock 区、按钮层级和占位状态
- 启动方式：

```powershell
uv sync --group gui
uv run python -B -m dyntool_gui.app
```

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
- plotting 的轴语义默认通过 `AxisConfig` 提供；`PlotTheme.axes` 继续只负责外观，`PlotTheme.axis_config` 和 `plot_dataset(..., axis_config=...)` 负责 continuous major/minor 刻度、科学计数法与倍频程标签策略，科学计数法 offset 文本的字号和位置也走这条正式配置链
- continuous 轴只要给了 `major_step` / `minor_step`，对应 `major_origin` / `minor_origin` 默认按 `0` 起算；continuous 轴默认不开科学计数法，只有显式开启时才启用
- `axis.<side>.label.fontsize` 控制轴标签字号，`axis.<side>.ticks.fontsize` 控制 ticklabel 字号；`formatter.scientific.fontsize` 只控制 offset 文本字号
- reporting 正式用于统计表导出、比较报告导出与报告包导出
- `DynTool` 与历史 `tool.*` 入口不再恢复

plotting TOML 当前正式采用点层级 schema：

- `grid.x.major / grid.x.minor / grid.y.major / grid.y.minor`
- `axis.x.label / axis.y.label`
- `axis.x / axis.y`

其中 `PlotTheme.axes` 继续只负责轴框和 tick 外观，`PlotTheme.grid` 负责网格策略与样式，`PlotTheme.axis_config` 与运行时 `axis_config` 负责 continuous / octave 轴语义。

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

## Codex 协作入口

如果你是在另一个项目里通过 Codex 询问“如何使用 AdvDynTool 完成某项任务”，推荐优先命中仓库级 skill `advdyntool-usage-guide`。

- 位置：`.agents/skills/advdyntool-usage-guide/`
- 适用问题：真实文件导入、样本与样本集、处理与评价、存储、绘图、日志、统计导出、报告包导出、资源查询
- 作用：把问题路由到当前正式 `Public API`、正式文档和正式示例
- 边界：这是面向 Codex 协作的仓库级技能，不是库运行时接口，也不替代 README、MkDocs 文档和公开 API

## 文档与质量命令

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'; uv run python -B -m mkdocs build --strict --site-dir .pytest_tmp/mkdocs-site
uv run python -B scripts/check_text_quality.py
uv run python -B scripts/check_docstring_coverage.py
uv run python -B scripts/check_mkdocs_site.py
uv run python -B scripts/check_repository_governance.py
uv run python -B scripts/check_helper_structure.py
$env:PYTHONDONTWRITEBYTECODE='1'; uv run python -B -m pytest -q --basetemp .pytest_tmp/pytest -p no:cacheprovider
```
