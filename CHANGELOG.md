# 更新日志

稳定性：`Public API`

## Unreleased

### Web 工作台实验线（冻结）
稳定性：`Internal API`

- `src/dyntool_web/` 继续保留源码、测试、构建包与依赖组，但项目定位降级为实验线，不再作为当前正式项目壳。
- Web 继续采用本地 `FastAPI` 服务、静态页面和 `Vite + React + TypeScript` 前端源码，固定四页工作台，不引入 Tauri，不引入 Plotly。
- 正式绘图继续走 `Matplotlib + PlotDataset + PlotTheme`，Web 端仅展示后端生成的 `SVG/PNG`，并提供项目级 PlotTheme 编辑入口。
- 新增 Web 内部接口覆盖会话摘要、项目路径、导入 demo 绑定、处理动作默认参数、绘图渲染、导出预检和任务状态快照。
- Web 导入接口扩展为真实 `SET_SQLITE_H5` 仓库轻量预览与绑定，支持真实主集上执行 `calc_freqspec`、生成结果预览、渲染 Matplotlib SVG 和导出预检；`demo=True` 仅保留为内部测试/演示入口。
- Web 前端导入页补齐路径输入、目录浏览、轻量预览、绑定主样本集、子集范围和底部任务/问题反馈。
- Web 工作台补齐会话版本、预览/图形过期标记、内存子集保存、`saved_subset` 范围、分页优先子集预览、未知异常中文问题反馈和 1080P 工作台布局合同。
- Web 前端升级通用表格、折叠任务面板、子集筛选控件、数据处理执行前检查和图形绘制前检查；Vite 构建会清理旧静态资源，避免浏览器加载历史 hash 资产。

### GUI 工作台全面收口

稳定性：`Internal API`

- GUI 当前正式主导航固定为 `总览 / 导入与筛选 / 数据处理 / 图形绘制`；`SUBSET / EXPORT` 继续只作为内部状态或工作区能力，不恢复独立主页面
- 图形绘制页移除右侧 facts panel，固定为 `左侧配置 + 中央画布/结果 + 底部结果页签`
- 设置、帮助、导入预览、导出预检、代码审查结果等入口改为真实对话框或真实只读容器，不再作为主流程占位弹窗
- 新增 GUI 按钮矩阵、前端架构、视觉参考和生图 prompt 开发者文档，明确按钮类型、触发条件、失败反馈和 4 页工作台标准
- 新增 1080P / 2K 横屏布局密度规则，收紧对象树、底部任务区、页面头部、导航按钮和页面 splitter 尺寸
- 新增 `ThemeManager + ThemeTokens` 视觉出口、页面头部、状态标签、摘要卡片、空态容器和按钮层级的统一口径
- 导入主链增加后台进度、取消反馈、轻量预览缓存复用和真实数据 GUI 审计脚本，避免轻量预览后绑定主集再次全量跑
- 数据处理页接入 `ProcessingManager`，执行分析后刷新主集摘要和能力快照，导出预检可识别刚生成的 `freqspec` 等结果
- 图形页接入 Matplotlib 画布与字体配置，解决中文截图缺字方框问题，并提供内部截图/审计入口
- 新增 GUI 项目持久化、设置持久化、资源树/底部任务区 model-view 化、真实数据集成测试和窗口拉伸/对话框拉伸结构测试
- 本轮不新增 `dyntool` Public API，不修改存储格式，不修改单位语义

## v1.2.2 - 2026-05-18

### 版本线定位

- `v1.2.2` 已作为当前 `1.2.x` 稳定基线正式发布
- `main` 当前承接 `v1.2.2` 发布后的稳定主线
- 前一稳定版本为 `v1.2.1`
- 正式发布事实以对应 `v1.2.2` git tag 为准

## v1.2.1 - 2026-04-21

### 版本线定位

- `v1.2.0` 已作为当前 `1.2.x` 稳定线基线发布
- `v1.2.1` 已作为当前 `1.2.x` 稳定基线正式发布
- 本次正式发布聚焦 plotting 补丁修复、公开配置补齐和工程治理升级
- 前一稳定版本为 `v1.2.0`
- 正式发布事实以对应 `v1.2.1` git tag 为准

### plotting 公开配置补齐

- `PlotTheme` 正式补齐 `grid.x.major / grid.x.minor / grid.y.major / grid.y.minor`
- `axis.x / axis.y` 连续轴配置补齐 `major_step`、`minor_step`、`scientific_*`
- `axis.x.label / axis.y.label` 正式纳入模板 schema
- `OneThirdOctavePlotter` 正式支持 `axis.y = ContinuousAxisSpec`
- `SongTNR` 全局字体快捷入口与主题应用链统一到正式 plotting 主链

### reporting / storage / logging 内部聚合

- `reporting` 内部实现改为 facade + builders / export / writers 结构
- sample-set storage 的重复摘要逻辑收敛为共享私有模块
- logging provider 的运行时状态收进私有 runtime，公开 API 不变

### 仓库治理与文档收口

- 新增仓库治理检查与 helper 结构检查，统一命令口径、正式 schema 口径和内部 helper 反模式治理
- 补齐仓库级 usage guide skill 与相关校验
- 文档、示例、public API baseline、typing 与回归测试同步对齐当前正式口径

## v1.2.0 - 2026-04-18

- plotting 正式主链固定为 `PlotDataset -> PlotTheme -> concrete plotter -> PlotResult.ax`
- `dyntool.reporting` 正式纳入公开面
- storage / runtime 内部边界进一步收紧
- domain helper 结构继续收口，但不改变正式对象 API

## v1.1.2 - 2026-04-04

- 完成 `SET_SQLITE_H5` v2 正式化、样本集主链收口
- 同步测试、baseline、性能基线与仓库门禁

## v1.1.1 - 2026-03-30

- 公开口径回正，统一 `DefaultSample / DefaultSampleSet`
- 补齐 storage 主链说明与文档规则修正

## v1.1.0 - 2026-03-19

- 完成公开面重整
- 资源模块统一到 `dyntool.resources`
- plotting 固定为 `matplotlib` 静态绘图路径
