# `v1.2.2` 发布检查清单

稳定性：`Internal API`

## 适用范围

本清单用于 `v1.2.2` 版本的最终收口、发布与发布后回写校验。

默认规则：

- 主目录 `AdvDynTool` 默认对应 `main`；本轮整合来源允许先在 `codex/gui-skeleton` 上完成后合回 `main`
- `codex/gui-skeleton` 只处理 `v1.2.2` 的整合、文档同步、治理收口和项目环境整理
- `v1.2.2` tag 只能打在通过合并后审查的稳定提交上

## 一、版本线确认

- [ ] 当前工作目录是主目录 `AdvDynTool`
- [ ] 当前分支是 `main` 或 `codex/gui-skeleton`
- [ ] `src/dyntool/_version.py` 已与目标发布版本一致
- [ ] 当前补丁不引入未经确认的公开 API、存储格式、单位语义或默认行为变化

## 二、文档与材料

- [ ] `README.md` 已说明当前为 `1.2.x` 稳定线，发布目标为 `v1.2.2`
- [ ] `CHANGELOG.md` 已包含 `v1.2.2` 条目
- [ ] `docs/reference/changelog.md` 已同步补丁摘要
- [ ] `docs/developer/version_lines.md` 已反映当前版本线规则
- [ ] `docs/api/public_api.md` 与 `docs/api/internal_api.md` 仍与当前代码一致

## 三、功能与边界检查

- [ ] plotting 正式公开面与当前代码一致
- [ ] reporting 正式公开面与对象薄委托一致
- [ ] `dyntool.storage` 顶层门面与 runtime/internal 边界一致
- [ ] 新增治理规则与当前仓库口径一致，不引入自相矛盾条目

## 四、质量门禁

发布前必须通过 AGENTS 第 9 节全量门禁：

- [ ] `uv run python -B scripts/check_codex_assets.py`
- [ ] `uv run ruff check --no-cache src/dyntool tests examples`
- [ ] `uv run ruff format --check src/dyntool tests examples`
- [ ] `uv run python -B scripts/check_layer_imports.py`
- [ ] `uv run python -B scripts/check_text_quality.py`
- [ ] `uv run python -B scripts/check_docstring_coverage.py`
- [ ] `uv run python -B scripts/check_public_api_baseline.py`
- [ ] `uv run python -B scripts/check_resource_consistency.py`
- [ ] `uv run python -B scripts/check_mkdocs_site.py`
- [ ] `uv run python -B scripts/check_repository_governance.py`
- [ ] `uv run python -B scripts/check_helper_structure.py`
- [ ] `$env:PYTHONDONTWRITEBYTECODE='1'; uv run python -B -m mkdocs build --strict --site-dir .pytest_tmp/mkdocs-site`
- [ ] `uv run pyright src/dyntool tests/typing_public_api.py`
- [ ] `$env:PYTHONDONTWRITEBYTECODE='1'; uv run python -B -m pytest -q --basetemp .pytest_tmp/pytest -p no:cacheprovider`

## 五、tag 与发布后动作

- [ ] 已完成补丁提交与合并后审查
- [ ] 已准备在稳定提交上创建 `v1.2.2` tag
- [ ] 发布后已同步回写 `main` 的版本线与 changelog 事实
- [ ] 如仍存在后续问题，下一补丁目标进入下一稳定补丁版本
