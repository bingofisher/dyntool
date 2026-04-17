# `v1.2.0` 发布检查清单

稳定性：`Internal API`

## 适用范围

本清单用于 `v1.2.0` 版本线的 RC 收口、正式发布和后续补丁发布。

默认规则：

- 主目录 `AdvDynTool` 只对应 `main`
- `.worktrees/v1.2.0` 只对应 `codex/v1.2.0`
- `v1.2.0` 的 breaking 改动只能在对应 worktree 中完成

## 一、版本线确认

- [ ] 当前工作目录是 `.worktrees/v1.2.0`
- [ ] 当前分支是 `codex/v1.2.0`
- [ ] 主目录 `main` 未承接 `v1.2.0` breaking 改动
- [ ] `src/dyntool/_version.py` 已与目标发布版本一致

## 二、文档与迁移材料

- [ ] `README.md` 已说明当前是 `v1.2.0` breaking / RC 版本线
- [ ] `ARCHITECTURE.md` 已对齐当前代码事实
- [ ] `CHANGELOG.md` 已补齐 `v1.2.0` 条目
- [ ] `docs/developer/migration_1_2_0.md` 已覆盖迁移说明
- [ ] `docs/developer/version_lines.md` 已反映当前版本线规则
- [ ] `docs/api/public_api.md` 与 `docs/api/internal_api.md` 已对齐

## 三、功能与边界检查

- [ ] plotting 正式公开面与当前代码一致
- [ ] reporting 正式公开面与对象薄委托一致
- [ ] `dyntool.storage` 顶层门面与 runtime/internal 边界一致
- [ ] 未引入未批准的公开 API 变化
- [ ] 未引入未批准的默认行为变化
- [ ] 未改变存储格式、单位语义或数值结果定义

## 四、示例与类型证明

- [ ] 至少一个 plotting 正式示例可运行
- [ ] 统计导出示例可运行
- [ ] 报告包导出示例可运行
- [ ] `tests/typing_public_api.py` 已覆盖新增正式公开面
- [ ] public API baseline 已对齐

## 五、质量门禁

发布前必须通过 AGENTS 第 9 节全量门禁：

- [ ] `python -B scripts/check_codex_assets.py`
- [ ] `ruff check --no-cache src/dyntool tests examples`
- [ ] `ruff format --check src/dyntool tests examples`
- [ ] `python -B scripts/check_layer_imports.py`
- [ ] `python -B scripts/check_text_quality.py`
- [ ] `python -B scripts/check_docstring_coverage.py`
- [ ] `python -B scripts/check_public_api_baseline.py`
- [ ] `python -B scripts/check_resource_consistency.py`
- [ ] `python -B scripts/check_mkdocs_site.py`
- [ ] `uv run python -B -m mkdocs build --strict --site-dir .pytest_tmp/mkdocs-site`
- [ ] `pyright src/dyntool tests/typing_public_api.py`
- [ ] `uv run python -B -m pytest -q --basetemp .pytest_tmp/pytest -p no:cacheprovider`

## 六、Tag 与发布节奏

### RC

- [ ] 形成可识别 RC 提交
- [ ] 创建 `v1.2.0-rc.N` tag
- [ ] 记录 RC 变更范围和剩余风险

### 正式版

- [ ] 清空 RC blocker
- [ ] 更新 `CHANGELOG.md`
- [ ] 创建 `v1.2.0` tag

### 补丁版

补丁版应回到稳定线评估：

- `1.2.1`
- `1.2.2`

如果问题只影响 `1.1.x` 稳定线，则在 `main` 上单独处理，不回流到 `v1.2.0` 的 breaking 叙事。
