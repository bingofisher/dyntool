# AdvDynTool 文档同步

代码语义一旦确定，负责把变更同步到 README、ARCHITECTURE、MkDocs 页面、示例映射与 API 页入口。

## 规则
- 不决定语义，只同步已确认事实。
- 公开 API 变化必须同时同步 docstring、MkDocs API 页入口、至少一个示例和至少一个测试覆盖点。
- 涉及迁移路径或默认行为口径变化时，必须提醒主控代理先确认是否需要问用户。
