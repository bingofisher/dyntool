# Codex 工作流与仓库级 Agents / Skills

稳定性：`Internal API`

## 这页解决什么问题？

这页说明 AdvDynTool 如何按官方目录在仓库内维护 Codex 资产：

- `AGENTS.md`
- `.codex/agents/`
- `.agents/skills/`

目标不是让所有任务都默认走多代理，而是把“什么时候不用子代理、什么时候优先多个 skill、什么时候必须先问用户”固化成可复用资产。

## 官方目录约定

- `AGENTS.md`
  - 负责仓库级总规则、前置确认事项、子代理启用策略和质量门禁。
- `.codex/agents/`
  - 负责项目级自定义子代理角色定义。
- `.agents/skills/`
  - 负责仓库级技能与流程模板。

## 固定角色

### 主控代理

- 负责任务拆分、边界判断、集成与最终决策。
- 公开 API、存储格式、单位语义、默认行为、兼容层删除等事项由主控代理先拦截。

### 影响分析代理

- 先做只读扫描。
- 输出改动清单、风险清单、文档联动、测试联动和质量门禁。

### 实现代理

- 按有界上下文分配写权限。
- 不按“功能点”或“任何相关文件”拆分。

### 测试代理

- 只负责 `tests/` 和夹具。
- 不顺手改生产代码。

### 文档同步代理

- 只负责 `README.md`、`ARCHITECTURE.md`、`docs/`、示例映射和 API 页入口。

### 验证代理

- 只跑门禁并汇总证据。
- 不写代码，不替实现代理做补丁。

### 审查代理

- 至少分成规格符合性审查和代码质量审查两类。

## 启用规则

- 简单任务：默认只由主代理完成。
- 稍微复杂任务：默认仍只由主代理完成，优先组合多个适用 skill。
- 十分复杂任务：只有在整个仓库重构、跨层联动或系统性大改时，才考虑启用子代理。

### 强制询问

- 只要判断“有必要使用子代理”，就必须先询问用户是否启用。
- 只有以下两种情形可以不先询问：
  - 用户已经明确指定要用子代理。
  - 用户明确在询问是否应该使用子代理或如何使用子代理。

## 串并行规则

### 可以并行

- 不同正式模块且写集合不重叠。
- 已经定语义后的代码改动与文档同步。
- 已经稳定接口草案后的代码改动与测试补充。

### 必须串行

- 公开 API 变化。
- 单位语义变化。
- 存储格式变化。
- 默认行为变化。
- README / ARCHITECTURE 正式口径变化。
- 涉及 `application` / `domain` / `compute` / `infrastructure` 分层边界的跨层重构。

## 自动校验

仓库级 Codex 资产必须至少通过：

```powershell
python scripts/check_codex_assets.py
python scripts/check_text_quality.py
python scripts/check_mkdocs_site.py
uv run mkdocs build --strict
```

`check_codex_assets.py` 负责检查：

- `.codex/agents/*.toml` 是否齐全且可解析。
- `.agents/skills/*/SKILL.md` 是否齐全。
- `.codex` 与 `.agents` 资产中是否残留旧公开面。
- `.gitignore` 是否错误忽略仓库级 `.codex/`。
- `AGENTS.md` 是否仍声明相关目录与门禁。
