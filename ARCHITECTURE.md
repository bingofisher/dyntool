# AdvDynTool 架构说明

稳定性：`Public API`

## 目标

AdvDynTool 以数值结果正确、单位一致和结果可追溯为第一优先级。公开面遵循“对象在顶层，动作在模块，实现下沉内部”的原则。

## 当前版本线

- 当前主目录对应 `main`，目标版本线为正式 `1.2.4`。
- `main` 承接 `1.2.x` 稳定维护、发布收口和项目层环境整理。
- 主目录 `AdvDynTool` 作为当前稳定主线目录，不再保留“主目录不直接推进收口”的旧口径。
- 迁移说明见 [docs/developer/migration_1_2_0.md](docs/developer/migration_1_2_0.md)。
- 发布检查项见 [docs/developer/release_checklist.md](docs/developer/release_checklist.md)。

## 实现层结构

- `domain`：对象、单位语义、样本与评价结果
- `compute`：数值计算、信号处理、评价流程
- `application`：默认运行时绑定和少量应用级编排
- `infrastructure`：持久化、日志 provider、内置资源文件、底层 I/O

依赖方向保持为：

- `application -> domain/compute`
- `domain -> compute`
- `infrastructure -> domain`

项目层 GUI 补充约束如下：

- `src/dyntool_gui` 是桌面工作台骨架，属于项目层应用，不进入 `dyntool` 库级公开面
- GUI 是当前唯一正式项目壳，当前主导航固定为 `总览 / 导入与筛选 / 数据处理 / 图形绘制`；导出只作为图形页、预检入口和内部导出工作区能力存在
- GUI 当前正式基线为 `PySide6 Widgets + QMainWindow + QDockWidget + QStackedWidget`
- GUI 长任务当前正式基线为 `QThread + worker QObject + Signal`，该约束只属于 GUI `Internal API` 实现合同
- GUI 第八轮将真实页面行为固定为：
  - `处理` 页先执行动作，再按显式请求生成预览表
  - `绘图` 页先选来源，再按显式请求渲染图形
  - 内部导出工作区先做前置校验，再执行真实导出
- GUI 已新增真实工程库集成套件，基线数据源为 `P-R1-3` 工程库：
  - 全量通路验证仓库检查、导入、主集绑定、全量 `calc_freqspec`、全量 `eval_zvl`
  - 页面正确性通路固定使用 `3` 个 UID 子集，避免页面默认落入全量大表与全量图集
