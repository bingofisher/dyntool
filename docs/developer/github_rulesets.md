# GitHub Rulesets 与发布治理

稳定性：`Internal API`

## 目标

本页固定 AdvDynTool 当前采用的 GitHub 仓库治理口径。治理核心只有三件事：

- `main` 是唯一正式主线
- `v*` tag 是唯一正式发布事实源
- CI 通过后，`quality` 是 `main` 合并前的强制门禁

当前不引入 `release/*`、`hotfix/*`、长期实验分支或 push ruleset 作为主设计前提。

## 正式 Ruleset

### `Protect main`

- 类型：branch ruleset
- 目标：`refs/heads/main`
- 当前固定规则：
  - 禁止删除分支
  - 禁止 force push
  - 合并前必须通过 Pull Request
  - 至少 `1` 个 approval
  - dismiss stale approvals
  - require conversation resolution
  - require linear history

### `Protect release tags`

- 类型：tag ruleset
- 目标：`refs/tags/v*`
- 当前固定规则：
  - 限制创建
  - 禁止更新
  - 禁止删除

正式 `v*` tag 只能由授权维护者创建；一旦发布，不允许重打、改写或删除。

## CI 与 required checks

仓库正式 CI 固定为：

- workflow 名：`CI`
- job 名：`quality`
- workflow 文件：`.github/workflows/ci.yml`

当前 `quality` job 负责执行仓库正式门禁，包括：

- `check_codex_assets.py`
- `ruff check --no-cache`
- `ruff format --check`
- `check_layer_imports.py`
- `check_text_quality.py`
- `check_docstring_coverage.py`
- `check_public_api_baseline.py`
- `check_resource_consistency.py`
- `check_mkdocs_site.py`
- `check_repository_governance.py`
- `check_helper_structure.py`
- `pyright`
- `mkdocs build --strict`
- `pytest -q -p no:cacheprovider`

第一阶段恢复 CI 时，允许 Ruleset 暂不启用 required status checks。待 PR 上的 `quality` 稳定后，再给 `Protect main` 增加：

- `Require status checks to pass before merging`
- required check：`quality`

## 维护规则

- 不再依赖人工口头约束决定是否允许直接推 `main`
- 不再把正式发布事实写在 branch 名或临时说明里；发布事实以 `v*` tag 为准
- 若 CI job 名从 `quality` 变更，必须同步更新：
  - 本页
  - 发布检查清单
  - GitHub Ruleset 中的 required check 配置
- 若未来需要 `rc` 或 `beta` tag，单独追加规则，不混入 `v*` 正式发布口径
