# 文档规范

稳定性：`Internal API`

本页定义 AdvDynTool 的正式文档写法、docstring 结构、示例映射和文档门禁规则。目标不是堆砌文字，而是保证 README、正式文档站、示例、测试和源码说明始终使用同一套事实。

## 正式文档栈

- 正式文档站统一使用 `MkDocs + Material + mkdocstrings`
- `README.md` 只负责仓库首页摘要，不承担完整手册
- `ARCHITECTURE.md` 负责公开边界、分层规则和默认运行时主链
- `docs/usage` 面向使用者，优先解释任务路径和正式契约
- `docs/api` 面向公开 API，人工说明优先，自动引用补充
- `docs/developer` 面向维护者和扩展开发者
- `docs/reference` 用于 `mkdocstrings` 自动模块参考
- `docs/archive` 只保留历史资料，不进入正式导航和正式扫描

## 稳定性标签

正式文档页必须显式标出稳定性：

- `Public API`
- `Internal API`
- `Private / implementation detail`

规则如下：

- 面向正式用户入口的对象、模块、工作流页面使用 `Public API`
- 只面向维护者、扩展点、内部架构的页面使用 `Internal API`
- 仅解释实现细节且不承诺稳定性的内容使用 `Private / implementation detail`

## Docstring 规范

仓库中的模块、类、公共函数与公共方法统一使用中文 Google 风格 docstring。

### 基本要求

- 模块 docstring 说明职责边界和适用场景
- 类 docstring 优先写 `Attributes`
- 公开函数和方法优先写 `Args`、`Returns`、`Raises`
- 重点入口再补 `Notes`、`Examples`
- 复杂字段、常量、类型别名可用邻近注释或 `#:` 说明

### 变量说明落点

- 公开参数写在 `Args`
- 返回值写在 `Returns`
- 异常边界写在 `Raises`
- dataclass 字段、`ClassVar`、关键属性写在 `Attributes`
- 局部复杂状态只在必要处写中文注释，不为普通局部变量逐个写说明

## 页面编排规范

用户主路径页面优先使用以下结构：

1. 这一页解决什么问题
2. 最短可运行用法
3. 关键代码片段
4. 标准类型 / 枚举 / 参数契约
5. 常见误区
6. 相关示例
7. 相关 API

重点页面必须直接展示代码片段，不能只给文件路径。

## 示例联动规则

- 正式示例采用“场景主线 + recipes”结构
- 每个示例目录必须提供中文 `README.md`
- `docs/examples_manifest.toml` 是“功能 -> 示例 -> 文档 -> 测试”映射的事实源
- 正式用户页必须至少给出一个对应示例
- 公开 API 变更时，至少同步一个示例和一个测试覆盖点

## 文档门禁

提交前至少验证：

- `uv run python -B scripts/check_text_quality.py`
- `uv run python -B scripts/check_docstring_coverage.py`
- `uv run python -B scripts/check_mkdocs_site.py`
- `$env:PYTHONDONTWRITEBYTECODE='1'; uv run python -B -m mkdocs build --strict --site-dir .pytest_tmp/mkdocs-site`

若改动涉及公开 API、示例或文档结构，还必须同步验证：

- `uv run python -B scripts/check_public_api_baseline.py`
- `uv run python -B -m pytest -q --basetemp .pytest_tmp/pytest -p no:cacheprovider`

## 禁止项

- 不再引入旧文档栈和旧 API 页入口
- 不在正式页面里只写“见某文件”，而不给最小代码片段
- 不在公开文档中把 `Internal API` 包装成正式主用法
