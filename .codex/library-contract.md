# AdvDynTool 库约定

## 主入口
```python
from dyntool import AccelSeries, Metadata, DefaultSample, DefaultSampleSet
import dyntool.storage as dt_storage
import dyntool.plotting as dt_plotting
import dyntool.logging as dt_logging
import dyntool.reporting as dt_reporting
import dyntool.config as dt_config
import dyntool.resources as dt_resources
```

## 正式支持模块
- `dyntool.storage`
- `dyntool.plotting`
- `dyntool.logging`
- `dyntool.reporting`
- `dyntool.config`
- `dyntool.resources`

## 正式公开面规则
- 顶层公开面以对象 API 为主，不暴露内部层级路径。
- 模块公开面以正式模块 API 为主，不把 `domain`、`application`、`compute`、`infrastructure` 直接包装成正式用户入口。
- 公开 API、存储格式、单位语义、默认行为和兼容层删除都必须先由主控代理触发用户确认。

## 任务路由
- 公开面、分层边界和命名口径相关任务优先命中 `advdyntool-task-routing` 与 `software-architecture`。
- 面向其他项目的公共用法问题优先命中 `advdyntool-usage-guide`。
- 文档联动任务优先命中 `advdyntool-doc-sync`。
- 影响分析优先命中 `advdyntool-impact-analysis`。
- 质量门禁收口优先命中 `advdyntool-quality-gates`。

## 枚举优先
公开策略控制优先使用真实 `Enum` / `StrEnum`，保持公开接口可发现、可验证、可文档化。
