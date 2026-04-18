# AdvDynTool Codex Rules

## 1) 项目目标与边界
- 本仓库用于动力学计算与振动评价，优先保证数值结果正确性、单位一致性和结果可追溯性。
- 任何涉及行为、接口、架构变化的改动，必须同步更新 `README.md`、`ARCHITECTURE.md` 和正式 MkDocs 文档站内容。
- 允许重构和 API 演进，但禁止无说明的静默破坏。

## 2) 实现层与依赖约束
- 当前实现层固定为：`domain`、`compute`、`application`、`infrastructure`。
- 依赖方向必须满足：
  - `application -> domain/compute`
  - `domain -> compute`
  - `infrastructure -> domain`
- 禁止反向依赖和跨层绕行。
- `compute -> domain` 明确禁止。
- 历史模块只允许删除或归档，不再新增业务功能。

## 3) 正式公开面
- 正式公开面采用两层结构：
  - 顶层对象 API：`AccelSeries`、`Metadata`、`DefaultSample`、`DefaultSampleSet` 等核心对象
  - 独立模块 API：`dyntool.storage`、`dyntool.plotting`、`dyntool.logging`、`dyntool.reporting`
- 正式支持模块：
  - `dyntool.config`
  - `dyntool.resources`
- 不再保留 `DynTool`。
- 不再恢复 `tool.models`、`tool.sample`、`tool.sampleset`、`tool.processing`、`tool.evaluation`、`tool.plotting`、`tool.logger`、`tool.storage` 等旧入口。

## 4) Python 代码规范
- Python >= 3.12，遵循 PEP 8。
- 公开 API 必须有明确类型标注，避免裸 `Any` 作为返回类型。
- 默认使用 `X | None`，除非有兼容需求再使用 `Optional[X]`。
- 模块、类、公共函数与方法使用中文 Google 风格 docstring。
- 代码注释统一使用中文。
- 日志文案可以保持简洁英文，但文档说明必须为中文。
- 运行时异常和用户可见报错使用中文。
- 禁止新增历史头注释模板。

## 5) 单位与 I/O 约束
- 简单轴值模型优先使用 `axis_unit + data_unit`。
- 复合模型优先使用字段级 `units={...}`。
- 保存接口不再公开 `write_units` 一类重复语义参数。
- CSV 读取公开参数统一使用：
  - `skiprows`
  - `sep`
  - `delimiter`
  - `header`
  - `names`
  - `index_col`
  - `encoding`
  - `comment`
  - `decimal`
  - `csv_read_options`
- `inspect_units(...)` 必须能返回轴和值字段单位。
- 模型标准持久化支持 `CSV/H5`，样本标准持久化支持 `H5`，样本集标准持久化支持 `H5/目录导出`。

## 6) 文档与示例规则
- `README.md` 负责入口摘要，不承担完整手册职责。
- 完整用户文档、开发者文档、API 参考统一固化到 MkDocs 文档工程。
- 正式文档采用 `MkDocs + Material + mkdocstrings`。
- 所有正式文档、示例说明、开发者手册统一使用中文。
- 文档中必须显式标注稳定性：
  - `Public API`
  - `Internal API`
  - `Private / implementation detail`
- 公开 API 变更时，必须同时更新：
  - docstring
  - MkDocs API 页入口
  - 至少一个示例引用
  - 至少一个测试覆盖点
- 核心内部模块变更时，必须更新开发者手册与稳定性说明。
- 历史归档文档保留在 `docs/archive`，但不进入正式导航和正式扫描。

## 7) 文本、编码与仓库规则
- README、ARCHITECTURE、docs、全部 docstring、代码注释统一使用中文。
- 仓库源码、文档、配置文件、测试文件统一使用 UTF-8 无 BOM。
- `src/dyntool/resources/**/*.csv` 统一使用 UTF-8-SIG。
- 仓库文本文件统一使用 LF。
- 对外 CSV 导出可按兼容需求使用 `utf-8` 或 `utf-8-sig`。
- 不允许提交乱码文本。
- `.editorconfig` 与 `.gitattributes` 属于仓库强规则，新增文本类型时必须同步更新。

