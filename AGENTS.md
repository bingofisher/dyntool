# AdvDynTool Codex Rules

## 1) 项目目标与边界
- 本仓库用于动力学计算与振动评价，优先保证数值结果正确性、单位一致性和结果可追溯性。
- 任何涉及行为、接口、架构变化的改动，必须同步更新 `README.md`、`ARCHITECTURE.md` 和正式文档站内容。
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
  - 顶层对象 API：`AccelSeries`、`Metadata`、`Sample`、`SampleSet` 等核心对象
  - 独立模块 API：`dyntool.storage`、`dyntool.plotting`、`dyntool.logging`
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
- 仓库源码、文档、配置文件统一使用 UTF-8 无 BOM。
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
  - `python scripts/check_codex_assets.py`
  - `ruff check src/dyntool tests examples`
  - `ruff format --check src/dyntool tests examples`
  - `python scripts/check_layer_imports.py`
  - `python scripts/check_text_quality.py`
  - `python scripts/check_docstring_coverage.py`
  - `python scripts/check_public_api_baseline.py`
  - `python scripts/check_mkdocs_site.py`
  - `uv run mkdocs build --strict`
  - `pyright src/dyntool tests/typing_public_api.py`
  - `pytest -q`
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
- 稍微复杂任务示例：
  - 同一子系统内的多文件改动。
  - 需要同时补测试和补文档说明的改动。
  - 需要组合两个及以上适用 skill 才能更稳妥完成的任务。
  - 复杂度高于单点修补，但不属于整个仓库重构或跨层系统性改动的任务。

### 十分复杂任务与重构任务
- 整个项目重构、跨层大改或十分复杂的任务，才考虑使用子代理。
- 十分复杂任务示例：
  - 跨 `domain`、`compute`、`application`、`infrastructure` 多层联动的重构。
  - 公开 API 调整。
  - 存储格式变化。
  - 单位语义变化。
  - 需要同步大量文档、示例、测试与质量基线检查的系统性改动。

### 询问用户是否启用子代理
- 当代理判断“有必要使用子代理”时，必须先询问用户是否启用子代理。
- 只有以下两种情况可以不先询问：
  - 用户已经明确指定要使用子代理。
  - 用户明确在询问是否应该使用子代理或如何使用子代理。
- 即使任务理论上可以拆分并行，只要主代理能够稳定完成，也不应仅因并行便利而默认启用子代理。

### 与现有确认规则的关系
- 本节只规定 Codex 的工作方式，不覆盖本文件第 8 节“必须先问用户的事项”。
- 涉及公开 API、存储格式、单位语义、兼容层删除、默认行为变化等事项时，仍必须先按第 8 节询问用户。
