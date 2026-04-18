# AdvDynTool 回归清单

用于维护 `advdyntool-usage-guide` 时的人工试压。每条都要确认：命中正确正式入口、引用正确文档与示例、没有滑回内部模块或历史路径。

## 主场景回归

### 1. CSV 导入并标准化

- 输入 prompt：如何用 `dyntool` 从 CSV 导入加速度数据、统一单位，再保存为样本集？
- 期望正式入口：`AccelSeries.from_csv(...)`、`DefaultSampleSet.save(...)`、`DefaultSampleSet.from_storage(...)`
- 期望引用：`import_and_normalize`、`docs/usage/01_input_and_types.md`、对应 scenario script / readme / test
- 禁止出现：内部模块导入、历史入口、把单位处理写成私有实现细节

### 2. 最小闭环

- 输入 prompt：给我一个 `from_accel -> eval -> save/load -> plot` 的最短闭环
- 期望正式入口：`DefaultSample.from_accel_data(...)`、`sample.eval_*`、`DefaultSampleSet.from_storage(...)`、`dyntool.plotting`
- 期望引用：`store_and_reload`、`docs/workflows/01_minimal_roundtrip.md`
- 禁止出现：内部存储实现路径、绕开正式 plotting 主链

### 3. sample set 批处理

- 输入 prompt：如何批量构建 sample set、筛选后再做统一评价？
- 期望正式入口：`DefaultSample`、`DefaultSampleSet`、`sample_set.compute`
- 期望引用：`build_and_manage_samples`，必要时补 `sample_set_filter_parallel_io`
- 禁止出现：把批处理入口写成内部模块导入

### 4. plotting 主链

- 输入 prompt：如何用当前 plotting 正式主链画时域曲线和统计图？
- 期望正式入口：`dyntool.plotting`
- 期望引用：`plot_and_export`、`plot_dataset_and_plotters`
- 禁止出现：旧 plotting 助手、旧中文绘图配置入口、绕开 `PlotDataset`

### 5. 带日志运行

- 输入 prompt：如何配置日志并在一次样本评价里落盘日志？
- 期望正式入口：`dyntool.logging.configure_logging(...)`、`dyntool.logging.get_logger(...)`
- 期望引用：`logged_run`，必要时补 `logging_providers_and_modes`
- 禁止出现：把日志推荐为内部 provider 实现细节

### 6. 统计导出

- 输入 prompt：如何从 sample set 导出统计表？
- 期望正式入口：`sample_set.export_scalar_frame(...)`、`sample_set.export_series_frame(...)`、`sample_set.export_peaks_frame(...)`
- 期望引用：`statistics_export`
- 禁止出现：把 reporting 模块内部细节写成首选路径

### 7. 报告包导出

- 输入 prompt：如何导出 report package 并附带图件？
- 期望正式入口：`sample_set.export_report_package(...)`
- 期望引用：`report_package_export`
- 禁止出现：跳过正式样本集对象入口直接引到内部实现

### 8. 资源驱动评价

- 输入 prompt：如何查询内置资源并驱动评价流程？
- 期望正式入口：`dyntool.resources`
- 期望引用：`resource_driven_eval`
- 禁止出现：把资源读取写成内部文件路径操作

## 边界纠偏回归

### 1. 旧 plotting 助手

- 输入 prompt：以前用的旧 plotting 助手现在怎么迁移到当前版本？
- 期望正式入口：`dyntool.plotting`
- 期望引用：`plot_and_export` 或 `plot_dataset_and_plotters`
- 禁止出现：把旧 plotting 助手描述成当前仍推荐可用

### 2. 旧中文绘图配置入口

- 输入 prompt：以前的中文绘图配置入口现在应该怎么写？
- 期望正式入口：`PlotTheme`、`PlotDataset`、具体 plotter、`PlotResult.ax`
- 期望引用：`plot_and_export`
- 禁止出现：推荐已退场的中文绘图配置兼容层

### 3. 内部模块导入

- 输入 prompt：我能直接从 `domain` 或 `compute` 的内部模块里导入样本类型吗？
- 期望正式入口：顶层对象 API 或正式模块 API
- 期望引用：`docs/api/public_api.md`
- 禁止出现：鼓励用户把内部导入路径当正式契约

### 4. 旧顶层入口或历史 tool 路径

- 输入 prompt：旧顶层入口或历史 tool 路径现在怎么迁移？
- 期望正式入口：当前顶层对象 API 与正式模块 API
- 期望引用：`docs/api/public_api.md`
- 禁止出现：把历史路径写成当前推荐主链

### 5. 自定义扩展

- 输入 prompt：我要扩展自己的 sample / sample set 类型，公共用法里该怎么做？
- 期望正式入口：先说明这超出 `Public API` 默认指导范围；只有用户明确要求内部扩展，再转向 `custom_extension`
- 期望引用：默认不引用 internal 示例；明确要求后才引用 `custom_extension`
- 禁止出现：在公共用法问题里默认推荐 internal 示例

## 误触发回归

### 1. 通用 Python CSV 问题

- 输入 prompt：纯 pandas 里怎么读取一个 GBK 编码的 CSV？
- 期望行为：不命中本 skill
- 禁止出现：把无关问题硬转到 `dyntool`

### 2. 通用 matplotlib 问题

- 输入 prompt：matplotlib 里怎么调整 legend 位置？
- 期望行为：不命中本 skill
- 禁止出现：无关场景下硬塞 AdvDynTool plotting 主链

### 3. 通用工程问题

- 输入 prompt：Python 项目里怎么组织日志目录结构更合理？
- 期望行为：不命中本 skill
- 禁止出现：把通用工程建议错误绑定到 `dyntool.logging`
