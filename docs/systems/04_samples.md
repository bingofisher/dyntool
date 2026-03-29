# 样本

- 稳定性：`Public API`
- 适用对象：需要把模型与元数据打包成可保存、可继续计算的业务对象的使用者
- 对应示例：`examples/10_scenarios/02_build_and_manage_samples/main.py`
- 对应测试：`tests/test_examples_systems.py::test_scenario_build_and_manage_samples`

## 用途

`DefaultSample` 是最小业务单元。它把元数据和一组主链数据槽位组织在一起，并对外暴露统一的：

- 数据更新入口
- 元数据更新入口
- alias 管理入口
- 计算入口
- 存储入口

当前正式槽位固定为：

- `accel`
- `vel`
- `disp`
- `force`
- `freqspec`
- `respspec`

## 推荐主线

```python
from dyntool import DefaultSample, SampleDomain, VibrationTestMetadata

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
sample.compute.spectrum.freqspec(source="accel", overwrite=True)
```

## 正式方法

- 元数据：`replace_metadata(...)`、`patch_metadata(...)`
- alias：`set_alias(...)`、`reset_alias()`、`refresh_alias()`
- 计算：`sample.compute`
- 兼容便捷方法：`calc_freqspec(...)`、`calc_respspec(...)`、`eval_*`

## 注意事项

- 不要直接赋值 `sample.metadata` 或 `sample.alias`
- 频谱入口默认使用 `accel`，也可以显式指定 `vel / disp / force`
- 响应谱和振动评价仍保持加速度语义