- GUI 主工作台第六轮已收敛到 `Model/View`：资源树使用 `QTreeView + ResourceTreeModel`，底部任务/日志/问题区使用 `QTableView + 表模型`
- 页面主区摘要原位更新；`_reload_view()` 只用于首屏初始化与整项目重载后的冷启动刷新
- GUI 项目文件已采用 JSON 持久化，机器级偏好与窗口布局通过 `QSettings` 持久化
- `ProjectFileStore` 在目标目录暂存完整 JSON 后替换文件；窗口仅在保存成功后更新项目引用和已保存状态，预期 I/O 或序列化错误通过中文提示反馈
- `AnalysisSaveManager` 使用正式 `dyntool.storage.save_sample_set` 在后台逐样本提交完整主集，主线程接收报告后更新分析仓库引用、摘要和保存状态；保存与线程收尾纳入全局忙态
- GUI 默认启动进入空项目会话；演示数据只通过显式参数 `uv run python -B -m dyntool_gui.app --demo bridge|generic` 进入
- GUI 内部使用 `ImportManager` 编排导入任务，使用 `GuiRuntimeBridge` 隔离 runtime/private 行为；二者都属于 `Internal API`
- GUI 第七轮起新增 `ProcessingManager`、`PlotManager`、`ExportManager`，分别负责处理、绘图和内部导出能力的真实模块接入；三者同样属于 `Internal API`
- `dyntool_gui -> dyntool` 只允许依赖正式对象 API 和正式模块 API
- Web 路线已退出；发行包和正式依赖只保留核心库与 GUI，历史实现通过 Git 历史追溯。
- GUI 私有范围对象区分未解析与冻结空范围；处理报告汇总逐样本核心结果，严格失败和中止后的前序成功结果继续保留并刷新状态。
- 项目 JSON 保存工作区描述、来源及成功的分析仓库引用；数组由独立 SQLite/H5 仓库保存，恢复时优先读取该引用。项目与数据脏状态分别检查，关闭或替换项目须完成确认；具体迁移见 [GUI 单路线迁移与可靠性](docs/developer/gui_single_route_migration.md)。
- 整仓 Ruff 门禁覆盖 `src/dyntool`、`src/dyntool_gui`、`tests`、`examples` 和 `scripts`；现有 GUI 工作流测试继续保留。
- 建筑振动展示通过正式场景示例生成真实可计算的合成数组、预计算结果与项目。私有生成器在暂存目录完成核心计算和完整性检查后交付，原始仓库和可写分析仓库分离；展示启动适配沿用普通项目读取和 PlotManager，不扩展项目 JSON 或核心存储格式。两者属于 GUI `Internal API`，场景配置为 `Private / implementation detail`，不替换既有占位演示。GUI 多样本模型绘图支持 OTOVL，并用循环颜色与图例区分实际样本。见 [建筑振动展示](docs/usage/gui_building_showcase.md)。
- 仓库测试入口必须使用 `$env:PYTHONDONTWRITEBYTECODE='1'; uv run python -B -m pytest ...`，不要使用普通 `uv run pytest`，避免生成物守卫被 `__pycache__` 污染
- 测试前需要确保 `.pytest_tmp` 存在，测试后统一运行 `uv run python -B scripts/clean_generated_artifacts.py --apply`
- GUI 当前顶层按任务型工作台组织：
- GUI 当前正式主导航固定为 `总览 / 导入与筛选 / 数据处理 / 图形绘制`；`SUBSET / EXPORT` 只作为内部状态或工作区能力，不恢复为独立主页面
- GUI v2 操作管线固定为 `点选状态 -> 命令快照 -> 管线节点 -> 统一反馈/审计`：对象树、表格选择和页面控件先写入 `GuiSelectionSnapshot`，主流程按钮基于当时状态生成 `GuiCommandSnapshot`，manager 再把快照解析为导入、处理、绘图或导出管线节点
- GUI 统一反馈事实源为 `ProjectSession` 内的任务、日志、问题、导出记录和审查记录；审计工具只读取这些状态与 `command_snapshots / feedback_events`，不反向驱动业务
- GUI 主窗口当前保留 `菜单栏 + 单行 4 页任务导航 + 左窄对象树 + 中央视图 + 底部薄任务区`；右侧事实栏已移除，页面级状态说明回收到各页主区
- GUI 页面主界面当前采用“摘要 + 主动作 + 结果主体”结构；导入参数、筛选规则、处理参数、绘图设置和内部导出参数进入真实对话框，不在左侧配置栏平铺堆叠
- 2K 横屏工作台密度固定为：对象树目标宽度 `170-180px`、底部任务区目标高度 `96-112px`、导航按钮不超过 `30px`、页面头部不超过 `64px`
- `总览` 页负责项目概况、主集摘要、能力摘要和下一步快捷动作
- `导入与筛选` 页负责主样本集接入、结构化筛选、命中预览、保存子样本集和切换当前工作范围；默认入口是 `SampleSet`
  - 页面结构固定为上方横向导入控制带和下方子集工作台，不再使用编号步骤器，也不恢复独立“筛选与子集”主页面
