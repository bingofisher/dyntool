# AdvDynTool

稳定性：`Public API`

AdvDynTool 是一个面向动力学计算、振动处理与评价的 Python 库。当前正式公开面采用“两层结构”：

- 顶层对象 API：`AccelSeries`、`Metadata`、`DefaultSample`、`DefaultSampleSet` 以及常用结果对象、限制对象和枚举
- 动作模块 API：`dyntool.storage`、`dyntool.plotting`、`dyntool.logging`、`dyntool.reporting`
- 正式支持模块：`dyntool.config`、`dyntool.resources`

当前版本线：

- 当前稳定线：`1.2.x`
- 当前正式发布版本：`v1.2.4`
- 前一稳定版本：`v1.2.3`
- 正式发布日期：`2026-06-23`

变更记录见 [CHANGELOG.md](CHANGELOG.md)。迁移说明见 [docs/developer/migration_1_2_0.md](docs/developer/migration_1_2_0.md)。发布检查清单见 [docs/developer/release_checklist.md](docs/developer/release_checklist.md)。

## 推荐入口

力学时程沿用现有 `TimeSeries`：`ForceSeries`、`MomentSeries`、`StressSeries`、`StrainSeries` 分别对应力、力矩、应力和应变，注册为 `DefaultSample` 的 `force/moment/stress/strain` 槽位。默认单位为 N、N·m、Pa、无量纲，应变可输入 `microstrain` 或 `percent`。用法见[样本与样本集](docs/usage/02_samples_and_sets.md)。

- 样本与样本集：`DefaultSample`、`DefaultSampleSet`
- 存储：`dyntool.storage`
- 绘图：`dyntool.plotting`
- 报告导出：`dyntool.reporting`
- 资源与配置：`dyntool.resources`、`dyntool.config`

分频最大振级规范阈值使用 `FDMVLLimit.from_standard(FDMVLLimitStandard.JGJ_T_170_2009, scene="居民文教区夜间")`，该场景返回 62 dB 标量。全部区域昼夜标准值、适用条件及原曲线占位接口调整见 [规范限值说明](docs/developer/limit_models.md)。

标准枚举值只接受统一规范编号，例如 `ZVLLimitStandard.GB_10070_1988.value` 为 `"GB 10070-1988"`；旧编号 `"GB_10070-1988"` 明确拒绝，不提供兼容映射。限值 DataFrame / xarray 快照保留规范来源和可选追溯；标量恢复必须恰好一个值，CSV 往返仍需另行提供元信息。

## GUI 骨架

GUI 整合保留当前四页与参数对话框，吸收旧工作区的紧凑主题及预览关闭入口；见[操作手册](docs/user_manual.md)及[整合复核](docs/developer/gui_integration_review.md)。

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
- GUI v2 主线固定为 `点选状态 -> 命令快照 -> 管线节点 -> 统一反馈/审计`：对象树和页面控件只更新选择状态，执行入口生成 `GuiCommandSnapshot`，manager 基于快照生成管线节点并统一写回任务、日志、问题、导出记录与审计报告
- 当前 GUI 主窗口已收口为：顶部菜单栏与 4 页任务导航、左侧窄对象树、中央主工作区、底部薄任务/日志/问题区；右侧事实栏已删除，页面级状态改回各页主区摘要
- GUI 主界面当前采用“摘要 + 主动作 + 结果主体”结构；导入参数、筛选规则、处理参数、绘图设置和内部导出参数进入真实对话框，避免在左侧配置栏平铺堆叠低频复杂输入
- `2560x1440` 等 2K 横屏默认采用工作台密度：对象树目标宽度 `170-180px`、底部任务区目标高度 `96-112px`、导航按钮不超过 `30px`、页面头部不超过 `64px`
- `总览` 页只保留项目上下文、当前主样本集、当前能力、最近记录和下一步快捷动作
- `导入与筛选` 页固定为主样本集接入、检查、预览和子集管理页：
  - 默认入口是 `SampleSet`
  - `SampleSet` 支持正式仓库导入：`SET_H5`、`SET_SQLITE_H5`、`SET_DIR`、`SET_ATTR_TABLE`
  - `SampleSet` 预览阶段会自动推断 `sample_domain`；遇到未知或混合元数据模式会直接阻止导入
  - `Sample` 支持批量 CSV：多选文件或目录扫描
