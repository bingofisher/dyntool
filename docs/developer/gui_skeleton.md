# GUI 骨架
稳定性：`Internal API`

本页描述 `src/dyntool_gui/` 当前骨架实现与现行标准之间的关系，避免把骨架代码误读为已经完整落地全部 GUI 蓝图。

## 当前骨架定位

- 当前 GUI 已建立 `PySide6 Widgets + QMainWindow + QDockWidget + QStackedWidget` 基本工作台
- GUI 是当前唯一正式项目壳；页面与交互收敛优先服务 `导入与筛选 / 数据处理 / 图形绘制 / 导出` 四条主链
- 当前骨架服务于 4 页主导航标准：`总览 / 导入与筛选 / 数据处理 / 图形绘制`
- `SUBSET / EXPORT` 不是正式主页面，即使内部仍保留兼容状态，也不应在导航语义上复活
- 当前骨架已具备真实导入、真实处理、真实 Matplotlib 绘图、轻量导出等主链能力
- 当前 4 页已统一接入页面头部组件，固定标题、副标题与当前摘要的展示层
- 当前骨架已接入 2K 横屏工作台密度：窄对象树、薄任务区、紧凑导航、横向低高度页头和中心表格/画布优先
- 当前工作台已收口主流程入口；仍需继续打磨页面细节与辅助交互
- 默认启动进入空项目会话；演示数据只通过显式参数 `--demo bridge` 或 `--demo generic` 进入

## 当前窗口结构

- 顶部：菜单栏与主导航相关壳层
- 左侧：对象树
- 中央：模块工作区
- 底部：任务 / 日志 / 问题 / 导出 / 审查

2K 横屏默认尺寸口径如下：

- 左侧对象树目标宽度 `170-180px`，最大不超过 `220px`
- 底部任务区目标高度 `96-112px`，默认只作为监控条和少量任务行
- 主导航按钮高度不超过 `30px`
- 页面头部最大高度 `64px`
- 导入控制带最大高度 `240px`
- 数据处理和图形绘制左侧配置栏最大宽度 `320px`
- 图形结果页签最大高度 `136px`

其中：

- `总览` 默认弱化对象树
- `导入与筛选` 是接入、检查、字段规则、数据预览、子集创建的唯一正式页面
- `数据处理` 和 `图形绘制` 是并列入口，不要求用户按固定向导顺序切页

## 当前已落地骨架

### 总览

- 能显示项目摘要、主样本集摘要、当前能力和近期记录摘要
- 仍偏“摘要页”，不承担复杂编辑

### 导入与筛选

- 已具备 Sample / SampleSet 接入入口
- 已具备轻量预览与显式深度检查动作
- 已具备筛选预览、子集保存与当前范围切换相关主链能力
- 仍需继续对齐 `2026-04-24-gui-import-filter-subset-contract.md` 的字段注册、规则树和数据预览合同

### 数据处理

- 已接入真实处理动作
- 已提供结构化参数区与结果预览区
- 仍需继续对齐方法分组、统一结果浏览器和 `BatchOperationStats` 映射

### 图形绘制

- 已接入真实 Matplotlib 画布
- 已支持显式渲染与图片保存
- 当前正式布局已收口为左侧配置、中央视图与底部结果页签，不再保留右侧 facts panel

## 当前未视为完成的区域

- 设置、帮助、导入预览、导出预检和审查结果入口已收口为真实容器
- 页面级工具栏、三层壳层和部分 Dock 行为仍在迭代中
- 导入与筛选页的结构化规则合同尚未完全收口
- 图形页的 Theme 配置仍未完整按正式 schema 暴露

## 与现行标准的关系

- 当前骨架必须服从 [gui_frontend_architecture.md](D:/BaiduSyncdisk/13_CodeRepository/Projects/AdvDynTool/docs/developer/gui_frontend_architecture.md)
- 详细合同以 `docs/superpowers/specs/2026-04-24-*` 为准
- 若骨架实现与这些文档冲突，应优先修正文档口径是否过期，再判断是否改代码

## 评审使用规则

- 评审骨架代码时，先确认引用的是当前有效 4 页标准，而不是历史 6 页口径
- 评审入口完成度时，应优先区分“真实主流程容器”与“仅内部保留的说明型入口”
- 对布局问题的判断应优先核对 `2026-04-24` 规格中的正式结构，而不是历史视觉探索稿

## 质量与生成物治理

- GUI 相关验证必须覆盖 `src/dyntool_gui`、`tests/test_gui_*.py` 和截图/审计脚本，不应只运行库级 `src/dyntool` 门禁。
- 测试入口统一使用 `$env:PYTHONDONTWRITEBYTECODE='1'; uv run python -B -m pytest ...`，不要使用普通 `uv run pytest`。
- 运行 pytest 前先确保 `.pytest_tmp` 存在；运行后必须执行 `uv run python -B scripts/clean_generated_artifacts.py --apply`，再确认仓库内没有 `__pycache__`、`.pytest_cache`、`.ruff_cache`、`site` 或 `docs/_build`。
- `scripts/audit_gui_workflow.py` 与 `scripts/capture_gui_screenshot.py` 属于 GUI 内部审计工具，输出默认落入 `.pytest_tmp`，不进入正式交付物。