- 导入参数通过 `导入参数` 对话框维护；导入页主界面只保留接入模式、来源路径、来源选择和导入主动作
- 子集工作区的正式筛选模型是 `FilterSpec(query_version=2)` 查询树，而不是旧的“字段条件 AND、单字段多值 OR”动态 hook
- 查询树由 `FilterGroup` 与 `FilterPredicate` 组成，布尔组合支持 `and / or / not`，谓词支持 `in / not_in`、`= / != / > / >= / < / <=`、`contains / not_contains`、`exists / not_exists`
- 查询字段路径固定为 `uid`、`alias`、`metadata.<field>`、`data.<slot>`、`result.<name>`；未知路径或不支持的操作符必须给出中文错误，不做静默放行；筛选规则编辑器采用可增删条件/分组列表，支持复制、删除、上移、下移和 metadata 分类候选值提示，不再使用固定数量条件槽
- 子集工作区主界面只保留筛选摘要、保存摘要、metadata 预览和已保存子集；metadata 字段筛选、布尔查询树、辅助条件、排序和分页通过 `筛选规则` 对话框维护，子集名称、说明和动态/冻结保存动作通过 `保存子集` 对话框维护
- 子样本集是主样本集上的范围对象，不是独立仓库；子集预览的 `preview_rows` 只受预览行数限制，完整命中 UID 集单独保存
- 动态子集保存查询定义和完整命中 UID；冻结子集进入当前工作范围时只使用保存时的 `resolved_uids`，不重放查询树
- 当前工作范围统一支持：`all_samples / saved_subset / multi_subset_union / temporary_selection / single_sample`
- `SampleSet` 走正式仓库导入：`SET_H5`、`SET_SQLITE_H5`、`SET_DIR`、`SET_ATTR_TABLE`
- `SampleSet` 预览先按仓库元数据模式自动推断 `sample_domain`；未知或混合元数据模式直接阻止导入
- `Sample` 走批量 CSV 导入：多选文件或目录扫描
- 导入默认先执行轻量检查，只读取仓库结构、元数据和存在性信息，不触发原始数据全量读载
- 样本集精确单位汇总属于显式“深度检查单位”动作，按实际存在的时程序列类型逐类汇总
- 导入预览与执行在后台线程中运行，导入页内显示带阶段前缀的进度条，底部任务区在导入模块下优先展示导入相关任务和日志
- 导入任务支持中止；中止、失败或关闭窗口时保留旧主集不变，并先完成线程与临时对象清理
- 处理、绘图、导出等后台任务运行或线程收尾期间，主窗口阻止直接关闭；处理任务中止采用协作式安全检查点，已请求中止后禁用重复点击并等待当前同步步骤结束
- 项目目录与导入源路径允许不一致；首次浏览从项目目录开始，后续优先使用最近来源目录
- `数据处理`、`图形绘制` 和内部导出工作区改成平行入口：
  - 页面优先消费当前主样本集已有数据
  - 缺少前置结果时，在页内给出中文缺口说明和“计算所需结果”入口
- `数据处理` 页当前只走正式公开对象 API：`calc_freqspec`、`calc_respspec`、`eval_zvl`、`eval_otovl`、`eval_fdmvl`、`eval_fpvdv`
- `数据处理` 页当前采用动作驱动请求模型：`ProcessingWorkspace` 只输出结构化处理请求，`ProcessingManager` 负责把公共参数与动作专属参数翻译成真实公开 API kwargs
- `数据处理` 页主界面只保留处理方法、执行入口和结果预览；范围目标、临时 UID、严格/覆盖开关、动作专属参数和预览字段通过 `处理参数` 对话框维护
- `ProcessingManager` 在 GUI 内部执行前构造处理范围计划；对需要 `accel` 的动作，只把具备前置数据的样本送入库层，缺少前置数据的样本统一写入处理状态、底部日志和问题列表
- `图形` 页当前使用 `Matplotlib + FigureCanvasQTAgg + NavigationToolbar2QT`
  - 单样本模型优先走 `PlotDataset.from_model(...)`
  - 样本集表格优先走 `PlotDataset.from_dataframe(...)`