- `导入与筛选` 页当前采用横向导入控制带和下方子集工作台：上方负责 `项目上下文 / 接入来源 / 检查结果 / 绑定结果`，下方负责筛选摘要、metadata 预览和已保存子集；详细导入参数、筛选规则和子集保存信息通过对话框维护
- 导入与筛选页正式文案统一使用中文，`metadata schema` 统一显示为“元数据模式”
- 默认预览执行轻量检查：只读取仓库结构、元数据和存在性信息，不触发原始数据全量读载
- 需要精确单位汇总时，导入页提供显式“深度检查单位”动作；按实际存在的时程序列分类汇总
- 导入预览和执行使用后台任务，导入页、长任务对话框和底部任务区共享阶段前缀进度显示，并支持中止
- 当前 GUI 工作台基线固定为 `PySide6 Widgets + QMainWindow + QDockWidget + QStackedWidget`
- 长任务基线固定为 `QThread + worker QObject + Signal`，该约束只属于 GUI `Internal API` 实现合同
- 第六轮主视图已切到 `Model/View`：左侧资源树使用 `QTreeView + ResourceTreeModel`，底部任务/日志/问题区使用 `QTableView + 表模型`
- 页面主区摘要原位更新；`_reload_view()` 仅保留首屏初始化和整项目加载后的冷启动刷新
- GUI 项目文件已采用 JSON 持久化；窗口几何、Dock 布局、最近目录和主题偏好通过 `QSettings` 持久化
- 项目 JSON 先写入同目录暂存文件再替换；保存失败提示原因，并保留已有文件与未保存状态
- “保存分析数据”（`Ctrl+Shift+S`）另存完整主集到独立 SQLite/H5 仓库，默认放在项目目录的 `analysis_data` 下；成功后再“保存项目”记录仓库引用
- 关闭、新建、打开或替换主集前，分别提示未保存的分析数据与项目状态；保存失败或取消时保留当前工作区
- GUI 内部新增 `ImportManager` 与 `GuiRuntimeBridge`，分别负责导入任务编排与 runtime/private 行为隔离；这些都属于 `Internal API`
- 项目目录与导入源路径可以不一致；首次打开从项目目录开始，后续记住最近来源目录
- 导入成功后默认绑定为当前项目主集
- 导入中止、失败或关闭窗口时，旧主集保持不变，并先完成资源清理后再退出
- 处理、绘图、导出等后台任务运行或线程收尾期间，主窗口阻止直接关闭；可中止任务先通过全局或页内中止入口结束
- `导入与筛选` 页的子集工作区负责筛选、预览、保存和复用子样本集；子样本集按“查询条件 + 完整命中 UID”挂在当前主样本集下面
- 子集筛选采用论文搜索式布尔查询树：支持 `and / or / not`、`in / not_in`、`= / != / > / >= / < / <=`、`contains / not_contains`、`exists / not_exists`；字段路径固定为 `uid`、`alias`、`metadata.*`、`data.*`、`result.*`，筛选规则在对话框内以可增删条件/分组列表维护，并支持复制、删除、上移、下移和 metadata 分类候选值提示，不再使用固定槽位
- 子集预览表只显示 `preview rows`，不代表完整命中集合；动态子集保存查询定义和完整命中 UID，冻结子集进入当前范围时只使用保存时的 `resolved_uids`
- 当前工作范围统一为：`all_samples / saved_subset / multi_subset_union / temporary_selection / single_sample`
- `数据处理`、`图形绘制` 和内部导出工作区已改成按需直达的平行入口，不再强制用户按向导顺序切页
- `数据处理` 页当前已接入 `calc_freqspec`、`calc_respspec`、`eval_zvl`、`eval_otovl`、`eval_fdmvl`、`eval_fpvdv`
- `数据处理` 页当前采用动作驱动结构：主界面先选处理方法并执行，范围目标、严格/覆盖开关、动作专属参数和预览字段通过 `处理参数` 对话框维护，预览表继续显式触发
- `数据处理` 页执行前会按动作所需数据槽校准当前范围；缺少加速度等前置数据的样本在 GUI 任务、日志和问题列表中记录为跳过，不送入库层批处理
- `图形` 页当前已接入 `FigureCanvasQTAgg + NavigationToolbar2QT`，可直接绘制当前主样本集已有的模型或表格结果；主题、点数上限和保存格式通过 `绘图设置` 对话框维护，并保存 `png / svg / pdf`
- GUI 内部保存 `PlotRequestSnapshot` 区分“当前设置”和“画布结果”；模式、来源、样本/范围、点数上限、主题或保存模式改变后，旧图只能作为上次结果展示，必须重新渲染后才能保存或导出当前图
- 内部导出工作区当前已接入 `scalar_frame / series_frame / peaks_frame / current_plot_image` 的轻交付入口
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

## GUI 单路线与行为说明

GUI 是当前唯一正式项目壳，核心 Python 库继续独立使用。Web 路线已退出：源码、专属依赖、启动入口和发行包已移除，历史实现通过 Git 历史追溯。

