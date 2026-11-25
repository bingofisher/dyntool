# 资源驱动评价

稳定性：`Public API`

资源是评价口径的一部分。当前正式路径直接使用 `dyntool.resources` 读取频带和资源表，也可以使用公开的 `ZVLLimit`、`OTOVLLimit`、`FPVDVLimit`、`FDMVLLimit` 从标准条款中提取单个场景限值。

```python
import dyntool.resources as dt_resources

freqs, _ = dt_resources.center_freqs((2.0, 80.0))
print(freqs[:5])
```

## 分频最大振级阈值

```python
from dyntool import FDMVLLimit, FDMVLLimitStandard

standard = FDMVLLimitStandard.JGJ_T_170_2009
print(FDMVLLimit.supported_scenes(standard))
limit = FDMVLLimit.from_standard(standard, scene="居民文教区夜间")
print(float(limit.fdmvl))  # 62.0，单位为 dB
```

[标准表与适用条件](../systems/10_resource_standards.md)规定 4–200 Hz 铅垂向、三分之一倍频程及 Z 计权口径。计算时显式传入 `freq_range=(4.0, 200.0)`；采样率还须覆盖最高频带的上边界，而不只是 200 Hz 中心频率。限值对象不自动改变求解参数，也不替代工程测量及汇总。

正式示例 `examples/10_scenarios/07_resource_driven_eval/main.py` 使用 512 Hz、1024 点的 16 Hz 合成加速度记录，计算 FDMVL，保存并重开 `fdmvl_limit.h5`，通过 `PlotDataset.add_limit(..., axis=...)` 绘制水平阈值，输出 `fdmvl_with_limit.png` 和数值摘要。合成记录只演示链路，不作工程合格判定。测试为 `tests/test_examples_systems.py::test_scenario_resource_driven_eval` 及 `tests/test_limits.py`。
