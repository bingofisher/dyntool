# 样本与样本集组织

稳定性：`Public API`

## 这一页解决什么问题

这一页说明如何创建 `DefaultSample`、组织 `DefaultSampleSet`，以及如何让元数据、模型和批量操作保持一致。

## 最短可运行用法

```python
from dyntool import DefaultSample, DefaultSampleSet, SampleDomain, VibrationTestMetadata

sample = DefaultSample.from_accel_data(
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
sample.patch_metadata(extra={"source": "docs"})
sample_set = DefaultSampleSet.from_samples([sample], sample_domain=SampleDomain.VIBRATION_TEST)
print(sample_set.count())
```

## 关键代码片段

--8<-- "generated/snippets/sample_set_minimal.py"

## 标准类型 / 枚举 / 参数契约

### 力学时程槽位

稳定性：`Public API`。`DefaultSample` 支持以下可选槽位，读写及部分保存规则与 `accel` 等现有槽位一致：

| 槽位 | 类型 | 默认单位 |
|---|---|---|
| `force` | `ForceSeries` | N |
| `moment` | `MomentSeries` | N·m |
| `stress` | `StressSeries` | Pa |
| `strain` | `StrainSeries` | 无量纲 |

```python
from dyntool import DefaultSample, Metadata, MomentSeries, StressSeries, StrainSeries

sample = DefaultSample(
    metadata=Metadata(identity={"case": "构件试验"}),
    moment=MomentSeries.from_data([1, 2, 3], dt=0.01, data_unit="kilonewton * meter"),
    stress=StressSeries.from_data([10, 20, 30], dt=0.01, data_unit="megapascal"),
    strain=StrainSeries.from_data([100, 200, 300], dt=0.01, data_unit="microstrain"),
)
stress_rms = sample.compute.feature.rms(source="stress")
sample.update_data(strain=StrainSeries.from_data([200, 300, 400], dt=0.01, data_unit="microstrain"))
result = sample.compute.spectrum.freqspec(source="stress", overwrite=True)
spectrum = sample.freqspec
```

这些模型沿用一维或“时间 × 通道”二维结构，通道含义仍由调用者确定；频谱须选择单通道。通用特征及频谱可指定 `source="force"/"moment"/"stress"/"strain"`，仅包含力学时程时默认选择首个可用时程。频谱仍写入现有单个 `freqspec` 槽位，更换来源重新计算须使用 `overwrite=True`，不新增每物理量独立的频谱槽位。单位和序列表导出沿用现有接口；标量报告建议显式指定 `features=["rms"]`，不要将应力标成 PGA。样本级加速度响应谱和振动评价的既有边界不变。不新增张量、坐标系变换或材料本构功能。

- `DefaultSample.from_accel_data(...)`
- `DefaultSample.update_data(...)`
- `DefaultSample.replace_metadata(...)`
- `DefaultSample.patch_metadata(...)`
- `DefaultSample.reset_alias()`
- `DefaultSampleSet.from_samples(...)`
- `DefaultSampleSet.find_by_alias(...)`
- `SampleDomain`

## 常见误区

- 直接写内部属性，绕开 `update...()`、`replace...()` 和 `patch...()` 入口
- 把 `DefaultSampleSet` 当作普通字典使用，忽略正式查询和批量入口
- 在正式代码里直接导入 `dyntool.application.*`

## 相关示例

- `examples/10_scenarios/02_build_and_manage_samples/main.py`
- `examples/90_recipes/metadata_patterns/main.py`

## 相关 API

- `DefaultSample`
- `DefaultSampleSet`
- `SampleDomain`
- `VibrationTestMetadata`
