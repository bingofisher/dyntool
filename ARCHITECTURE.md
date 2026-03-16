# 架构说明

AdvDynTool 采用“稳定公开面 + 分层实现”的结构。

## 实现层

- `application`
- `domain`
- `compute`
- `infrastructure`

依赖方向：

- `application -> domain/compute`
- `domain -> compute`
- `infrastructure -> domain`
- `compute` 不反向依赖 `domain`

补充约束：

- `logging`、`plotting`、`storage`、`config`、`resources` 是正式模块入口，不再被视为实现层命名空间
- `dyntool.interfaces` 已移除，不再作为正式层存在

## 正式公开面

- 核心类 API：数据模型、元数据、样本、样本集
- 模块 API：`dyntool.storage`、`dyntool.plotting`、`dyntool.logging`、`dyntool.config`
- `DynTool` 仅保留 `resource` 与 `options`

## 文档与示例

- 正式文档栈统一为 `MkDocs + Material + mkdocstrings[python]`
- 示例正式结构统一为：
  - `examples/10_scenarios/`
  - `examples/90_recipes/`
- `plotting` 模块默认字体资源为内置 `SongTNR.ttf`，默认字体口径为 `SongTNR`

## 日志模块约束

- `dyntool.logging` 是唯一正式日志入口
- 默认 provider 为 `loguru`
- `loguru` 未安装时，默认配置自动回退到 `stdlib`，并记录一次 `WARNING` 日志
- 外部调用者通过 `configure_logging()` 或 `LoggingOptions` 设置 provider、等级、模式、路径和 provider 专属参数
- `get_logger()` 的公开契约保持 stdlib 风格，不向上泄露第三方 logger 类型
