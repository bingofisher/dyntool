# 测试与示例

`Internal API`

正式示例采用“系统示例 + 工作流示例”双层结构，并与测试和文档页保持一一映射。

## 要求

- 每个示例目录必须提供中文 `README.md`
- 正式文档页必须给出对应示例与测试
- `docs/examples_manifest.toml` 是示例映射的事实源
- smoke 测试覆盖关键使用路径
- `SET_H5` / `SET_SQLITE_H5` 的证明层回归要优先覆盖 `connect -> save_all -> load_all -> summary_frame`，以及 `scalar_frame()` / `compare_with()` 的摘要快路径
- 性能证明只验证阶段存在、快路径命中和功能一致，不使用脆弱的固定毫秒断言
