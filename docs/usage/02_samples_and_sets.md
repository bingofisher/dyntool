# 样本与样本集组织

稳定性：`Public API`

## 这一页解决什么问题

这一页说明如何创建 `Sample`、组织 `SampleSet`，以及如何让元数据、模型和批量操作保持一致。

## 最短可运行用法

```python
from dyntool import Sample, SampleDomain, SampleSet, VibrationTestMetadata

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
sample_set = SampleSet.from_samples([sample], sample_domain=SampleDomain.VIBRATION_TEST)
print(sample_set.count())
```

## 关键代码片段

--8<-- "generated/snippets/sample_set_minimal.py"

## 标准类型 / 枚举 / 参数契约

- `Sample.from_accel_data(...)`
- `Sample.update_data(...)`
- `Sample.update_metadata(...)`
- `SampleSet.from_samples(...)`
- `SampleSet.find_by_alias(...)`
- `SampleDomain`

## 常见误区

- 直接写内部属性，绕开 `update...()` 和 `replace...()` 入口
- 把 `SampleSet` 当作普通字典使用，忽略正式筛选和批量入口
- 在正式代码里直接导入 `dyntool.application.*`

## 相关示例

- `examples/10_scenarios/02_build_and_manage_samples/main.py`
- `examples/90_recipes/metadata_patterns/main.py`

## 相关 API

- `Sample`
- `SampleSet`
- `SampleDomain`
- `VibrationTestMetadata`
