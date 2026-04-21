# GUI 骨架首轮落地

稳定性：`Internal API`

本页记录 `src/dyntool_gui/` 首轮骨架的目标、边界和模块组织。

## 范围

- 只落 `PySide6` 桌面骨架
- 只固定信息架构、模块页、dock 分区、按钮归属和子窗口壳
- 只使用内存假数据驱动界面
- 不接真实导入、处理、绘图、工程导出链

## 包结构

```text
src/dyntool_gui/
  app.py
  main_window.py
  session.py
  facades.py
  models/
  widgets/
```

## 主窗口结构

- 顶部：菜单栏 + 主工具栏
- 左侧：项目资源树
- 中央：模块工作区
- 右侧：信息区
- 底部：任务 / 日志 / 问题 / 导出 / 审查
- 状态栏：工作目录、主 SampleSet、脏状态、任务状态

## 固定模块

- `项目`
  - 项目本体摘要
  - 主 SampleSet 摘要
  - metadata 字段与 categories 入口
- `导入`
  - `导入 Sample`
  - `导入 SampleSet`
  - 参数、预览、单位检测、hook 区都先占位
- `处理`
  - 子集构建器
  - 处理入口
  - 结果预览与结果导出准备
- `绘图`
  - 图任务树
  - 统一预览区
  - 统一图参数区
- `工程导出`
  - 导出任务
  - 内容编排
  - 输出与预检

## 动作路由

- 页面内按钮统一通过 `ModuleWorkspace.action_requested` 上送
- 主窗口统一分发动作
- 首轮动作固定分三类：
  - 直接生效：模块切换、dock 显隐、恢复布局、切换假数据
  - 打开子窗口：导入预览、长任务进度、大图预览、导出预检、日志详窗、代码审查结果、结果预览
  - 明确提示未接入：真实导入、真实处理、真实绘图、真实工程导出

## 子窗口

- `ImportPreviewDialog`
- `LongTaskProgressDialog`
- `FigurePreviewDialog`
- `ExportPrecheckDialog`
- `LogDetailDialog`
- `CodeReviewResultDialog`
- `ResultPreviewDialog`

## 会话模型

`ProjectSession` 只承载骨架阶段状态：

- 项目名、工作目录、默认导出目录
- 主 / 对比 / 附属 SampleSet 摘要
- 当前模块、当前选中对象、脏状态
- 任务、日志、导出记录、审查记录
- 绘图任务树

## 启动方式

```powershell
uv sync --group gui
uv run python -B -m dyntool_gui.app
```

临时运行也可以使用：

```powershell
uv run --with PySide6 python -B -m dyntool_gui.app
```

## 第二轮接入边界

- `ProjectSession` 对接真实项目摘要和 `sampleset` 摘要
- 导入模块对接 `Sample / SampleSet` 双路径
- 处理模块对接子集、结果表和导出准备
- 绘图模块对接 Matplotlib 真实预览与导出
- 工程导出模块对接 reporting 与图组导出