## 8) 必须先问用户的事项
- 公开 API 变化。
- 存储格式变化。
- 单位语义变化。
- 删除功能或兼容层。
- 示例和文档的正式口径变化。
- 任何会影响现有用户迁移路径的默认行为变化。

## 9) 质量门禁
- 提交前至少执行：
  - `uv run python -B scripts/check_codex_assets.py`
  - `uv run ruff check --no-cache src/dyntool tests examples`
  - `uv run ruff format --check src/dyntool tests examples`
  - `uv run python -B scripts/check_layer_imports.py`
  - `uv run python -B scripts/check_text_quality.py`
  - `uv run python -B scripts/check_docstring_coverage.py`
  - `uv run python -B scripts/check_public_api_baseline.py`
  - `uv run python -B scripts/check_resource_consistency.py`
  - `uv run python -B scripts/check_mkdocs_site.py`
  - `uv run python -B scripts/check_repository_governance.py`
  - `uv run python -B scripts/check_helper_structure.py`
  - `$env:PYTHONDONTWRITEBYTECODE='1'; uv run python -B -m mkdocs build --strict --site-dir .pytest_tmp/mkdocs-site`
  - `uv run pyright src/dyntool tests/typing_public_api.py`
  - `$env:PYTHONDONTWRITEBYTECODE='1'; uv run python -B -m pytest -q --basetemp .pytest_tmp/pytest -p no:cacheprovider`
- 关键行为必须有测试：
  - demo 路径
  - `from_accel -> eval -> save/load -> plot` 最小闭环
  - Enum-only 参数校验
  - `tests/input_data` 真实输入文件读取测试
  - 示例 smoke
  - 文档构建与 API 导航一致性

## 10) 示例与测试资源
- README 示例必须可运行或可被 smoke 测试覆盖。
- 示例采用“系统示例 + workflow 示例”双层结构，不以单一大全脚本作为主路径。
- 每个示例目录必须提供 `README.md`。
- 文档中必须提供“功能 -> 示例 -> 测试”映射索引。
- `tests/input_data` 是长期维护的真实输入夹具目录。
- I/O 和样本闭环测试必须覆盖真实输入文件，而不只依赖临时构造数组。

## 11) Codex 工作方式与子代理策略
- 默认优先由主代理直接完成任务，不因为“可以并行”就默认启用子代理。
- 子代理是复杂度驱动的协作手段，不是每次启动时都要使用的默认工作模式。
- 如果任务可以由主代理在当前上下文中稳定完成，应优先直接完成。
- 仓库级子代理定义放在 `.codex/agents/`。
- 仓库级技能定义放在 `.agents/skills/`。
- 这些仓库级 Codex 资产必须纳入 `python scripts/check_codex_assets.py` 校验。

### 简单任务
- 简单任务默认不用子代理，由主代理直接处理。
- 简单任务示例：
  - 单文件小修。
  - 文案、注释、docstring 修正。
  - 局部测试修正。
  - 局部实现细节修正。
  - 不涉及公开 API、存储格式、单位语义、分层边界的微小改动。

### 稍微复杂任务
- 稍微复杂的任务默认仍不用子代理，优先组合多个适用 skill 协作完成。
- 如果只有一个 skill 真正适用，则只使用一个适用 skill，不机械要求必须调用多个 skill。

### 十分复杂任务与重构任务
- 整个项目重构、跨层大改或十分复杂的任务，才考虑使用子代理。
- 涉及公开 API 调整、存储格式变化、单位语义变化时，仍必须先按第 8 节询问用户。

## 12) 维护脚本
- 编码与文本卫生维护入口：
  - `python -B scripts/fix_text_hygiene.py --check`
  - `python -B scripts/fix_text_hygiene.py --apply`
