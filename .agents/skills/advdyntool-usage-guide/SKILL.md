---
name: advdyntool-usage-guide
description: Use when users ask how to use AdvDynTool or `dyntool` in another project, including real-file import, sample or sample-set workflows, processing or evaluation, storage, plotting, logging, statistics export, report-package export, or built-in resources. Use when the answer must stay on the current Public API, official docs, and official examples.
---

# AdvDynTool 公共使用指导

为在其他项目中调用 AdvDynTool 的使用者提供快速、准确、可落地的正式用法指导。回答始终绑定当前仓库的正式公开面、正式文档和正式示例，不把内部实现、兼容层或历史路径包装成当前推荐用法。

## 强规则

- 只推荐 `Public API`
- 事实源优先级固定为：
  1. `src/dyntool/__init__.py` 与正式模块 `__all__`
  2. `docs/api/public_api.md`
  3. `docs/examples_manifest.toml`
  4. `docs/workflow_guide.md`
  5. `docs/examples_overview.md`
- 若 `usage-map.md` 与以上事实源冲突，以事实源为准
- 遇到兼容层、旧路径或内部模块导入问题时，直接改写成当前正式替代路径
- 不推荐内部模块路径、历史入口、未在正式公开面中出现的符号

## 回答协议

每次回答都按这个顺序组织：

1. 识别任务类型
2. 选择正式入口
3. 给最短可运行骨架
4. 给 `doc / script / test` 锚点
5. 必要时纠偏旧入口或越界导入

默认输出形态：

- 先用一句话说明当前正式主链
- 再给一个最短 Python 代码块
- 最后只附最相关的 `doc / script / test`

除非用户明确要求，不一次性展开多个互相竞争的入口。

## 示例选择规则

- 默认优先 `kind="scenario"` 且 `featured=true`
- `logged_run` 与 `resource_driven_eval` 虽然不是 featured，但属于正式 scenario，可直接命中
- 只有用户需要更细颗粒度补充时，才降级到 `recipe`
- `kind="internal"` 默认不推荐；只有用户明确要求 `Internal API`、自定义扩展或维护者视角时，才允许引用 `custom_extension`

## 任务快速路由

| 任务 | 正式入口 | 优先 example id |
| --- | --- | --- |
| 真实文件导入 | `AccelSeries.from_csv(...)`、`DefaultSampleSet.save(...)`、`DefaultSampleSet.from_storage(...)` | `import_and_normalize` |
| 最小闭环 | `DefaultSample.from_accel_data(...)`、`DefaultSample.eval_*`、`DefaultSampleSet.from_storage(...)` | `store_and_reload` |
| sample / sample set | `DefaultSample`、`DefaultSampleSet` | `build_and_manage_samples` |
| processing / evaluation | `model.compute`、`sample.compute`、`sample_set.compute` | `evaluate_vibration` |
| storage 检测与 scheme 选择 | `dyntool.storage`、对象级 `save(...)` / `from_storage(...)` | `store_and_reload`、`storage_scheme_selection` |
| plotting | `dyntool.plotting` | `plot_and_export`、`plot_dataset_and_plotters` |
| logging | `dyntool.logging.configure_logging(...)`、`dyntool.logging.get_logger(...)` | `logged_run`、`logging_providers_and_modes` |
| statistics export | `sample_set.export_scalar_frame(...)` 等对象级导出入口，必要时补 `dyntool.reporting` | `statistics_export` |
| report package | `sample_set.export_report_package(...)`，必要时补 `dyntool.reporting.export_report_package(...)` | `report_package_export` |
| resources | `dyntool.resources` | `resource_driven_eval` |

## 最短骨架要求

- 只用正式公开导入
- 优先最短闭环，不给大而全模板
- 保留关键参数名，让用户知道该填什么
- 除非问题本身要求，不引入内部模块、复杂扩展点或非正式入口
- plotting 统一走 `PlotDataset -> PlotTheme -> concrete plotter -> PlotResult.ax`

如果用户只问“该走哪个入口”，也要给 3 到 8 行最小骨架，而不是只丢路径。

## 常见纠偏

- 用户想直接从内部模块导入类型：改为顶层对象 API 或正式模块 API
- 用户追问旧中文绘图配置入口或旧 plotting 助手：改回 `PlotDataset`、`PlotTheme`、具体 plotter、`PlotResult.ax`
- 用户把存储内部字段名当正式参数：改回 `dyntool.storage` 契约与对象级读写入口
- 用户把底层计算函数当主入口：优先改回 `model.compute`、`sample.compute`、`sample_set.compute`
- 用户要求示例：优先给正式 scenario；需要更细颗粒度时再补 recipe

## 参考加载

默认先读：

- `src/dyntool/__init__.py`
- `docs/api/public_api.md`
- `docs/examples_manifest.toml`

按任务再读：

- 导入与单位：`docs/usage/01_input_and_types.md`
- 样本与样本集：`docs/usage/02_samples_and_sets.md`
- 处理与评价：`docs/usage/03_processing_and_results.md`
- 存储：`docs/usage/04_storage_rules.md`
- plotting / logging / resources：`docs/usage/05_plotting_logging_resources.md`
- 教程顺序：`docs/workflow_guide.md`
- 示例总览：`docs/examples_overview.md`

高频任务的正式入口、example id、文档、脚本和测试锚点见 [usage-map.md](references/usage-map.md)。

## 维护回归

修改这个 skill 或其引用资料后，按 [regression-checklist.md](references/regression-checklist.md) 回归：

- 主场景是否命中正确正式入口
- 边界问题是否被纠偏到当前主链
- 无关问题是否不会误触发
