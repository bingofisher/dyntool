# 使用总览

稳定性：`Public API`

## 如何使用本站

本站按“先掌握正式对象，再进入完整场景，最后查局部 recipe 和 API”的顺序组织：

- `入门与使用`：讲正式公开类型、枚举、参数契约和最小代码
- `教程`：讲完整闭环场景，优先对应 `examples/10_scenarios`
- `参考与附录`：讲示例附录、公开 API、内部说明和开发者文档

## 你最先需要知道的正式入口

| 分类 | 推荐入口 | 用途 |
| --- | --- | --- |
| 数据模型 | `AccelSeries`、`VelSeries`、`FreqSpec` | 表示时程、频谱和计算结果 |
| 元数据 | `Metadata`、`VibrationTestMetadata` | 生成 UID，组织身份与属性 |
| 样本 | `Sample`、`SampleSet` | 把模型、元数据和批量操作组织到一起 |
| 存储 | `dyntool.storage` | 保存和加载模型、样本、样本集 |
| 绘图 | `dyntool.plotting` | 按 plotter-first 方式绘制模型、样本或 payload |
| 资源 | `DynTool().resource` | 读取标准资源、中心频率和资源表 |

## 场景主线与 Recipes 的关系

- `examples/10_scenarios/` 是主线场景，从导入、建样本、评价、存储、绘图、日志到资源驱动评价一路贯通
- `examples/90_recipes/` 是技巧附录，用来补某个局部问题，例如单位视图、元数据模式、样本集筛选并行 I/O、存储方案选择
- 阅读顺序建议：先看主题页和场景页，再根据问题回到 recipes

## 先读哪几页

- 只想先把对象建起来：[`docs/usage/01_input_and_types.md`](usage/01_input_and_types.md)
- 想组织样本和样本集：[`docs/usage/02_samples_and_sets.md`](usage/02_samples_and_sets.md)
- 想处理、评价并理解结果对象：[`docs/usage/03_processing_and_results.md`](usage/03_processing_and_results.md)
- 想确认 H5、目录导出、严格模式和并发参数：[`docs/usage/04_storage_rules.md`](usage/04_storage_rules.md)
- 想查完整场景入口：[`docs/examples_overview.md`](examples_overview.md)

## 不推荐的阅读方式

??? warning "不要从自动 API 页开始读"
    自动 API 参考适合查完整签名和 docstring，不适合作为第一次理解项目的入口。

??? warning "不要把 recipes 当成主学习路径"
    recipes 解决的是局部问题。第一次接入时，应优先看主题页和 `10_scenarios` 场景示例。

??? warning "不要把旧 examples 目录名当成当前事实来源"
    当前正式示例结构就是 `examples/10_scenarios` 和 `examples/90_recipes`。如果文档或本地笔记仍写旧目录，应以这两个目录为准。
