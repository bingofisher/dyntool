# 样本与样本集组织

稳定性：`Public API`

## 这页解决什么问题

这页说明如何把模型与元数据组织成 `Sample`，以及如何把多个样本组织成 `SampleSet` 进行批量评价和批量管理。

## 最短可运行用法

```python
from dyntool import Sample, SampleDomain, SampleSet

sample = Sample.from_accel_data([0.0, 0.1, -0.03], dt=0.01, sample_domain=SampleDomain.VIBRATION_TEST)
sample_set = SampleSet.from_samples([sample], sample_domain=SampleDomain.VIBRATION_TEST)
print(len(sample_set))
```

## 关键代码片段

--8<-- "generated/snippets/sample_set_minimal.py"

## 标准类型 / 枚举 / 参数契约

- `Sample.from_accel_data(...)`
- `Sample.from_models(...)`
- `SampleSet.from_samples(...)`
- `SampleSet.eval_zvl(...)`

## 常见误区

- 把样本集当成简单列表，而忽略 UID 唯一约束
- 在批量场景里直接手动操作底层存储实现

## 相关示例

- 场景：[main.py](/D:/BaiduSyncdisk/13_CodeRepository/Projects/AdvDynTool/examples/10_scenarios/02_build_and_manage_samples/main.py)
- Recipe：[main.py](/D:/BaiduSyncdisk/13_CodeRepository/Projects/AdvDynTool/examples/90_recipes/sample_set_filter_parallel_io/main.py)

## 相关 API

- `Sample`
- `SampleSet`
- `SampleDomain`
