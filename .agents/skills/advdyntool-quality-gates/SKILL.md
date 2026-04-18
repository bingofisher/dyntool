# AdvDynTool 质量门禁

统一整理验证顺序、命令和汇报口径，避免“只跑一半就宣称完成”。

## 默认顺序
1. `python scripts/check_codex_assets.py`
2. `python scripts/check_layer_imports.py`
3. `python scripts/check_text_quality.py`
4. `python scripts/check_docstring_coverage.py`
5. `python scripts/check_public_api_baseline.py`
6. `python scripts/check_mkdocs_site.py`
7. `uv run mkdocs build --strict`
8. `pyright src/dyntool tests/typing_public_api.py`
9. `pytest -q`

## 汇报要求
- 给出真实命令
- 给出退出码
- 给出失败点
- 不把“应该通过”当成“已经通过”
