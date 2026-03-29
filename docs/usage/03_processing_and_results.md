# 处理、评价与结果对象

稳定性：`Public API`

## 这一页解决什么问题

这一页说明如何从时程序列得到频谱、反应谱和评价结果，以及如何理解单样本和样本集的统一计算入口。

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
sample.compute.process.pipeline(highpass=0.5)
sample.compute.spectrum.freqspec(source="accel", overwrite=True)
result = sample.eval_zvl(freq_range=(2.0, 60.0))
print(result.ok)
```

## 统一计算入口

对象级统一计算入口为：

- `model.compute`
- `sample.compute`
- `sample_set.compute`

主要分组包括：

- `process`
- `derive`
- `spectrum`
- `response`
- `evaluate`
- `feature`
- `plan`
- `flow`

其中：

- `process` 用于截断、基线校正、滤波等处理
- `derive` 用于速度、位移、加速度等派生量计算
- `plan` 用于复用步骤定义
- `flow` 用于阶段化执行、分支和比较

底层 `dyntool.compute` 纯数组函数与对象层入口的分工固定为：

- `dyntool.compute.*`：优先接收纯数组输入，并返回带稳定键名的结果字典
- `model.compute` / `sample.compute` / `sample_set.compute`：负责把底层结果装配为领域对象、写回样本槽位或生成批量报告

## 主线能力

- `sample.compute.process.pipeline(...)`
- `sample.compute.process.flow(...)`
- `sample.compute.spectrum.freqspec(...)`
- `sample.compute.response.respspec(...)`
- `sample.compute.evaluate.zvl(...)`
- `sample.compute.feature.rms(...)`
- `sample.compute.feature.peak(...)`

兼容便捷方法如 `calc_freqspec(...)`、`calc_respspec(...)`、`eval_*` 仍可使用，但不再是文档主路径。

## 边界说明

- `process / spectrum / feature` 支持合适的时序槽位
- `response` 只负责反应谱相关计算
- `evaluate` 只保留 `zvl / otovl / fdmvl / fpvdv` 四个振动评价能力，并继续保持加速度专用语义
- 频谱入口默认源是 `accel`，但也可显式指定 `vel / disp / force`

## 相关 Recipes

- `examples/90_recipes/compute_flow/main.py`
- `examples/90_recipes/compute_plan/main.py`
- `examples/90_recipes/scalar_frame_features/main.py`
- `examples/90_recipes/series_frame_alignment/main.py`
- `examples/90_recipes/peaks_frame/main.py`
