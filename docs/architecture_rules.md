# 架构与规则

项目采用 `application -> domain/compute` 与 `infrastructure -> domain` 的分层约束。

## 核心规则

- `compute` 不反向依赖 `domain`
- 历史模块只允许删除或归档
- 正式公开面保持最小且稳定
- 文档、示例、测试和公开 API 说明必须同步
