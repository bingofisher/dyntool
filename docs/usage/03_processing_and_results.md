# 处理、评价与结果对象

稳定性：`Public API`

## 这页解决什么问题

这页说明如何从时域模型继续计算频谱、反应谱和评价对象，并把结果保留在正式对象链路中。

## 最短可运行用法

```python
from dyntool import AccelSeries

accel = AccelSeries.from_data([0.0, 0.1, -0.03, 0.02], dt=0.01)
freqspec = accel.calc_freqspec()
print(type(freqspec).__name__)
```

## 关键代码片段

--8<-- "generated/snippets/processing_eval_minimal.py"

## 标准类型 / 枚举 / 参数契约

- `calc_freqspec()`
- `calc_respspec_bundle()`
- `eval_zvl()`
- `eval_otovl(...)`

## 常见误区

- 只保存最终评价值，不保留中间结果对象
- 处理后不再检查单位与频率范围

## 相关示例

- 场景：[main.py](/D:/BaiduSyncdisk/13_CodeRepository/Projects/AdvDynTool/examples/10_scenarios/03_evaluate_vibration/main.py)
- 场景：[main.py](/D:/BaiduSyncdisk/13_CodeRepository/Projects/AdvDynTool/examples/10_scenarios/07_resource_driven_eval/main.py)

## 相关 API

- `FreqSpec`
- `RespSpec`
- `OTOVLEval`
