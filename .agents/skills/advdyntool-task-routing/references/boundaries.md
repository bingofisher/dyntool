# 角色边界

- `public-surface-guardian` 只处理公开入口与正式公开口径。
- `test-specialist` 只改 `tests/`。
- `docs-sync` 只改 README、ARCHITECTURE 和 `docs/`。
- `verification-runner`、`spec-reviewer`、`code-quality-reviewer` 一律只读。
- 业务实现代理不得并行改 `src/dyntool/__init__.py`、README、ARCHITECTURE。