需要完整可操作的展示项目时，运行 `uv run --group gui python -B -m examples.10_scenarios.09_gui_building_showcase.main --open`。该入口生成 36 条明确标注的合成建筑振动数据、实际派生结果和子集，并自动显示隔振前后对比图。多样本模型图以不同颜色和图例区分曲线，支持 OTOVL 来源。核心计算使用 `Public API`，桌面展示属于 GUI `Internal API`；详见 [建筑振动展示](docs/usage/gui_building_showcase.md)。

处理、预览、绘图和导出的空范围不再回退为全量。处理反馈汇总核心报告中的成功、跳过、失败和未执行数量；严格失败或中止保留已完成结果，并同步数据状态。

项目 JSON 保存工作区描述、原始来源和成功的分析仓库引用，不保存模型数组。“保存分析数据”另存全部主集，后续沿用成功目标；重新打开项目优先恢复已保存结果，不自动写回原始来源。详见 [GUI 单路线迁移与可靠性](docs/developer/gui_single_route_migration.md)。

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
sample.eval_zvl(overwrite=True, freq_range=(2.0, 60.0), time_windows=-1)
dt_storage.save_sample(sample, "output/sample.h5")
freqs, _ = dt_resources.center_freqs((2.0, 80.0))
print(freqs[:3])
```

## 当前正式边界

- 顶层只保留对象、结果对象、限制对象和必要枚举
- `DefaultSample / DefaultSampleSet` 是正式样本对象主名
- plotting 正式主链固定为 `PlotDataset -> PlotTheme -> concrete plotter -> PlotResult.ax`
- plotting 多子图正式组合层为 `PlotPanel -> SubplotLayout -> SubplotFigurePlotter -> PlotResult.axes`，用于把多个 `PlotDataset + concrete plotter` 组合到同一张 Matplotlib figure
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

多子图布局不扩展 TOML schema；`PlotTheme.figure.add_axes_rect` 作为整组子图外接区域，行列数、共享轴和宽高比例通过 Python 侧 `SubplotLayout` 表达。

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

主开发与主回归覆盖独立核心库 `src/dyntool` 和唯一桌面界面 `src/dyntool_gui`。不要使用普通 `uv run pytest`；测试前先创建 `.pytest_tmp`，测试后使用生成物清理脚本移除 `__pycache__` 等临时产物。

```powershell
uv run python -B scripts/clean_generated_artifacts.py --apply
New-Item -ItemType Directory -Force -Path .pytest_tmp | Out-Null
$env:PYTHONDONTWRITEBYTECODE='1'; uv run python -B -m mkdocs build --strict --site-dir .pytest_tmp/mkdocs-site
uv run ruff check --no-cache src/dyntool src/dyntool_gui tests examples scripts
uv run ruff format --check src/dyntool src/dyntool_gui tests examples scripts
uv run python -B scripts/check_text_quality.py
uv run python -B scripts/check_docstring_coverage.py
uv run python -B scripts/check_mkdocs_site.py
uv run python -B scripts/check_repository_governance.py
uv run python -B scripts/check_helper_structure.py
$env:PYTHONDONTWRITEBYTECODE='1'; uv run python -B -m pytest -q --basetemp .pytest_tmp/pytest -p no:cacheprovider
uv run python -B scripts/clean_generated_artifacts.py --apply
```

本轮核心库修正采用 SI 计算、完整单边 FFT 和单样本原子保存。行为变化与重新计算建议见 [核心库迁移说明](docs/developer/core_correctness_migration.md)。

## 核心库整改合同

查询返回独立样本状态，默认禁止写回源仓库，允许计算与另存；模型数组只读，编辑使用正式更新方法。报告数值统一 SI 并标注单位，普通 `scalar_frame()` 显示单位保持不变。派生结果新增可选计算依据与过期状态；旧数据继续可读，旧版重存可能丢失追溯扩展。行为及显式交换载荷迁移见 [核心架构整改说明](docs/developer/core_architecture_remediation.md)。

单位原位转换在内部通知失败时恢复模型和拥有者状态；结构化交换载荷的重复数值、单位及追溯信息冲突均明确拒绝，历史缺少可选追溯的载荷继续可读。

存储精度选项只处理数值载荷，计算参数和追溯保持原精度；输入数值未改变时，不因追溯表示差异使派生结果过期。

核心后续整改固定：传递函数采用输出/输入相位且保留浮点 Hz；组合谱须具有同一物理轴；评价载荷缺失标量不补零。xarray 快照保留形状、单位及可选追溯，样本流分支显式提交写回原槽位。行为迁移与复核见 [核心架构整改](docs/developer/core_architecture_remediation.md) 和 [复核记录](docs/developer/core_architecture_verification.md)。
