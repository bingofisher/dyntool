# Skill 治理与主入口

稳定性：`Internal API`

本页是当前 Codex skill 体系的治理真源，统一回答 4 个问题：这个 skill 是做什么的、什么时候应该优先命中、什么时候不该用、是否建议长期保留。

## 安装源与基线

- 官方 system skill 目录：`C:\Users\Administrator\.codex\skills\.system\`
- 官方 runtime skill 目录：`C:\Users\Administrator\.codex\skills\codex-primary-runtime\`
- 全局自装 skill 目录：`C:\Users\Administrator\.agents\skills\`
- 仓库本地 skill 目录：`.agents/skills/`

当前基线快照日期：`2026-04-22`

- 官方 system skill：`05`
- 官方 runtime skill：`02`
- 全局自装 skill：`25`
- 仓库本地 skill：`03`
- 合计：`35`

说明：

- `Excel` 的实际目录名为 `spreadsheets`
- `PowerPoint` 的实际目录名为 `slides`
- 官方 skill 纳入边界治理，但不作为手动删除对象

## 主入口映射

| 类别 | 主入口 | 说明 |
| --- | --- | --- |
| skill 治理 | `using-superpowers` / `find-skills` / `writing-skills` | 分别负责总入口、发现安装、编写维护 |
| 规划执行 | `writing-plans` / `executing-plans` / `planning-with-files-zh` | 分别负责写计划、执行计划、文件化跟踪 |
| 设计治理 | `software-architecture` | 架构与方案讨论统一从这里进入 |
| 代码分析 | `repository-analyzer` / `lsp-code-analysis` | 分别负责仓库总览、语义级代码导航 |
| 实现质量 | `test-driven-development` / `systematic-debugging` / `verification-before-completion` / `requesting-code-review` | 分别负责开发、排障、完工验证、发起评审 |
| 图示可视化 | `drawio` | 统一作为本地可编辑图的主入口 |
| 仓库本地业务指导 | `advdyntool-usage-guide` | 只处理 AdvDynTool 在其他项目里的正式用法 |

## 固定分界

- `writing-skills` 负责 skill 设计、测试和长期维护；`skill-creator` 只作为官方脚手架备选。
- `software-architecture` 是设计主入口；`brainstorming` 只用于前期发散；`library-design-patterns` 只在明确做 Python 库模式设计时使用。
- `dispatching-parallel-agents` 负责独立子任务并行派发；`subagent-driven-development` 只在明确做大任务子代理协作时使用。
- `drawio` 负责离线可编辑图；`imagegen` 只处理位图图像，不接管结构图主入口。
- `repository-analyzer` 负责仓库全局理解；`lsp-code-analysis` 负责定义、引用和符号级导航。
- `writing-plans` 负责把需求收敛成实现计划；`planning-with-files-zh` 负责把计划、发现和进度落到文件。
- `receiving-code-review` 只处理“收到评审意见后怎么消化”；`requesting-code-review` 只处理“什么时候以及如何发起评审”。
- `building-qt-apps` 是 AdvDynTool 当前 PySide6 / Qt Widgets 开发主 skill；`pyside6-reviewer` 只负责 Qt 代码评审，不替代实现指导。
- 在 AdvDynTool 当前 GUI 里，默认异步模型是 `QThread + worker QObject + Signal`；`qasync` 和 `QtAsyncio` 只在明确引入 asyncio 主循环时再考虑。

## 边界表

### 官方 system skill

| skill 名称 | 来源 | 主要功能 | 主入口场景 | 不该使用的场景 | 相邻 skill 分界 | 保留建议 |
| --- | --- | --- | --- | --- | --- | --- |
| `imagegen` | 官方 | 生成或编辑位图图像 | 需要图片、贴图、位图原型、视觉稿 | 需要 `.drawio`、Mermaid、HTML 架构图 | 与 `drawio` 的分界是“结构图 vs 位图图像” | 保留 |
| `openai-docs` | 官方 | 查询 OpenAI 官方文档 | 需要 OpenAI 产品或 API 最新官方信息 | 普通 Python 库、仓库内部设计 | 与 `documenting-python-libraries` 的分界是“官方产品文档 vs 本地库文档” | 可选 |
| `plugin-creator` | 官方 | 创建 Codex plugin 骨架 | 需要新建或整理 Codex plugin | 编写 skill 或普通仓库功能 | 与 `skill-creator` 的分界是“plugin vs skill” | 可选 |
| `skill-creator` | 官方 | 快速搭 skill 基本结构 | 需要官方风格脚手架快速起步 | 需要测试驱动地编写和验证 skill | `writing-skills` 负责长期维护质量 | 可选 |
| `skill-installer` | 官方 | 安装或更新 skill | 需要把 skill 装到本机 | 只是查找 skill 或编写 skill | `find-skills` 负责发现，`writing-skills` 负责编写 | 保留 |

### 官方 runtime skill

| skill 名称 | 来源 | 主要功能 | 主入口场景 | 不该使用的场景 | 相邻 skill 分界 | 保留建议 |
| --- | --- | --- | --- | --- | --- | --- |
| `Excel` | 官方 runtime | 处理表格文件、公式、图表 | 需要读写或分析 `.xlsx` / `.csv` | 普通文档、代码或图示设计 | 与 `PowerPoint` 的分界是“表格 vs 幻灯片” | 保留 |
| `PowerPoint` | 官方 runtime | 处理幻灯片和演示文稿 | 需要制作或修改 `.pptx` | 表格、架构图源码、普通 Markdown 文档 | 与 `Excel` 的分界是“幻灯片 vs 表格” | 保留 |

### 全局自装 skill

| skill 名称 | 来源 | 主要功能 | 主入口场景 | 不该使用的场景 | 相邻 skill 分界 | 保留建议 |
| --- | --- | --- | --- | --- | --- | --- |
| `brainstorming` | 全局自装 | 做需求发散和前期思路整理 | 需求模糊、要先列方向和约束 | 设计已经收敛、要做决策完整方案 | `software-architecture` 负责收敛后的架构设计 | 可选 |
| `deep-learning-pytorch` | 全局自装 | 处理 PyTorch、Transformer、扩散和 LLM 开发 | 明确是深度学习或大模型任务 | 普通数值计算、库治理、GUI 设计 | 与 `scipy-best-practices` 的分界是“深度学习 vs 科学计算” | 可选 |
| `dispatching-parallel-agents` | 全局自装 | 把独立任务并行派发给子代理 | 多个低耦合子任务可并行 | 单线程小任务、强耦合实现链 | `subagent-driven-development` 负责重型协作开发 | 可选 |
| `documenting-python-libraries` | 全局自装 | 编写 Python 库文档和 docstring | 需要系统整理库文档 | 只是查 OpenAI 官方文档或做一般计划 | 与 `openai-docs` 的分界是“本地库文档 vs OpenAI 官方文档” | 可选 |
| `drawio` | 全局自装 | 生成和维护 `.drawio` 可编辑图 | 需要结构图、流程图、架构图、离线可编辑图 | 只要位图效果图或单纯 PPT | `imagegen` 负责位图，`PowerPoint` 负责幻灯片 | 保留 |
| `executing-plans` | 全局自装 | 按既有计划执行实施 | 已有明确计划，进入实施阶段 | 还没有决策完整计划 | `writing-plans` 负责写计划 | 保留 |
| `find-skills` | 全局自装 | 查找合适 skill 并判断是否安装 | 不确定该用哪个 skill | 已明确要执行具体任务 | `using-superpowers` 负责总入口协议 | 保留 |
| `finishing-a-development-branch` | 全局自装 | 处理开发分支收尾、集成和清理 | 实施完成，准备收尾 | 还在设计或编码中 | `verification-before-completion` 负责先验证，再收尾 | 保留 |
| `library-design-patterns` | 全局自装 | 处理 Python 库设计模式 | 明确在做库接口或分层模式设计 | 普通功能讨论或广义产品架构 | `software-architecture` 是通用设计主入口 | 可选 |
| `lsp-code-analysis` | 全局自装 | 做语义级代码导航与符号分析 | 需要查定义、引用、实现和重构影响 | 只要仓库总览或文档摘要 | `repository-analyzer` 负责总览，`lsp-code-analysis` 负责精读 | 保留 |
| `planning-with-files-zh` | 全局自装 | 用中文文件持续跟踪计划、发现和进度 | 长任务需要文件化沉淀 | 只需一轮简短计划 | `writing-plans` 负责生成计划本体 | 保留 |
| `pydantic` | 全局自装 | 处理 Pydantic 模型与校验 | 明确使用 Pydantic | 普通 dataclass、一般架构讨论 | `software-architecture` 负责框架无关设计 | 可选 |
| `receiving-code-review` | 全局自装 | 消化和判断收到的评审意见 | 需要回应 code review | 准备发起评审 | `requesting-code-review` 负责发起评审 | 保留 |
| `repository-analyzer` | 全局自装 | 快速建立仓库结构与技术认知 | 初次理解仓库、做高层分析 | 已知道目标文件，要做符号级定位 | `lsp-code-analysis` 负责符号级导航 | 保留 |
| `requesting-code-review` | 全局自装 | 发起结构化代码评审 | 实施完成，需要系统审查风险 | 收到意见后逐条处理 | `receiving-code-review` 负责后续消化 | 保留 |
| `scipy-best-practices` | 全局自装 | 处理 SciPy 科学计算与信号分析 | 明确是 SciPy 数值、信号、统计任务 | 深度学习、架构治理、文档工作 | `deep-learning-pytorch` 负责深度学习 | 可选 |
| `software-architecture` | 全局自装 | 做架构设计、模块边界和技术路线 | 设计主入口、方案收敛、接口边界讨论 | 只需发散灵感或只改一个局部 bug | `brainstorming` 负责发散，`library-design-patterns` 负责库模式细化 | 保留 |
| `subagent-driven-development` | 全局自装 | 用子代理协作执行较大实现任务 | 大任务、清晰拆分、允许多代理协作 | 小任务、纯探索或无需子代理 | `dispatching-parallel-agents` 更适合轻量并行 | 可选 |
| `systematic-debugging` | 全局自装 | 用系统方法定位和复现问题 | 出现 bug、失败、异常或不一致行为 | 纯新增功能实现 | `test-driven-development` 负责新功能开发路径 | 保留 |
| `test-driven-development` | 全局自装 | 先写测试再实现功能或修复 | 功能开发、缺陷修复、回归保护 | 只是做高层设计或文档整理 | `systematic-debugging` 负责定位问题根因 | 保留 |
| `using-git-worktrees` | 全局自装 | 建立隔离 worktree 和分支环境 | 新专题开发需要隔离 | 已处于稳定工作区且不需要隔离 | `finishing-a-development-branch` 负责收尾阶段 | 保留 |
| `using-superpowers` | 全局自装 | 统一 skill 使用入口和装配规则 | 会话开始、需要判断 skill 策略 | 已明确命中具体 skill | `find-skills` 负责补充发现 | 保留 |
| `verification-before-completion` | 全局自装 | 在宣称完成前执行完整验证 | 准备声称完成、提交、推送或切任务 | 仍在探索或尚未实现 | `finishing-a-development-branch` 负责验证后的收尾 | 保留 |
| `writing-plans` | 全局自装 | 把需求写成决策完整计划 | 任务复杂，需要先定方案 | 已有成熟计划、直接实施 | `executing-plans` 负责执行 | 保留 |
| `writing-skills` | 全局自装 | 用测试驱动方式编写与维护 skill | 需要长期维护 skill 质量 | 只想快速搭一个脚手架 | `skill-creator` 只提供快速起步骨架 | 保留 |

### 仓库本地 skill

| skill 名称 | 来源 | 主要功能 | 主入口场景 | 不该使用的场景 | 相邻 skill 分界 | 保留建议 |
| --- | --- | --- | --- | --- | --- | --- |
| `advdyntool-usage-guide` | 仓库本地 | 指导其他项目按当前 Public API 使用 AdvDynTool | 真实文件导入、sample / sample set、处理、评价、存储、绘图、日志、统计导出、报告包、资源查询 | 内部实现、历史入口、兼容层、维护者内部重构 | 仓库文档负责手册，`advdyntool-usage-guide` 负责面向 Codex 的正式用法路由 | 保留 |
| `building-qt-apps` | 仓库本地 | 指导当前项目的 PySide6 / Qt Widgets 桌面应用实现 | 编写 `src/dyntool_gui` 相关窗口、页面、信号槽、长任务交互和 `pytest-qt` 测试 | 把 `qasync` / `QML` / system tray 当作当前项目默认基线 | `pyside6-reviewer` 只负责评审，`building-qt-apps` 负责实现指导 | 保留 |
| `pyside6-reviewer` | 仓库本地 | 审查当前项目的 PySide6 / Qt 代码质量与线程安全 | 审查 `main_window`、`widgets`、`QThread`/worker、signals、布局、生命周期和 GUI 测试 | 把缺少 `QML` 或缺少 asyncio 主循环视为默认缺陷 | `building-qt-apps` 负责实现指导，`pyside6-reviewer` 负责评审约束 | 保留 |

## 已清理记录

| skill 名称 | 来源 | 清理日期 | 原因 |
| --- | --- | --- | --- |
| `netease-uu-booster` | 全局自装 | `2026-04-21` | 与当前开发和通用工程工作流无关，且不属于官方 skill |
