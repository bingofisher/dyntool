# AdvDynTool 项目上下文

## 目标
- 提供可复用的动力学计算与振动评价 Python 库。
- 优先保证数值结果正确、单位一致、结果可追溯。
- 保持对象关系、公开 API 和正式文档口径稳定清晰。

## 当前正式公开面
- 顶层对象 API：`AccelSeries`、`Metadata`、`Sample`、`SampleSet` 等核心对象。
- 正式模块 API：`dyntool.storage`、`dyntool.plotting`、`dyntool.logging`、`dyntool.config`、`dyntool.resource`。
- 不再保留旧顶层入口，也不恢复任何历史入口。

## 当前实现层
- `application`
- `domain`
- `compute`
- `infrastructure`

## 仓库级工作方式
- 简单任务默认由主代理直接完成。
- 稍微复杂任务默认仍由主代理完成，优先组合多个适用 skill。
- 十分复杂任务或整个仓库重构，才考虑启用子代理。
- 只要判断有必要启用子代理，必须先问用户是否启用。

## 固定角色
- 主控代理：任务拆分、边界判断、集成与最终决策。
- 影响分析代理：先做只读影响分析。
- 实现代理：按有界上下文分配写权限。
- 测试代理：只改测试。
- 文档同步代理：只改 README、ARCHITECTURE、`docs/`。
- 验证代理：只跑门禁并汇总证据。
- 审查代理：规格审查与代码质量审查分离。

## 质量门禁
- `python scripts/check_codex_assets.py`
- `python scripts/check_layer_imports.py`
- `python scripts/check_text_quality.py`
- `python scripts/check_docstring_coverage.py`
- `python scripts/check_public_api_baseline.py`
- `python scripts/check_mkdocs_site.py`
- `uv run mkdocs build --strict`
- `pyright src/dyntool tests/typing_public_api.py`
- `pytest -q`
