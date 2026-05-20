# GitHub Rulesets 与发布治理

稳定性：`Internal API`

## 目标

本页定义 AdvDynTool 当前采用的 GitHub 仓库治理口径。当前治理只围绕三件事：

- `main` 是唯一正式主线
- `v*` tag 是唯一正式发布事实源
- `CI / quality` 是正式质量门禁入口

当前不引入长期 `release/*`、`hotfix/*` 或 push ruleset 体系。

## 当前正式 Ruleset

### `Protect main`

- 类型：branch ruleset
- 目标：`refs/heads/main`
- 当前规则：
  - 禁止删除分支
  - 禁止 force push
  - 必须通过 Pull Request 合并
  - 至少 `1` 个 approval
  - dismiss stale approvals
  - require conversation resolution
  - require linear history

当前仓库为单维护者场景，因此额外为仓库拥有者配置了 bypass actor，避免仓库进入“规则成立但无人可合并”的锁死状态。该 bypass 只用于当前单维护者治理，不改变正式规则本体。

### `Protect release tags`

- 类型：tag ruleset
- 目标：`refs/tags/v*`
- 当前规则：
  - 限制创建
  - 禁止更新
  - 禁止删除

正式 `v*` tag 只能由授权维护者创建；一旦发布，不允许重打、改写或删除。

## CI 与 required check

仓库当前正式 CI 固定为：

- workflow 名：`CI`
- job 名：`quality`
- workflow 文件：`.github/workflows/ci.yml`

`quality` 当前覆盖的正式门禁包括：

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

当前仓库已恢复 `CI / quality` 并验证通过，但 `Protect main` 还未启用 required status check。这一步属于下一阶段治理动作：

- 启用 `Require status checks to pass before merging`
- required check 固定为：`quality`

## 维护规则

- 不再依赖口头约束决定是否允许直接修改 `main`
- 正式发布事实只认 `v*` tag，不再以 branch 名、PR 标题或临时说明代替
- 若 CI job 名从 `quality` 变更，必须同步更新：
  - 本页
  - 发布检查清单
  - GitHub ruleset 的 required check 配置
- 若未来需要 `rc` 或 `beta` tag，应单独追加规则，不混入正式 `v*` 发布口径
