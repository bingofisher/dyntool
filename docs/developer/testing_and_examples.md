# 测试与示例

`Internal API`

正式示例采用“系统示例 + 工作流示例”双层结构，并与测试和文档页保持一一映射。

## 要求

- 每个示例目录必须提供中文 `README.md`
- 正式文档页必须给出对应示例与测试
- `docs/examples_manifest.toml` 是示例映射的事实源
- smoke 测试覆盖关键使用路径
- `SET_H5` / `SET_SQLITE_H5` 的证明层回归要优先覆盖 `connect -> save_all -> load_all -> summary_frame`，以及 `scalar_frame()` / `compare_with()` 的摘要快路径
- 性能证明只验证阶段存在、快路径命中和功能一致，不使用脆弱的固定毫秒断言

## 核心一致性回归

[核心库行为、示例与测试映射](core_correctness_migration.md)覆盖独立数值基准、单位矩阵、各策略部分更新和故障注入。故障测试只使用临时仓库。`scripts/benchmark_set_sqlite_h5_io.py` 输出固定种子和规模的原始计时 JSON；比较同条件中位数，不把单样本提交误写为整批回滚。

维护脚本与核心库、测试、示例一并执行 Ruff 检查；连续问号 docstring 纳入文本门禁。

## GUI 单路线回归

GUI 范围与批次行为见 [GUI 单路线迁移与可靠性](gui_single_route_migration.md) 的功能、示例与测试映射。Ruff 检查覆盖 `src/dyntool_gui`；空范围、失败统计、已有结果跳过和协作式中止使用真实振动样本验证。Web 专属实现和测试退出后，由治理测试检查依赖组、发行包、正式导航和启动说明，避免恢复平行路线。

分析数据保存与未保存保护由 `tests/test_gui_analysis_persistence.py` 使用真实 QThread 和临时仓库验证；覆盖懒源另存、源文件摘要不变、部分失败、重试、冷启动结果恢复、关闭取消和保存失败。项目 JSON 原子替换由 `tests/test_gui_workbench_persistence.py` 注入序列化、写入与替换异常。自动巡检只对自己创建的审计窗口明确放弃内存状态，不自动保存原始来源。

## 建筑振动展示

[建筑振动展示](../usage/gui_building_showcase.md)是正式维护的 GUI 场景。`tests/test_gui_building_showcase.py` 验证固定种子、实际 36 样本矩阵、0.35 倍对照、预计算、真实子集、默认渲染、图片保存、重算和项目重开。测试仅使用生成的临时合成仓库，生成 smoke 不启动窗口。

## 核心整改回归映射

力学时程的 `Public API` 用法并入 `02_build_and_manage_samples` 场景；`tests/test_mechanical_series.py` 覆盖四种模型的单位、形状、FFT 幅值、CSV/H5、注册交换、受控更新和六策略部分保存、懒加载及 deep 检查，以及实际来源的 RMS 比较和 SI 导出。`tests/typing_public_api.py` 验证四个槽位返回类型，`tests/test_examples_systems.py::test_scenario_build_and_manage_samples` 验证示例。

| 功能 | 相关示例 | 测试 |
|---|---|---|
| 独立查询、只读与受控修改 | `sample_set_filter_parallel_io`、`compute_flow` | `tests/test_core_architecture_contracts.py` |
| 单位、二维积分、FFT 与采样率 | `units_and_unit_views` | `tests/test_core_numerical_contracts.py`、`tests/test_core_architecture_contracts.py` |
| 追溯、部分保存、命名冲突 | `storage_scheme_selection`、`structured_payload_roundtrip` | `tests/test_core_storage_contracts.py`、`tests/test_core_architecture_contracts.py` |
| SI 报告、暂存及回滚 | `statistics_export`、`report_package_export` | `tests/test_reporting.py`、`tests/test_core_architecture_contracts.py` |
| JGJ/T 170 标量阈值、规范来源、H5 与绘图 | `resource_driven_eval` | `tests/test_limits.py`、`tests/test_resources.py`、`tests/test_examples_systems.py::test_scenario_resource_driven_eval` |
| 标准编号及旧值拒绝、标量完整性、限值 DataFrame / xarray 来源往返 | `resource_driven_eval` | `tests/test_limits.py` |
| 原位单位通知失败回滚、重复追溯冲突拒绝 | `structured_payload_roundtrip`、`units_and_unit_views` | `tests/test_core_architecture_contracts.py` |
| 同名坐标冲突、无效交换版本、残缺计算依据拒绝 | `structured_payload_roundtrip` | `test_structured_payload_rejects_conflicting_coordinate_and_variable`、`test_exchange_payload_rejects_invalid_version_format`、`test_result_provenance_rejects_fresh_record_without_basis`、`test_result_provenance_rejects_history_without_input_revision` |
| 六策略存储精度保留实际计算参数及输入版本 | `storage_scheme_selection` | `test_storage_precision_preserves_calculation_parameters` |

最低支持 Python 3.12.12 运行核心回归并验证隔离 wheel 安装；`CI / quality` 继续执行完整门禁及现有 GUI 回归。性能脚本使用固定种子 20261004、重复三次和固定规模，详见 [复核记录](core_architecture_verification.md)。

## 后续修复回归映射

| 功能 | 示例 | 测试 |
|---|---|---|
| 传递函数独立 DFT、浮点采样率及单通道 | `03_evaluate_vibration` | `tests/test_core_review_followup.py` 的传递函数回归 |
| 直接依赖、多级失效与分支提交回滚 | `compute_flow` | `test_dependency_order_self_update_and_all_matching_slots`、`test_branch_commit_failure_rolls_back` |
| xarray 单位、形状、根及分量追溯 | `structured_payload_roundtrip` | `test_xarray_complete_model_roundtrip`、`test_xarray_unit_conflict_rejected` |
| 六策略可恢复性与合法部分状态覆盖 | `storage_scheme_selection` | `test_deep_detects_unrecoverable_payload_across_schemes`、`test_dependency_partial_save_reopen_and_deep` |
| 摘要一次扫描、quick 不读数组 | `storage_scheme_selection` | `test_deep_summary_query_is_batched`、`test_quick_never_reads_arrays` |
