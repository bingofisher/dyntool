# AdvDynTool

AdvDynTool 是面向动力学计算、振动处理与结果评价的 Python 工具库，强调数值结果正确性、单位一致性和结果可追溯性。

## 正式公开面

- 类 API：`AccelSeries`、`Metadata`、`Sample`、`SampleSet`
- 模块 API：`dyntool.plotting`、`dyntool.logging`、`dyntool.storage`、`dyntool.config`
- `DynTool` 只保留：`resource`、`options`

日志模块当前支持：

- 默认 `loguru` provider
- 未安装 `loguru` 时自动回退到 `stdlib`，并记录一次警告日志
- 通过 `configure_logging()` 或 `LoggingOptions` 统一设置 provider、等级、模式与输出位置

## Windows 快速开始

```powershell
uv sync --group dev --group docs
uv run mkdocs serve
uv run pytest -q
```

常用本地命令：

- `uv run mkdocs serve`
- `uv run mkdocs build --strict`
- `uv run ruff check src/dyntool tests examples scripts`
- `uv run pyright src/dyntool tests/typing_public_api.py`
- `uv run pytest -q`

## 文档入口

- 文档首页：`docs/index.md`
- 使用总览：`docs/user_guide.md`
- 示例索引：`docs/examples_overview.md`
- API 与附录：`docs/api/index.md`
- 架构说明：`ARCHITECTURE.md`

## 示例结构

- 场景主线：`examples/10_scenarios/`
- Recipes：`examples/90_recipes/`
- 真实输入夹具：`examples/input_data/`

推荐阅读顺序：

1. `docs/user_guide.md`
2. `docs/usage/01_input_and_types.md`
3. `docs/usage/04_storage_rules.md`
4. `docs/examples_overview.md`

## 质量门禁

- `uv run ruff check src/dyntool tests examples scripts`
- `uv run ruff format --check src/dyntool tests examples scripts`
- `uv run python scripts/check_layer_imports.py`
- `uv run python scripts/check_public_api_baseline.py`
- `uv run python scripts/check_text_quality.py`
- `uv run python scripts/check_docstring_coverage.py`
- `uv run python scripts/check_mkdocs_site.py`
- `uv run mkdocs build --strict`
- `uv run pyright src/dyntool tests/typing_public_api.py`
- `uv run pytest -q`
