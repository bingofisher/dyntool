# 统计导出

稳定性：`Public API`

本页说明 `SampleSetBase` 的统计导出薄委托口径。当前正式口径是：样本集对象负责对外提供稳定入口，统计类导出逻辑下沉到 `dyntool.reporting`，避免在样本集主链路里继续堆叠报表细节。

## 这页解决什么问题

- 把样本集的统计结果导出为可复用的表格或文件
- 保持 `SampleSetBase` 的对象语义稳定，导出实现通过薄委托进入 `dyntool.reporting`
- 为后续的统计表、汇总表和报表字段扩展预留统一入口

## 当前口径

- `SampleSetBase` 继续保留样本集身份、查询和组织能力
- 统计导出不再作为样本集内部重实现细节暴露
- 对外正式模块采用 `dyntool.reporting`

## 推荐用法

```python
from pathlib import Path
from dyntool import DefaultSampleSet

sample_set = DefaultSampleSet.from_storage("output/sample_set.h5")
sample_set.export_scalar_frame(
    Path("output/statistics/scalar_frame.xlsx"),
    features=["pga", "rms"],
)
sample_set.export_series_frame(
    Path("output/statistics/series_frame.csv"),
    data_var="accel",
    format="csv",
)
sample_set.export_peaks_frame(
    Path("output/statistics/peaks_frame.xlsx"),
    source="accel",
)
```

## 对应示例

- `examples/90_recipes/statistics_export/README.md`

## 对应测试

- `tests/test_reporting.py`
- `tests/test_examples_workflows.py::test_recipe_statistics_export`

