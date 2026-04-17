# 报告包导出

任务目标：演示 `SampleSetBase` 通过薄委托进入 `dyntool.reporting` 的报告包导出口径，输出完整报告包。

## 这条 recipe 覆盖什么

- 报告包导出
- `SampleSetBase` 对象级薄委托
- `dyntool.reporting` 的正式模块入口

## 运行命令

```powershell
python examples/90_recipes/report_package_export/main.py
```

## 关键 API

- `SampleSetBase`
- `dyntool.reporting`

## 预期结果

- 生成 `report.xlsx`
- 生成 `tables/`、`figures/`
- 生成 `manifest.json`
- 生成 `metadata_summary.json`

## 对应文档

- `docs/workflows/08_report_package_export.md`

## 对应测试

- `tests/test_examples_workflows.py::test_recipe_report_package_export`
