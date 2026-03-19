# 使用总览

稳定性：`Public API`

## 两层公开面

| 层级 | 入口 | 说明 |
| --- | --- | --- |
| 顶层对象层 | `AccelSeries`、`Metadata`、`Sample`、`SampleSet` | 负责构造与操纵核心对象 |
| 动作模块层 | `dyntool.storage`、`dyntool.plotting`、`dyntool.logging` | 负责存储、绘图、日志 |
| 支持模块层 | `dyntool.config`、`dyntool.resources` | 负责配置加载和内置资源读取 |

## 推荐操作流程

1. 先通过顶层对象 API 构造模型、元数据、样本或样本集。
2. 处理与评价使用对象方法或对象级闭环。
3. 读写走 `dyntool.storage`。
4. 绘图走 `dyntool.plotting`。
5. 日志走 `dyntool.logging`。
6. 标准资源和频带表走 `dyntool.resources`。
