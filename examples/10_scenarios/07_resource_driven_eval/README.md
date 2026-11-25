# 资源驱动评价

稳定性：`Public API`

这个场景演示如何用正式资源模块读取内置频带和标准资源，再驱动评价流程。

关键 API：`dyntool.resources.center_freqs(...)`、`ZVLLimit.from_standard(...)`、`OTOVLLimit.from_standard(...)`、`FDMVLLimit.from_standard(...)`、`eval_otovl()`、`eval_fdmvl()`。

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
uv run python -B examples/10_scenarios/07_resource_driven_eval/main.py
```

示例将 JGJ/T 170—2009 的“居民文教区夜间”阈值读取为 62 dB 标量。使用 512 Hz、1024 点的 16 Hz 合成加速度记录，显式计算 4–200 Hz 的 FDMVL，保存并重开限值 H5，然后按现有绘图流程广播为水平线。输出位于 `tmp/examples/resource_driven_eval/`，包含 `fdmvl_limit.h5`、`fdmvl_with_limit.png` 和 `resource_summary.txt`。

城市 Z 振级限值同时演示 `to_pandas() -> from_pandas()` 及 `to_xarray() -> from_xarray()`：规范来源和追溯保留在独立 `attrs`，标准编号只接受 `GB 10070-1988`，历史 `GB_10070-1988` 明确拒绝。标量载荷须恰好一个值，表须恰好一行；CSV 不保存 DataFrame 属性，完整来源持久化使用 H5。

数据仅为链路演示，不作工程合格判定。该阈值用于 Z 计权后的分频最大振级，不能混用于未计权倍频程或最大 Z 振级。区域和昼夜须明确选择，工程测量及汇总要求另行核验。

`FDMVLLimit` 已由原曲线占位统一为标量：没有 `freq` 字段，显式构造传入 `fdmvl: float`；绘图轴通过 `PlotDataset.add_limit(limit, axis=...)` 提供。旧曲线载荷必须明确单个阈值后迁移，不能静默取首值。
