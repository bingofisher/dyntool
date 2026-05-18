# AdvDynTool

稳定性：`Public API`

AdvDynTool 是一个面向动力学计算、振动处理与评价的 Python 库。当前正式公开面采用“两层结构”：

- 顶层对象 API：`AccelSeries`、`Metadata`、`DefaultSample`、`DefaultSampleSet` 以及常用结果对象、限制对象和枚举
- 动作模块 API：`dyntool.storage`、`dyntool.plotting`、`dyntool.logging`、`dyntool.reporting`
- 正式支持模块：`dyntool.config`、`dyntool.resources`

当前版本线：

- 当前稳定线：`1.2.x`
- 当前正式发布版本：`v1.2.2`
- 前一稳定版本：`v1.2.1`
- 正式发布日期：`2026-05-18`

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
- 当前 GUI 第八轮已固定“真实工程库整体验证 + 全页面收敛”口径：
  - `处理` 动作与预览表生成拆开，执行动作后不再自动构建全量表
  - `绘图` 改为显式“渲染”，默认抽样，单条曲线点数上限 `20000`
  - `导出` 改为“前置校验 -> 执行导出”，缺少前置结果时只给出中文阻断提示与补算入口
- 已新增 `P-R1-3` 真实工程库 GUI 集成套件：
  - 全量通路覆盖仓库检查、轻量预览、深度单位检查、正式导入、全量 `calc_freqspec`、全量 `eval_zvl`
  - 页面正确性通路使用 `3` 个 UID 子集覆盖处理预览、单样本 `accel / freqspec` 绘图与真实导出
- 当前 GUI 顶层按任务型工作台组织：
- 当前正式主导航固定为 `总览 / 导入与筛选 / 数据处理 / 图形绘制`；`SUBSET / EXPORT` 只作为内部状态或工作区能力，不恢复为独立主页面
- 当前 GUI 主窗口已收口为：顶部菜单栏与 4 页任务导航、左侧窄对象树、中央主工作区、底部薄任务/日志/问题区；右侧事实栏已删除，页面级状态改回各页主区摘要
- `2560x1440` 等 2K 横屏默认采用工作台密度：对象树目标宽度 `170-180px`、底部任务区目标高度 `96-112px`、导航按钮不超过 `30px`、页面头部不超过 `64px`
- `总览` 页只保留项目上下文、当前主样本集、当前能力、最近记录和下一步快捷动作
- `导入与筛选` 页固定为主样本集接入、检查、预览和子集管理页：
  - 默认入口是 `SampleSet`
  - `SampleSet` 支持正式仓库导入：`SET_H5`、`SET_SQLITE_H5`、`SET_DIR`、`SET_ATTR_TABLE`
  - `SampleSet` 预览阶段会自动推断 `sample_domain`；遇到未知或混合元数据模式会直接阻止导入
  - `Sample` 支持批量 CSV：多选文件或目录扫描
- `导入与筛选` 页当前采用横向导入控制带和下方子集工作台：上方负责 `项目上下文 / 接入来源 / 检查结果 / 绑定结果`，下方负责筛选、metadata 预览和已保存子集
- 导入与筛选页正式文案统一使用中文，`metadata schema` 统一显示为“元数据模式”
- 默认预览执行轻量检查：只读取仓库结构、元数据和存在性信息，不触发原始数据全量读载
- 需要精确单位汇总时，导入页提供显式“深度检查单位”动作；按实际存在的时程序列分类汇总
- 导入预览和执行使用后台任务，导入页、长任务对话框和底部任务区共享阶段前缀进度显示，并支持中止
- 当前 GUI 工作台基线固定为 `PySide6 Widgets + QMainWindow + QDockWidget + QStackedWidget`
- 长任务基线固定为 `QThread + worker QObject + Signal`
- 第六轮主视图已切到 `Model/View`：左侧资源树使用 `QTreeView + ResourceTreeModel`，底部任务/日志/问题区使用 `QTableView + 表模型`
- 右侧信息区改为固定卡片原位更新；`_reload_view()` 仅保留首屏初始化和整项目加载后的冷启动刷新
- GUI 项目文件已采用 JSON 持久化；窗口几何、Dock 布局、最近目录和主题偏好通过 `QSettings` 持久化
- GUI 内部新增 `ImportManager` 与 `GuiRuntimeBridge`，分别负责导入任务编排与 runtime/private 行为隔离；这些都属于 `Internal API`
- 项目目录与导入源路径可以不一致；首次打开从项目目录开始，后续记住最近来源目录
- 导入成功后默认绑定为当前项目主集
- 导入中止、失败或关闭窗口时，旧主集保持不变，并先完成资源清理后再退出
- `筛选与子集` 页负责筛选、预览、保存和复用子样本集；子样本集按“条件 + 快照”双保存语义挂在当前主样本集下面
- `筛选与子集` 页当前按主样本集 `metadata` 字段动态生成 hook：离散字段走候选值多选语义，数值字段走区间输入，中央预览表按 `metadata_df` 风格显示 `UID / alias + metadata 字段`
- 当前工作范围统一为：`全部样本 / 当前子样本集 / 多子样本集 / 临时手选 / 单个样本`
- `分析`、`图形`、`交付` 三页已改成按需直达的平行入口，不再强制用户按向导顺序切页
- `分析` 页当前已接入 `calc_freqspec`、`calc_respspec`、`eval_zvl`、`eval_otovl`、`eval_fdmvl`、`eval_fpvdv`
- `分析` 页当前采用“先选处理方法，再显示该方法参数”的动作驱动结构：公共参数固定，动作专属参数按真实公开 API 差异展开，预览表继续显式触发
- `图形` 页当前已接入 `FigureCanvasQTAgg + NavigationToolbar2QT`，可直接绘制当前主样本集已有的模型或表格结果，并保存 `png / svg / pdf`
- `交付` 页当前已接入 `scalar_frame / series_frame / peaks_frame / current_plot_image` 的轻交付入口
- 三页优先消费当前主样本集已有数据；若缺少前置结果，由页面内直接给出中文缺口说明与补算入口
- 会写回主样本集的任务继续串行执行；纯绘图预览与图片保存不改变主样本集
- GUI 内部新增 `ProcessingManager`、`PlotManager`、`ExportManager`；这些都属于 `Internal API`
- 启动方式：默认进入空项目会话；需要演示数据时显式指定 `--demo bridge` 或 `--demo generic`

