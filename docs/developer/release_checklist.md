# `v1.2.2` 发布检查清单

稳定性：`Internal API`

## 适用范围

本清单用于 `v1.2.2` 版本线的最终收口、发布与发布后回写校验。

默认规则：

- 主目录 `AdvDynTool` 对应正式主线 `main`
- `v1.2.2` tag 只能打在通过审查和门禁的稳定提交上
- GitHub branch ruleset 名称固定为 `Protect main`
- GitHub tag ruleset 名称固定为 `Protect release tags`
- CI workflow 名称固定为 `CI`
- CI 主 job 名称固定为 `quality`

## 一、版本线确认

- [ ] 当前工作目录是主目录 `AdvDynTool`
- [ ] 当前收口目标是 `main` 上的 `v1.2.2` 稳定线
- [ ] `src/dyntool/_version.py` 与目标发布版本一致
- [ ] 当前补丁不引入未确认的公开 API、存储格式、单位语义或默认行为变化

## 二、文档与材料

- [ ] `README.md` 已说明当前为 `1.2.x` 稳定线，正式发布版本为 `v1.2.2`
- [ ] `CHANGELOG.md` 已包含 `v1.2.2` 条目
- [ ] `docs/reference/changelog.md` 已同步摘要
- [ ] `docs/developer/version_lines.md` 已反映当前版本线规则
- [ ] 相关开发者治理文档与当前仓库事实一致

## 三、功能与边界检查

- [ ] plotting 正式公开面与当前代码一致
- [ ] reporting 正式公开面与当前实现一致
- [ ] `dyntool.storage` 顶层门面与内部边界一致
- [ ] 新增治理规则与当前仓库口径一致，不引入自相矛盾条目

## 四、质量门禁

发布前至少通过以下门禁：

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

## 五、Tag 与发布后动作

- [ ] 已完成补丁提交、PR 审查与正式合并
- [ ] 已在稳定提交上创建 `v1.2.2` tag
- [ ] GitHub `Protect main` 与 `Protect release tags` 已按当前版本线配置
- [ ] `CI / quality` 已恢复并通过
- [ ] 若已进入 phase 2，`quality` 已配置为 `main` 合并前 required check
- [ ] 发布后已同步回写 `main` 的版本线与 changelog 事实
- [ ] 若仍存在后续问题，已明确下一补丁版本目标
