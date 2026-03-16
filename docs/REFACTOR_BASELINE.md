# 重构基线与当前收口结论（日期：2026-03-16）

## 当前已经稳定的事实

1. 实现层命名空间固定为 `application`、`domain`、`compute`、`infrastructure`。
2. `plotting`、`logging`、`storage`、`config`、`resources` 已收口为独立正式模块入口。
3. `dyntool.interfaces` 已移除，相关入口只作为历史兼容禁用项保留在 baseline 与测试守卫里。
4. 元数据、样本和样本集已经收口到 schema-first 与 runtime delegation 路线。
5. `plotting` 已切换为 plotter-first；对象级 `.plot()` 入口不再保留。
6. `logging` 已采用 provider registry；默认 provider 为 `loguru`，缺依赖时自动回退 `stdlib` 并记录一次警告。
7. 正式文档栈已经统一为 `MkDocs + Material + mkdocstrings[python]`。

## 当前仍需持续治理的点

### 1. 活动文档、示例与 baseline 必须继续和代码同口径

README、ARCHITECTURE、活动 docs、examples、baseline 与 smoke 测试必须同步。只要接口、行为或架构发生变化，就必须同步更新这些活动文件。

### 2. 大文件拆分仍有空间，但要以真实边界为准

当前仍偏大的重点文件主要包括：

- `domain.samples.base`
- `domain.samples.sets`
- `storage.runtime`

后续拆分应继续围绕 helper、types、workflow、facade 的真实边界推进，不再引用已经不存在的 `application.model_namespaces` 或 `application.storage_service` 方案。

### 3. 环境噪音与真实回归要分开记录

若出现 `tmp_path`、临时目录权限、可选依赖缺失等环境问题，需要明确记录为环境阻塞，而不是误判为代码回归。

## 推荐治理顺序

1. 先完成活动文档、示例、baseline 和测试守卫同步，保证外部口径稳定。
2. 再补系统级测试与真实输入文件闭环，覆盖 `from_accel -> eval -> save/load -> plot -> log`。
3. 最后推进剩余大文件拆分与内部实现整理。

## 当前建议的验收口径

- `check_layer_imports.py`、`check_public_api_baseline.py`、`check_text_quality.py`、`ruff`、`pyright` 通过
- README、ARCHITECTURE、活动 docs 与当前实现一致
- 示例与 baseline 对齐，smoke 可运行
- 若全量 `pytest` 受环境条件影响，应显式记录阻塞点与替代验证结果
