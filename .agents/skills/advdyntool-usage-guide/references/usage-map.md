# AdvDynTool 使用地图

以 `docs/examples_manifest.toml` 为示例映射事实源，按“任务 -> 正式入口 -> example id -> doc / script / readme / test”组织。若本页与 `src/dyntool/__init__.py`、`docs/api/public_api.md` 或 manifest 冲突，以后三者为准。

## 真实文件导入与标准化

- 正式入口：`AccelSeries.from_csv(...)`、`DefaultSample.from_models(...)`、`DefaultSampleSet.save(...)`、`DefaultSampleSet.from_storage(...)`
- example id：`import_and_normalize`
- doc：`docs/usage/01_input_and_types.md`
- script：`examples/10_scenarios/01_import_and_normalize/main.py`
- readme：`examples/10_scenarios/01_import_and_normalize/README.md`
- test：`tests/test_examples_systems.py::test_scenario_import_and_normalize`

## 最小闭环

- 正式入口：`DefaultSample.from_accel_data(...)`、`sample.eval_*`、`DefaultSampleSet.from_storage(...)`、`dyntool.plotting`
- example id：`store_and_reload`
- doc：`docs/workflows/01_minimal_roundtrip.md`
- script：`examples/10_scenarios/04_store_and_reload/main.py`
- readme：`examples/10_scenarios/04_store_and_reload/README.md`
- test：`tests/test_examples_systems.py::test_scenario_store_and_reload`

## sample / sample set 构建与批处理

- 正式入口：`DefaultSample`、`DefaultSampleSet`
- example id：`build_and_manage_samples`
- doc：`docs/usage/02_samples_and_sets.md`
- script：`examples/10_scenarios/02_build_and_manage_samples/main.py`
- readme：`examples/10_scenarios/02_build_and_manage_samples/README.md`
- test：`tests/test_examples_systems.py::test_scenario_build_and_manage_samples`
- 补充 recipe：`sample_set_filter_parallel_io`

## processing / evaluation

- 正式入口：`model.compute`、`sample.compute`、`sample_set.compute`
- example id：`evaluate_vibration`
- doc：`docs/usage/03_processing_and_results.md`
- script：`examples/10_scenarios/03_evaluate_vibration/main.py`
- readme：`examples/10_scenarios/03_evaluate_vibration/README.md`
- test：`tests/test_examples_systems.py::test_scenario_evaluate_vibration`
- 补充 recipe：`compute_flow`、`compute_plan`

## storage 检测与 scheme 选择

- 正式入口：`DefaultSample.save(...)`、`DefaultSampleSet.from_storage(...)`、`dyntool.storage.detect_storage_scheme(...)`、`dyntool.storage.inspect_storage_repository(...)`
- example id：`store_and_reload`
- doc：`docs/usage/04_storage_rules.md`
- script：`examples/10_scenarios/04_store_and_reload/main.py`
- readme：`examples/10_scenarios/04_store_and_reload/README.md`
- test：`tests/test_examples_systems.py::test_scenario_store_and_reload`
- 补充 recipe：`storage_scheme_selection`

## plotting 正式主链

- 正式入口：`dyntool.plotting`
- 固定主链：`PlotDataset.from_* -> PlotTheme.from_file/default -> concrete plotter -> PlotResult.ax`
- plotting continuous 轴补充口径：`ticks.major.step` / `ticks.minor.step` 默认按 `origin = 0` 起算，scientific 默认关闭，只有显式开启时才启用
- plotting 字号补充口径：`axis.<side>.label.fontsize` 管轴标签，`axis.<side>.ticks.fontsize` 管 ticklabel，`formatter.scientific.fontsize` 只管 offset 文本
- example id：`plot_and_export`
- doc：`docs/usage/05_plotting_logging_resources.md`
- script：`examples/10_scenarios/05_plot_and_export/main.py`
- readme：`examples/10_scenarios/05_plot_and_export/README.md`
- test：`tests/test_examples_systems.py::test_scenario_plot_and_export`
- 补充 recipe：`plot_dataset_and_plotters`

## logging / 带日志运行

- 正式入口：`dyntool.logging.configure_logging(...)`、`dyntool.logging.get_logger(...)`
- example id：`logged_run`
- doc：`docs/workflows/05_logged_run.md`
- script：`examples/10_scenarios/06_logged_run/main.py`
- readme：`examples/10_scenarios/06_logged_run/README.md`
- test：`tests/test_examples_systems.py::test_scenario_logged_run`
- 补充 recipe：`logging_providers_and_modes`

## statistics export

- 正式入口：`sample_set.export_scalar_frame(...)`、`sample_set.export_series_frame(...)`、`sample_set.export_peaks_frame(...)`
- example id：`statistics_export`
- doc：`docs/workflows/07_statistics_export.md`
- script：`examples/90_recipes/statistics_export/main.py`
- readme：`examples/90_recipes/statistics_export/README.md`
- test：`tests/test_examples_workflows.py::test_recipe_statistics_export`

## report package export

- 正式入口：`sample_set.export_report_package(...)`
- 需要模块函数时补：`dyntool.reporting.export_report_package(...)`
- example id：`report_package_export`
- doc：`docs/workflows/08_report_package_export.md`
- script：`examples/90_recipes/report_package_export/main.py`
- readme：`examples/90_recipes/report_package_export/README.md`
- test：`tests/test_examples_workflows.py::test_recipe_report_package_export`

## resources / resource-driven evaluation

- 正式入口：`dyntool.resources`
- example id：`resource_driven_eval`
- doc：`docs/workflows/06_resource_driven_eval.md`
- script：`examples/10_scenarios/07_resource_driven_eval/main.py`
- readme：`examples/10_scenarios/07_resource_driven_eval/README.md`
- test：`tests/test_examples_systems.py::test_scenario_resource_driven_eval`

## 默认不推荐的入口

- 不推荐未出现在 `src/dyntool/__init__.py`、`docs/api/public_api.md` 或正式模块 `__all__` 中的符号
- 不推荐内部模块导入路径
- 不把内部实现细节包装成当前正式主链
- 不默认推荐 `kind="internal"` 条目；只有用户明确要求 `Internal API` 或自定义扩展时，才允许转向 `custom_extension`
