# AdvDynTool 架构说明

稳定性：`Public API`

## 目标

AdvDynTool 以数值结果正确、单位一致和结果可追溯为第一优先级。公开面遵循“对象在顶层，动作在模块，实现下沉内部”的原则。

## 当前版本线

- 当前主目录对应 `main`，目标版本线为正式 `1.2.2`。
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
- GUI 是当前唯一正式项目壳，当前主链固定为 `导入与筛选 / 数据处理 / 图形绘制 / 导出`
- GUI 当前正式基线为 `PySide6 Widgets + QMainWindow + QDockWidget + QStackedWidget`
- GUI 长任务当前正式基线为 `QThread + worker QObject + Signal`
- `src/dyntool_web` 是保留源码与可运行性的 Web 工作台实验线，属于 `Internal API`，不进入 `dyntool` 库级公开面
- Web 工作台第一阶段采用 `FastAPI + 静态页面 + Vite React TypeScript 源码` 本地服务，不引入 Tauri，不引入 Plotly；正式图形继续由 `Matplotlib + PlotDataset + PlotTheme` 在后端生成 `SVG/PNG`
- Web 工作台保留现有路径管理、真实 `SET_SQLITE_H5` 仓库轻量预览与绑定、任务进度、处理默认参数、只读预览、导出预检和项目级 PlotTheme 编辑能力，但本轮起不再继续扩张
- Web 工作台保留当前真实验证流程：`轻量预览 -> 绑定主样本集 -> 子集范围 -> calc_freqspec -> Matplotlib SVG/PNG 渲染 -> 导出预检`
- Web 工作台会话层维护内部版本号、任务记录、问题记录、预览过期标记和内存子集；这些状态只属于 `dyntool_web` 内部应用协议，不进入库级公开面或项目持久化格式
- GUI 第八轮将真实页面行为固定为：
  - `处理` 页先执行动作，再按显式请求生成预览表
  - `绘图` 页先选来源，再按显式请求渲染图形
  - `导出` 页先做前置校验，再执行真实导出
- GUI 已新增真实工程库集成套件，基线数据源为 `P-R1-3` 工程库：
  - 全量通路验证仓库检查、导入、主集绑定、全量 `calc_freqspec`、全量 `eval_zvl`
  - 页面正确性通路固定使用 `3` 个 UID 子集，避免页面默认落入全量大表与全量图集
- GUI 主工作台第六轮已收敛到 `Model/View`：资源树使用 `QTreeView + ResourceTreeModel`，底部任务/日志/问题区使用 `QTableView + 表模型`
- 右侧信息区采用固定卡片原位更新；`_reload_view()` 只用于首屏初始化与整项目重载后的冷启动刷新
- GUI 项目文件已采用 JSON 持久化，机器级偏好与窗口布局通过 `QSettings` 持久化
- GUI 默认启动进入空项目会话；演示数据只通过显式参数 `uv run python -B -m dyntool_gui.app --demo bridge|generic` 进入
- GUI 内部使用 `ImportManager` 编排导入任务，使用 `GuiRuntimeBridge` 隔离 runtime/private 行为；二者都属于 `Internal API`
- GUI 第七轮起新增 `ProcessingManager`、`PlotManager`、`ExportManager`，分别负责处理、绘图、导出页的真实模块接入；三者同样属于 `Internal API`
- `dyntool_gui -> dyntool` 只允许依赖正式对象 API 和正式模块 API
- 整仓质量门禁仍应显式覆盖 `src/dyntool_gui`、`src/dyntool_web`、`tests` 和 `scripts`；但主问题清单、主收敛叙事和主迭代节奏以 GUI 为准，Web 按实验线独立验证
- 仓库测试入口必须使用 `$env:PYTHONDONTWRITEBYTECODE='1'; uv run python -B -m pytest ...`，不要使用普通 `uv run pytest`，避免生成物守卫被 `__pycache__` 污染
- 测试前需要确保 `.pytest_tmp` 存在，测试后统一运行 `uv run python -B scripts/clean_generated_artifacts.py --apply`
- GUI 当前顶层按任务型工作台组织：
- GUI 当前正式主导航固定为 `总览 / 导入与筛选 / 数据处理 / 图形绘制`；`SUBSET / EXPORT` 只作为内部状态或工作区能力，不恢复为独立主页面
- GUI 主窗口当前保留 `菜单栏 + 单行 4 页任务导航 + 左窄对象树 + 中央视图 + 底部薄任务区`；右侧事实栏已移除，页面级状态说明回收到各页主区
- 2K 横屏工作台密度固定为：对象树目标宽度 `170-180px`、底部任务区目标高度 `96-112px`、导航按钮不超过 `30px`、页面头部不超过 `64px`
- `总览` 页负责项目概况、主集摘要、能力摘要和下一步快捷动作
- `导入与筛选` 页负责主样本集接入、结构化筛选、命中预览、保存子样本集和切换当前工作范围；默认入口是 `SampleSet`
  - 页面结构固定为上方横向导入控制带和下方子集工作台，不再使用编号步骤器，也不恢复独立“筛选与子集”主页面