- `图形` 页左侧只保留绘图模式、来源范围和渲染/保存/补算入口；主题路径、点数上限、保存模式和保存格式通过 `绘图设置` 对话框维护；渲染成功写入 GUI Internal 的 `PlotRequestSnapshot`，绘图设置变化后旧图不能继续作为当前设置保存或导出，必须重新渲染
- `交付` 页当前只暴露轻交付入口：`scalar_frame`、`series_frame`、`peaks_frame` 与 `current_plot_image`
- `ExportManager` 内部仍可调用正式公开导出 API；GUI 页面首版不再把 `report_package` 作为主入口
- 会写回主样本集的 GUI 任务继续串行执行，避免并发改写同一主样本集；处理写任务必须可枚举 UID 并按 UID 分块执行以支持协作式中止，无法枚举 UID 时拒绝启动不可中止的全量写任务；纯绘图预览与保存图片不参与主集写回串行链

## 正式公开面

`ForceSeries`、`MomentSeries`、`StressSeries`、`StrainSeries` 同级继承 `TimeSeries`，通过现有类别注册、`DefaultSample.sample_schema` 和计算源解析接入原有生命周期；不新增层、后端或存储布局。`Public API` 为四类模型及 `DefaultSample` 四个槽位；注册和来源解析仍为 `Private / implementation detail`。这些槽位复用通用处理、单位交换和持久化，不增加应力张量、材料本构或自动方向识别。`VibrationTestSample` 保持原 schema。

### 顶层对象层
- 常用模型：`AccelSeries`、`FreqSpec`、`RespSpec`
- 元数据与样本：`Metadata`、`VibrationTestMetadata`、`DefaultSample`、`DefaultSampleSet`
- 结果与限制：`OperationResult`、`BatchOperationReport`、各类限制和评价对象
- 必要枚举与参数类型：`SampleDomain`、`UnitSystem`、`StorageScheme`、`StorageMode`、`StorageConnectOptions`、`LoggingMode`、`PlotKind`

### 动作模块层
- `dyntool.storage`
- `dyntool.plotting`
- `dyntool.logging`
- `dyntool.reporting`

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
- `src/dyntool/reporting/__init__.py`

存储相关的当前实现约束补充如下：

- `dyntool.storage` 保持公开薄门面，不直接承载大段流程编排
- 运行时拆分到 `storage._runtime_common`、`_model_runtime`、`_sample_runtime`、`_sample_set_runtime`
- 样本/样本集 `data_options` 契约与 H5 默认参数集中在 `infrastructure.storage_options`
- H5 默认写入策略统一为 `gzip`，默认级别为 `4`
- 样本集批量读写与 `convert_storage()` 的默认进度显示，按当前 logging 是否输出到控制台判定；实现兼容 `stdlib` 与 `loguru`
- `connect_storage()` / `dyntool.storage.connect_sample_set()` 保持原参数形状，但参数优先级、详细连接日志和正式枚举约束已收紧

这条链路负责把对象级 `save/load/connect_storage` 以及统计导出、报告包导出委托到正式实现，不再维护第二套平行门面。

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
- writer session 复用 SQLite 连接，每个样本独立打开并关闭 H5 写句柄，再提交 SQLite。
- `save_all()` 对每个样本分别更新 `sample`、`sample_slot_presence` 与 `sample_summary_projection` 并提交，不保留延迟整批 flush。
- `load_many_fields()`、`load_all()`、`prefetch()`、`compare_with()` 的补载路径优先复用 reader session。
- 这条并发与吞吐规则当前只正式适用于 `SET_SQLITE_H5`。
- `sqlite_h5_v2` 的内部实验已收敛进正式 `SET_SQLITE_H5 v2`；当前正式实现不再维护独立实验分派路径。
## `SET_SQLITE_H5` v2 正式化说明

