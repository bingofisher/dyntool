# 报告包导出

稳定性：`Public API`

本页说明 `SampleSetBase` 的报告包导出薄委托口径。当前正式口径是：报告包由 `dyntool.reporting` 统一负责，样本集对象只提供稳定的对象级入口，不在主链路里承载打包格式和报告布局细节。

## 这页解决什么问题

- 从样本集导出完整报告包
- 保持样本集对象的职责边界清晰
- 将报告包结构、统计结果和导出策略统一收敛到 `dyntool.reporting`

## 当前口径

- `SampleSetBase` 只保留对象级调用入口
- 报告包导出属于正式模块 `dyntool.reporting`
- 报告包和统计导出共享同一条正式出口，但在语义上分开说明

## 推荐用法

```python
from pathlib import Path
from dyntool import DefaultSampleSet

sample_set = DefaultSampleSet.from_storage("output/sample_set.h5")
compare_to = DefaultSampleSet.from_storage("output/reference_sample_set.h5")
sample_set.export_report_package(
    Path("output/report_package"),
    compare_to=compare_to,
    features=["pga", "rms"],
    series_vars=["accel"],
    peak_sources=["accel"],
    include_plots=True,
)
```

## 对应示例

- `examples/90_recipes/report_package_export/README.md`

## 对应测试

- `tests/test_reporting.py`
- `tests/test_examples_workflows.py::test_recipe_report_package_export`