- `筛选与子集` 页当前由主样本集 `metadata_fields` 驱动动态 hook；内部筛选语义固定为“字段条件 AND、单字段多值 OR”，中央主视图固定为 `metadata_df` 风格预览表
- 子样本集是主样本集上的范围对象，不是独立仓库；当前采用“条件 + 快照”双保存语义
- 当前工作范围统一支持：`all_samples / saved_subset / multi_subset_union / temporary_selection / single_sample`
- `SampleSet` 走正式仓库导入：`SET_H5`、`SET_SQLITE_H5`、`SET_DIR`、`SET_ATTR_TABLE`
- `SampleSet` 预览先按仓库元数据模式自动推断 `sample_domain`；未知或混合元数据模式直接阻止导入
- `Sample` 走批量 CSV 导入：多选文件或目录扫描
- 导入默认先执行轻量检查，只读取仓库结构、元数据和存在性信息，不触发原始数据全量读载
- 样本集精确单位汇总属于显式“深度检查单位”动作，按实际存在的时程序列类型逐类汇总
- 导入预览与执行在后台线程中运行，导入页内显示带阶段前缀的进度条，底部任务区在导入模块下优先展示导入相关任务和日志
- 导入任务支持中止；中止、失败或关闭窗口时保留旧主集不变，并先完成线程与临时对象清理
- 项目目录与导入源路径允许不一致；首次浏览从项目目录开始，后续优先使用最近来源目录
- `分析`、`图形`、`交付` 三页改成平行入口：
  - 页面优先消费当前主样本集已有数据
  - 缺少前置结果时，在页内给出中文缺口说明和“计算所需结果”入口
- `分析` 页当前只走正式公开对象 API：`calc_freqspec`、`calc_respspec`、`eval_zvl`、`eval_otovl`、`eval_fdmvl`、`eval_fpvdv`
- `分析` 页当前采用动作驱动请求模型：`ProcessingWorkspace` 只输出结构化处理请求，`ProcessingManager` 负责把公共参数与动作专属参数翻译成真实公开 API kwargs
- `图形` 页当前使用 `Matplotlib + FigureCanvasQTAgg + NavigationToolbar2QT`
  - 单样本模型优先走 `PlotDataset.from_model(...)`
  - 样本集表格优先走 `PlotDataset.from_dataframe(...)`
- `交付` 页当前只暴露轻交付入口：`scalar_frame`、`series_frame`、`peaks_frame` 与 `current_plot_image`
- `ExportManager` 内部仍可调用正式公开导出 API；GUI 页面首版不再把 `report_package` 作为主入口
- 会写回主样本集的 GUI 任务继续串行执行，避免并发改写同一主样本集；纯绘图预览与保存图片不参与主集写回串行链

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
