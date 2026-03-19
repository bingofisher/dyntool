# 内置资源与标准表

稳定性：`Public API`

当流程依赖标准输入时，应通过 `dyntool.resources` 获取，而不是在脚本里复制常量。

## 正式入口

- `dyntool.resources.keys()`
- `dyntool.resources.manifest()`
- `dyntool.resources.path(key)`
- `dyntool.resources.csv(key, ...)`
- `dyntool.resources.center_freqs(freq_range)`
