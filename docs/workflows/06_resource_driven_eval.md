# 资源驱动评价

稳定性：`Public API`

资源是评价口径的一部分。当前正式路径直接使用 `dyntool.resources` 读取频带和资源表，也可以使用公开的 `ZVLLimit`、`OTOVLLimit`、`FPVDVLimit` 从标准条款中提取单个场景限值。

```python
import dyntool.resources as dt_resources

freqs, _ = dt_resources.center_freqs((2.0, 80.0))
print(freqs[:5])
```