```powershell
uv sync --group gui
uv run python -B -m dyntool_gui.app
uv run python -B -m dyntool_gui.app --demo bridge
uv run python -B -m dyntool_gui.app --demo generic
```

## Web 工作台实验线（冻结）

稳定性：`Internal API`

- GUI 是当前唯一正式项目壳；Web 工作台仅保留为实验/验证路线，不再作为当前推荐工作台入口。
- Web 工作台位于 `src/dyntool_web/`；它不属于 `dyntool` 库级 `Public API`，本轮只保留源码、测试和可运行性，不继续扩张功能面。
- 第一阶段采用本地 `FastAPI` 服务、可直接服务的静态页面和 `Vite + React + TypeScript` 前端源码，不引入 Tauri，不引入 Plotly；正式图形仍由 `Matplotlib + PlotDataset + PlotTheme` 在后端生成 `SVG/PNG`。
- Web 工作台保留当前 `总览 / 导入与筛选 / 数据处理 / 图形绘制` 四页与现有真实主流程，用于内部验证 `轻量预览 -> 绑定主样本集 -> 子集范围 -> calc_freqspec -> Matplotlib SVG/PNG 渲染 -> 导出预检`；`demo=True` 仅保留为内部测试和演示入口。
- Web 工作台当前会记录会话版本、内存子集、任务进度和预览过期状态；子集保存仍是 Web 会话内存态，不改变项目持久化格式。
- 当前 Web 服务接口均为 `Internal API`，不改变存储格式、单位语义和 `dyntool` 正式公开面；Web 相关验证独立保留，但不再与 GUI 按对称主线推进。

```powershell
uv sync --group web
uv run python -B -m dyntool_web.server
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
- 全部 skill 的主入口、分界和保留策略见 `docs/developer/skill_governance.md`

## 文档与质量命令

主开发与主回归以 `src/dyntool` 和 `src/dyntool_gui` 为中心；`src/dyntool_web` 仍应保留独立验证，但不再作为与 GUI 对称推进的正式主线。不要使用普通 `uv run pytest`；测试前先创建 `.pytest_tmp`，测试后使用生成物清理脚本移除 `__pycache__` 等临时产物。

```powershell
uv run python -B scripts/clean_generated_artifacts.py --apply
New-Item -ItemType Directory -Force -Path .pytest_tmp | Out-Null
$env:PYTHONDONTWRITEBYTECODE='1'; uv run python -B -m mkdocs build --strict --site-dir .pytest_tmp/mkdocs-site
uv run ruff check --no-cache src/dyntool src/dyntool_gui src/dyntool_web tests examples scripts
uv run ruff format --check src/dyntool src/dyntool_gui src/dyntool_web tests examples scripts
uv run python -B scripts/check_text_quality.py
uv run python -B scripts/check_docstring_coverage.py
uv run python -B scripts/check_mkdocs_site.py
uv run python -B scripts/check_repository_governance.py
uv run python -B scripts/check_helper_structure.py
$env:PYTHONDONTWRITEBYTECODE='1'; uv run python -B -m pytest -q --basetemp .pytest_tmp/pytest -p no:cacheprovider
uv run python -B scripts/clean_generated_artifacts.py --apply
```