- 当前正式 `SET_SQLITE_H5` 已切换到 `v2` 存储布局。
- `v2` 只保留 `sample`、`sample_slot_presence` 和 `sample_summary_projection` 三类 SQLite 数据；完整 metadata 仅保存在 `sample.metadata_json` 中。
- 旧版 `v1` 仓库在连接时会自动迁移到 `v2`，迁移完成后继续以 `SET_SQLITE_H5` 身份工作。
- `metadata_frame()` 与 `summary_frame(metadata_fields=...)` 仍优先走 storage 快路径，但 `v2` 的快路径改为读取 `metadata_json` 后在 Python 侧展开。
- 这次升级的已知权衡是：写入与体积收益明显，但 metadata 表格读取速度低于旧版。
## plotting 轴配置

- `dyntool.plotting` 现已把轴语义正式提升为 `AxisConfig`
- `ContinuousAxisSpec` 用于连续轴的 major/minor ticks、科学计数法和显示范围控制
- `ContinuousAxisSpec` 同时承载科学计数法 offset 文本的字号与位置配置
- `OctaveAxisSpec` 用于倍频程轴的标签疏密与可选显式位置/标签
- `PlotTheme.axes` 继续只负责外观，不混入 locator 或 formatter 语义
- `PlotTheme.grid` 独立承载网格策略与样式，TOML 入口固定为 `grid.x.major / grid.x.minor / grid.y.major / grid.y.minor`
- 轴标签 TOML 入口固定为 `axis.x.label / axis.y.label`
- 轴语义 TOML 入口固定为 `axis.x / axis.y`
- `PlotTheme.axis_config` 只承载主题级默认轴语义
- 运行时优先级固定为：`plot_dataset(..., axis_config=...)` > plotter 构造参数 `axis_config` > `PlotTheme.axis_config` > plotter 内建默认行为
- plotting 正式 TOML schema 只使用 `grid.x.major / ...`、`axis.x.label / axis.y.label`、`axis.x / axis.y`；`PlotTheme.axis_config` 等字段名仅属于运行时对象说明
- continuous 轴只要给了 `major_step` / `minor_step`，对应 `major_origin` / `minor_origin` 默认按 `0` 起算；continuous 轴默认不开科学计数法，只有显式开启时才启用
- `axis.<side>.label.fontsize` 控制轴标签字号，`axis.<side>.ticks.fontsize` 控制 ticklabel 字号；`formatter.scientific.fontsize` 只控制 offset 文本字号
- 项目级 variant patch 仍属于项目层集成策略，不进入 `dyntool.plotting` 的正式 schema

## plotting 多子图组合

- `PlotPanel`、`SubplotLayout`、`SubplotFigurePlotter` 属于 `dyntool.plotting` 的正式 `Public API`
- 多子图层只负责 figure / axes 布局和 panel 编排；具体图种语义仍由 `FramePlotter`、`OneThirdOctavePlotter`、`StoryValuePlotter`、`BoxPlotter` 承担
- 每个 `PlotPanel` 显式接收 `PlotDataset` 与 concrete plotter，可按 panel 传入 `categories`、`names`、`legend_options`、`axis_config` 和图种运行时参数
- `SubplotLayout` v1 支持 `rows / cols`、`share_x / share_y`、`height_ratios / width_ratios`、`hspace / wspace`
- `PlotTheme.figure.add_axes_rect` 作为整组子图外接区域；多子图布局不新增 TOML schema，避免把布局组合语义写入单图模板契约
- `SubplotFigurePlotter.plot_panels(...)` 返回 `PlotResult`，其中 `axes` 汇总所有子图，`ax` 仍指向第一个子图

## 核心库一致性边界

稳定性：`Internal API`。单位转换集中在求解边界；`_SampleWritePlan` 统一非空槽位选择与 metadata，`_FileCommit` 和 `_WriteMarker` 负责提交、回滚及中断检测，`_SqliteSessionCleanup` 保证异常退出仍尝试释放全部资源，`_ScalarComparison` 统一 SI 比较。对象入口与独立模块入口共用目标切换前的选择性补载。内部对象属于 `Private / implementation detail`，不新增公开入口。四层依赖方向保持不变。完整合同见 [核心库迁移说明](docs/developer/core_correctness_migration.md)。

