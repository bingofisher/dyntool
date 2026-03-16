# 绘图、日志与资源

稳定性：`Public API`

## 这页解决什么问题？

这页说明三个正式模块 API：`dyntool.plotting`、`dyntool.logging`、`DynTool.resource`。它们不负责建模本身，但决定结果如何展示、如何排查以及如何复用标准资源。

## 最短可运行用法

```python
import dyntool.logging as dt_logging
import dyntool.plotting as dt_plotting
from dyntool import AccelSeries, DynTool, LoggingMode

accel = AccelSeries.from_data([0.0, 0.1, -0.03], dt=0.01)
dt_logging.configure_logging(mode=LoggingMode.CONSOLE_ONLY, level="INFO")
payload = accel.to_plot_payload()
plot = dt_plotting.render_payload(payload)
tool = DynTool()
print(type(plot).__name__, len(tool.resource.keys()))
```

## 关键代码片段

--8<-- "generated/snippets/plotting_minimal.py"

## 标准类型 / 枚举 / 参数契约

- `AccelSeries.to_plot_payload(...)`
- `dyntool.plotting.render_payload(...)`
- `dyntool.plotting.render_plotter(...)`
- `configure_logging(provider=..., mode=..., level=..., provider_options=...)`
- `LoggingMode`

## 常见误区

- 继续寻找对象级 `.plot()` 接口，而不是使用 plotter-first 入口
- 误以为切到 `loguru` 后 `get_logger()` 会返回第三方 logger
- 假设 plotting 默认会随机选择系统中文字体；正式默认字体是模块内置 `SongTNR`

## 相关示例

- 场景：[main.py](/D:/BaiduSyncdisk/13_CodeRepository/Projects/AdvDynTool/examples/10_scenarios/05_plot_and_export/main.py)
- Recipe：[main.py](/D:/BaiduSyncdisk/13_CodeRepository/Projects/AdvDynTool/examples/90_recipes/plot_payload_and_plotters/main.py)
- Recipe：[main.py](/D:/BaiduSyncdisk/13_CodeRepository/Projects/AdvDynTool/examples/90_recipes/logging_providers_and_modes/main.py)

## 相关 API

- `dyntool.plotting`
- `configure_zh`
- `dyntool.logging`
- `DynTool().resource`
