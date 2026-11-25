# 示例总览

稳定性：`Public API`

核心库正式示例展示顶层对象 API 与正式模块 API，不直接依赖核心内部导入路径。建筑振动展示为正式维护的 GUI 场景，其桌面启动属于 `Internal API`，生成器为 `Private / implementation detail`。

## 正式场景

- `examples/10_scenarios/01_import_and_normalize/main.py`
- `examples/10_scenarios/02_build_and_manage_samples/main.py`
- `examples/10_scenarios/03_evaluate_vibration/main.py`
- `examples/10_scenarios/04_store_and_reload/main.py`
- `examples/10_scenarios/05_plot_and_export/main.py`
- `examples/10_scenarios/06_logged_run/main.py`
- `examples/10_scenarios/07_resource_driven_eval/main.py`：规范资源与 JGJ/T 170 分频最大振级标量阈值、H5 重开及限值绘图
- `examples/10_scenarios/09_gui_building_showcase/main.py`：[建筑室内振动与隔振效果展示](usage/gui_building_showcase.md)

## Recipes

- `examples/90_recipes/units_and_unit_views/main.py`
- `examples/90_recipes/metadata_patterns/main.py`
- `examples/90_recipes/sample_set_filter_parallel_io/main.py`
- `examples/90_recipes/compute_flow/main.py`
- `examples/90_recipes/compute_plan/main.py`
- `examples/90_recipes/scalar_frame_features/main.py`
- `examples/90_recipes/series_frame_alignment/main.py`
- `examples/90_recipes/peaks_frame/main.py`
- `examples/90_recipes/plot_dataset_and_plotters/main.py`
- `examples/90_recipes/logging_providers_and_modes/main.py`
- `examples/90_recipes/storage_scheme_selection/main.py`
- `examples/90_recipes/statistics_export/main.py`
- `examples/90_recipes/report_package_export/main.py`

## 内部示例

内部示例属于 `Internal API`，不进入正式导航和正式 smoke。具体条目由 `docs/examples_manifest.toml` 维护。