## 核心所有权与提交聚合

稳定性：`Private / implementation detail`。查询选择与独立状态、身份原子更新、不可变数组载荷、计算依据、样本写入计划及报告提交分别由私有聚合对象管理。公开计算 namespace 保留；未增加平行 runtime。单位换算更新表示和摘要，物理输入变化使依赖结果过期。追溯写入既有属性与 JSON / 摘要扩展，SQLite 保持 v2。

层外组装例外显式限定：`storage` 连接领域和基础设施，`reporting` 连接领域表、绘图及文件提交，`plotting` 依赖领域绘图类型和配置，`logging` / `config` 独立；类型叶模块禁止绕行实现层。完整合同见 [核心架构整改](docs/developer/core_architecture_remediation.md)。

## 规范限值统一链路

稳定性：限值对象和标准枚举属于 `Public API`，`domain.limits.registry` 与限值公共基类属于 `Internal API`。JGJ/T 170—2009 分频最大振级阈值沿“标准枚举 → CSV 资源 → LimitStandardSpec → ScalarLimitBase”解析，`FDMVLLimit` 保留类别，改为无频率轴的单个 dB 标量。绘图复用已有标量限值广播，存储复用模型 H5 路径和 UTF-8 规范元信息，不新增层外依赖、运行时或 SQLite 表。

`limit_building_fdmvl` 是准确的资源键；既有 `limit_building_zvl` 仍引用同一表，保留已有引用但不将该表作为最大 Z 振级阈值。数值求解和工程测量前提与阈值对象分开。接口调整、来源及功能—示例—测试映射见 [规范驱动限值模型](docs/developer/limit_models.md)。

标准按评价族划分枚举，成员名称使用 Python 标识符，值只接受正式编号；GB 10070 统一为 `GB 10070-1988`，旧下划线编号明确拒绝，不设置兼容映射。限值公共基类维护独立的 DataFrame / xarray 规范属性及可选追溯，标量恢复要求恰好一个值、一行表。资源键及现有磁盘目录不随显示编号重命名。

`Private / implementation detail`：模型单位发布由 `_ModelRepresentationUpdate` 聚合，在回调异常或可捕获中断后恢复模型、组合分量绑定、槽位追溯和脏状态；结构化载荷解析将重复追溯纳入一致性检查，缺失的历史扩展仍按原兼容合同读取。

交换载荷一致性检查包含可选追溯，存储精度的物理变更判断只比较数值和单位；精度处理保留 `_dyntool` / `_dyntool_state` 中实际计算参数，不把参数舍入误当成输入载荷更新。

同名坐标和值字段合并前验证一致性；交换版本只接受规范的非负 ASCII 三段编号。`_ResultProvenance` 在恢复边界校验已知结果的操作、参数、输入版本、单位、算法、库版本及 UTC 时间，拒绝残缺的 `fresh` / `stale` 声明和损坏历史；缺少可选追溯仍保持 `unknown`。没有新增存储字段或格式版本。

## 核心后续修复边界（2026-10-05）

稳定性：上述对象入口为 `Public API`；模型 xarray 交换、依赖登记及仓库检查聚合为 `Private / implementation detail`。共享交换适配保留字段维度、物理单位和可选追溯；组合谱构造统一校验相同物理轴。样本依赖按输入版本映射登记并迭代传播过期，分支继承提交目标但隔离计算状态，提交进入受控更新聚合。仓库 deep 复用模型恢复校验，SQLite 摘要一次批量读取；quick 不读取数组。保持四层方向、既有存储布局、SQLite v2 和单写者边界，详见 [后续整改](docs/developer/core_architecture_remediation.md)。
