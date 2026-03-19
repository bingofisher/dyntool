# 示例附录

稳定性：`Public API`

正式示例采用“场景主线 + recipes”结构。内部扩展示例不计入正式场景。

## 场景主线

| 场景 | 主脚本 | 对应页面 |
| --- | --- | --- |
| 导入并标准化 | `examples/10_scenarios/01_import_and_normalize/main.py` | `docs/usage/01_input_and_types.md` |
| 构建并管理样本 | `examples/10_scenarios/02_build_and_manage_samples/main.py` | `docs/usage/02_samples_and_sets.md` |
| 处理并评价振动 | `examples/10_scenarios/03_evaluate_vibration/main.py` | `docs/usage/03_processing_and_results.md` |
| 存储并回读 | `examples/10_scenarios/04_store_and_reload/main.py` | `docs/usage/04_storage_rules.md` |
| 绘图并导出 | `examples/10_scenarios/05_plot_and_export/main.py` | `docs/usage/05_plotting_logging_resources.md` |
| 带日志运行 | `examples/10_scenarios/06_logged_run/main.py` | `docs/workflows/05_logged_run.md` |
| 资源驱动评价 | `examples/10_scenarios/07_resource_driven_eval/main.py` | `docs/workflows/06_resource_driven_eval.md` |

## Recipes

### 输入与建模
- `examples/90_recipes/units_and_unit_views/main.py`
- `examples/90_recipes/metadata_patterns/main.py`

### 存储与批处理
- `examples/90_recipes/sample_set_filter_parallel_io/main.py`
- `examples/90_recipes/storage_scheme_selection/main.py`

### 绘图与日志
- `examples/90_recipes/plot_dataset_and_plotters/main.py`
- `examples/90_recipes/logging_providers_and_modes/main.py`

## 功能 -> 示例 -> 文档 -> 测试

| 目标 | 示例 | 文档 | 测试 |
| --- | --- | --- | --- |
| 导入并标准化 | `examples/10_scenarios/01_import_and_normalize/main.py` | `docs/usage/01_input_and_types.md` | `tests/test_examples_systems.py::test_scenario_import_and_normalize` |
| 样本与样本集组织 | `examples/10_scenarios/02_build_and_manage_samples/main.py` | `docs/usage/02_samples_and_sets.md` | `tests/test_examples_systems.py::test_scenario_build_and_manage_samples` |
| 处理与评价 | `examples/10_scenarios/03_evaluate_vibration/main.py` | `docs/usage/03_processing_and_results.md` | `tests/test_examples_systems.py::test_scenario_evaluate_vibration` |
| 标准存储闭环 | `examples/10_scenarios/04_store_and_reload/main.py` | `docs/usage/04_storage_rules.md` | `tests/test_examples_systems.py::test_scenario_store_and_reload` |
| 静态绘图 | `examples/10_scenarios/05_plot_and_export/main.py` | `docs/usage/05_plotting_logging_resources.md` | `tests/test_examples_systems.py::test_scenario_plot_and_export` |
| 日志化运行 | `examples/10_scenarios/06_logged_run/main.py` | `docs/workflows/05_logged_run.md` | `tests/test_examples_systems.py::test_scenario_logged_run` |
| 资源驱动评价 | `examples/10_scenarios/07_resource_driven_eval/main.py` | `docs/workflows/06_resource_driven_eval.md` | `tests/test_examples_systems.py::test_scenario_resource_driven_eval` |
| 单位视图 | `examples/90_recipes/units_and_unit_views/main.py` | `docs/usage/01_input_and_types.md` | `tests/test_examples_workflows.py::test_recipe_units_and_unit_views` |
| 存储方案选择 | `examples/90_recipes/storage_scheme_selection/main.py` | `docs/usage/04_storage_rules.md` | `tests/test_examples_workflows.py::test_recipe_storage_scheme_selection` |
| 绘图数据集与 plotter | `examples/90_recipes/plot_dataset_and_plotters/main.py` | `docs/usage/05_plotting_logging_resources.md` | `tests/test_examples_workflows.py::test_recipe_plot_dataset_and_plotters` |