- 生成物清理维护入口：
  - `python -B scripts/clean_generated_artifacts.py --check`
  - `python -B scripts/clean_generated_artifacts.py --apply`
- 这两个脚本只作为维护入口，不替代第 9 节的强制门禁。
- `fix_text_hygiene.py` 只自动修复低风险问题：UTF-8 BOM、LF、可确定的固定乱码片段。
- 无法确定映射的疑似乱码必须保留为人工处理项，不能猜测性转码。
- `clean_generated_artifacts.py` 只允许清理仓库内高置信临时产物，不得删除 `.venv`、`.uv-cache`、`.worktrees`、`.git`。
- 生成物治理优先从命令源头解决，不依赖“生成后再循环删除”：
  - Python 入口统一禁用 bytecode 写入
  - `ruff` 统一使用 `--no-cache`
  - `mkdocs build` 统一输出到已忽略目录，并在 shell 级显式设置 `PYTHONDONTWRITEBYTECODE=1`
  - `pytest` 临时目录统一落到已忽略路径，并关闭 `cacheprovider`

## 13) 内部聚合与 Helper 规则
- 禁止在单文件顶层平铺成组私有 helper，尤其是同前缀、同风格、围绕同一份 payload 或 runtime 状态工作的 `_normalize_*`、`_coerce_*`、`_apply_*`、`_resolve_*` 小函数簇。
- 更推荐的内部组织方式是：
  - 私有 runtime / parser / adapter / resolver 对象
  - 按职责拆开的私有子模块
- 少量职责独立、复用明确的 helper 可以保留，但不得让主流程退化为“读一个文件要横跳一串小函数清单”。
- 该规则由 `uv run python -B scripts/check_helper_structure.py` 作为硬门禁执行。

## 14) plotting 配置与文档口径
- plotting 正式 TOML schema 只能使用当前正式入口：
  - `grid.x.major / grid.x.minor / grid.y.major / grid.y.minor`
  - `axis.x.label / axis.y.label`
  - `axis.x / axis.y`
- `PlotTheme.axis_labels`、`PlotTheme.axis_config` 等运行时对象字段名，只允许在 Python API 或运行时说明中出现，不得冒充正式 TOML schema。
- 项目级 profile / variant patch 仍属于项目层集成手法，不得写成 `dyntool.plotting` 的正式 schema。
- 已移除的 plotting schema/token 不得在正式文档、示例和内置 theme 资产中复活；迁移文档、归档文档和显式负例测试除外。
- 该规则由 `uv run python -B scripts/check_repository_governance.py` 作为硬门禁执行。

## 15) 模块内定义顺序
- 模块内定义顺序遵循“先稳定入口，再下沉细节”的轻量组织规则，不要求所有文件完全同构，但必须保证公开入口可连续阅读。
- 推荐顺序为：
  - 模块常量、类型别名、模块级配置
  - 私有聚合对象或私有 dataclass
  - 对外公开类
  - 对外公开函数
  - 私有薄包装
  - 底层转换、校验、coerce 细节
  - `__all__`
- 私有聚合对象优先于公开入口依赖的散乱 helper；如果公开类或公开函数依赖内部 parser / runtime / adapter / resolver，应把这些聚合对象放在公开入口之前，而不是在公开入口前后散落一组自由 helper。
- 公开类和公开函数应尽量连续、集中出现；禁止公开类/函数之间被一组无关私有 helper 打断主流程。
- 这条规则和第 13 节的 helper 聚合规则配套使用：
  - 第 13 节约束“不要把内部逻辑拆成散乱 helper 簇”
  - 本节约束“即使已有内部对象，也不要把公开入口和底层细节混排”
- 本轮该规则只作为仓库规范与评审约束，不新增自动失败门禁；若后续同类问题继续反复出现，再考虑把“公开入口被无关私有 helper 打断”补进 `check_helper_structure.py`。
