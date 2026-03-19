# 处理、评价与结果对象

稳定性：`Public API`

## 这一页解决什么问题

这一页说明如何从时程序列得到频谱、反应谱和评价结果，以及如何理解单样本和样本集的返回对象。

## 最短可运行用法

```python
from dyntool import Sample, SampleDomain, VibrationTestMetadata

sample = Sample.from_accel_data(
    [0.0, 0.1, -0.03],
    dt=0.01,
    sample_domain=SampleDomain.VIBRATION_TEST,
    metadata_cls=VibrationTestMetadata,
    case="demo",
    point="P1",
    instr="ACC-01",
    dir="Z",
    record="R1",
    timestamp="2026-03-08 12:00:00",
)
result = sample.eval_zvl(freq_range=(2.0, 60.0))
print(result.ok)
```

## 关键代码片段

--8<-- "generated/snippets/processing_eval_minimal.py"

## 标准类型 / 枚举 / 参数契约

- `Sample.calc_freqspec(...)`
- `Sample.calc_respspec(...)`
- `Sample.eval_zvl(...)`
- `SampleSet.eval_zvl(...)`
- `OperationResult`
- `BatchOperationReport`

## 常见误区

- 误以为 `calc_freqspec()` 会自动落盘
- 误以为样本集批处理会改变正式样本身份字段
- 把结果对象当成裸字典，而不是正式返回类型

## 相关示例

- `examples/10_scenarios/03_evaluate_vibration/main.py`
- `examples/10_scenarios/07_resource_driven_eval/main.py`

## 相关 API

- `Sample`
- `SampleSet`
- `OperationResult`
- `BatchOperationReport`
