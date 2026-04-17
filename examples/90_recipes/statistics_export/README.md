# 统计导出

任务目标：演示 `SampleSetBase` 通过薄委托进入 `dyntool.reporting` 的统计导出口径，输出可复用的统计结果。

## 这条 recipe 覆盖什么

- 样本集统计结果导出
- `SampleSetBase` 对象级薄委托
- `dyntool.reporting` 的正式模块入口

## 运行命令

```powershell
python examples/90_recipes/statistics_export/main.py
```

## 关键 API

- `SampleSetBase`
- `dyntool.reporting`

## 预期结果

- 生成 `scalar_frame.xlsx`
- 生成 `series_frame.csv`
- 生成 `peaks_frame.xlsx`
- 生成 `compare_report.xlsx`

## 对应文档

- `docs/workflows/07_statistics_export.md`

## 对应测试

- `tests/test_examples_workflows.py::test_recipe_statistics_export`
