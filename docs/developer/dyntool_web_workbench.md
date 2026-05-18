# Web 工作台实验线（冻结）

稳定性：`Internal API`

## 定位

`src/dyntool_web/` 是保留源码与可运行性的 Web 工作台实验线。它继续服务于后续产品化验证，但当前不再作为正式项目壳推进，不改变 `dyntool` 顶层对象 API、正式模块 API、存储格式或单位语义。

当前项目层正式口径固定为：

- GUI 是唯一正式项目壳
- Web 仅保留为 `Internal API` 实验线
- Web 保留现有测试和 smoke，用于验证浏览器/远程工作流设想，不承担当前主发布叙事

第一阶段采用本地 `FastAPI` 服务、可直接服务的静态页面和 `Vite + React + TypeScript` 前端源码：

- 不引入 Tauri。
- 不引入 Plotly、Bokeh 或其他交互式网页绘图库。
- 正式绘图继续使用 `Matplotlib + PlotDataset + PlotTheme`。
- Web 端只展示后端生成的 `SVG/PNG` 图像。

## 保留范围

本轮起，Web 工作台只保留以下内容：

- 现有四页结构
- 现有 FastAPI 路由与前端源码
- 现有测试与真实数据 smoke
- 当前可运行性

不在本线继续扩张新功能，不再与 GUI 对称推进。

## 页面合同

Web 工作台继续固定为四页：

- `总览`
- `导入与筛选`
- `数据处理`
- `图形绘制`

`SUBSET` 和 `EXPORT` 不恢复为独立主导航页面。子集是“导入与筛选”页内能力，导出是预检、工作区和任务能力。

## 内部服务边界

Web 服务入口：

```powershell
uv sync --group web
uv run python -B -m dyntool_web.server
```

核心内部接口包括：

- `GET /api/session`：当前项目、主集、能力快照和当前范围。
- `POST /api/project/open-path`：设置项目工作目录。
- `GET /api/fs/list`：列出后端允许根目录下的目录。
- `POST /api/import/preview`、`POST /api/import/bind`：导入预览和绑定。
- `POST /api/subsets/preview`、`POST /api/subsets/save`、`POST /api/scope/set`：子集预览、保存和范围切换。
- `GET /api/processing/actions`、`POST /api/processing/run`、`POST /api/processing/preview`：处理动作默认值、执行和结果预览。
- `GET /api/plot/theme`、`POST /api/plot/theme`、`POST /api/plot/render`、`POST /api/plot/save`：项目级 PlotTheme 编辑、渲染和保存。
- `POST /api/export/precheck`、`POST /api/export/run`：导出预检和导出任务。
- `WS /api/tasks/stream`：任务状态、进度、日志和问题推送。

这些接口全部属于 `dyntool_web` 内部协议，不进入 `dyntool` Public API。

## 绘图与主题

Web 图形页只负责配置、触发和展示正式图：

- 渲染由后端调用 `PlotDataset`、`PlotTheme` 和具体 Matplotlib plotter 完成。
- Web UI theme 只控制页面视觉，不控制正式图。
- `PlotTheme` 编辑器只修改正式图主题，并保存到项目级 TOML，例如 `<项目目录>/themes/gui_plot_theme.toml`。
- 修改后的主题必须能被 `PlotTheme.from_file(...)` 读取。

## 当前真实验证流程

当前 Web 工作台已经支持真实 `SET_SQLITE_H5` 仓库的主流程：

- `POST /api/import/preview` 使用 `inspect_storage_repository(..., level="quick")` 做轻量预览，并返回存储识别、样本数、metadata 模式、可用数据槽和问题列表。
- `POST /api/import/bind` 使用 `VibrationTestSampleSet.from_storage(..., load_mode=LAZY)` 绑定真实主样本集；`demo=True` 只作为内部测试/演示入口。
- 绑定主样本集会复用同路径轻量预览缓存，不再重复做完整预览；绑定后会推进会话 `primary_version` 并清空旧预览、旧图形和内存子集。
- 子集预览默认按当前页优先扫描，保存子集会写入 Web 会话内存态 `saved_subsets`，可通过 `saved_subset` 范围参与处理和预览；本阶段不写入项目持久化。
- `POST /api/processing/run` 可在真实主样本集或当前 UID 范围上执行 `calc_freqspec` 等处理动作。
- `POST /api/processing/preview` 和 `POST /api/plot/render` 会记录来源版本；当前范围或主题变化后，`GET /api/session` 会在 `last_preview.stale` 或 `last_plot.stale` 中提示旧结果已过期。
- `POST /api/plot/render` 继续只通过 Matplotlib 渲染正式 `SVG/PNG`。
- 任务面板使用统一任务记录，包含 `id / status / progress_percent / stage / cancelable / detail`；同步长操作也会先写入运行中任务，不可安全中止的阶段明确显示“暂不可中止”。
- 未知异常会写入问题列表并返回中文 `内部错误`，避免前端白屏或裸露内部 traceback。

## 1080P 工作台布局

当前 Web 前端以 `1920x1080` 和 `1366x768` 为主要验收尺寸：

- 顶栏、四页导航和底部任务区采用固定低高度布局，主工作区使用页内滚动，避免整页被表单撑高。
- 表格统一使用 sticky 表头、固定列宽、横向滚动和空态提示，不引入大型 grid 依赖。
- 任务区默认作为底部监控条，展开后浮层显示任务和问题详情，不持续挤压主表格或图形区。
- 导入与筛选页把导入链路、子集条件和命中表格分区展示；数据处理页和图形绘制页在执行前展示可执行性检查。

## 第一阶段限制

当前仍保留以下边界：

- 桌面原生目录选择器留到后续桌面集成阶段。
- 截图验收和完整按钮巡检应在 Web 前端稳定后再补 Playwright 流程。

## 质量与生成物治理

- Web 工作台验证必须覆盖 `src/dyntool_web`、`tests/test_dyntool_web*.py` 和 Web 真实数据 smoke，不应只运行库级 `src/dyntool` 门禁。
- 这些验证用于保证实验线未被误删或误破坏，不再代表与 GUI 对称的正式主线推进要求。
- 测试入口统一使用 `$env:PYTHONDONTWRITEBYTECODE='1'; uv run python -B -m pytest ...`，不要使用普通 `uv run pytest`。
- Web 前端源码产生的 `node_modules`、`*.tsbuildinfo` 和构建缓存不进入仓库；Python 测试生成物统一由 `scripts/clean_generated_artifacts.py --apply` 清理。
- 当前 Web 服务接口只作为 `Internal API` 验收，测试不得把路由字段或会话状态写成 `dyntool` Public API 合同。
