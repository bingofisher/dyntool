# 存储并回读
任务目标：完成 `from_accel -> calc_freqspec/calc_respspec -> save/load -> plot` 的最小闭环，并确认派生谱结果会随样本集一起持久化。

## 这条场景覆盖什么
- `DefaultSampleSet.save()` / `save_all()`
- `DefaultSampleSet.from_storage(...)`
- `StorageScheme.SET_H5`
- `freqspec` / `respspec` 的持久化与回读
- 回读后继续进入 plotting 主链

## 运行命令

```powershell
python examples/10_scenarios/04_store_and_reload/main.py
```

## 输入

- 示例脚本内部构造的一条振动加速度样本
- 由该样本计算得到的 `freqspec` 与 `respspec`

## 关键 API
- `DefaultSample.calc_freqspec(source=...)`
- `DefaultSample.calc_respspec()`
- `DefaultSampleSet.save()`
- `DefaultSampleSet.from_storage()`
- `PlotTheme.default()`
- `PlotDataset.from_model(...)`
- `FramePlotter(theme=theme).plot_dataset(dataset)`

## 预期结果
- 生成样本集 H5 文件
- 回读后的样本仍然包含 `freqspec`
- 回读后的样本仍然包含 `respspec`
- 生成一张回读后数据的绘图文件

## 输出

- 样本集 H5 存储文件
- 回读后验证 `freqspec` / `respspec` 已恢复的运行结果
- 一张基于回读样本绘制的 PNG 图片

## 对应测试

`tests/test_examples_systems.py::test_scenario_store_and_reload`

## 桌面 GUI 对应验证

GUI 为 `Internal API`，核心保存和回读方法为 `Public API`。运行本示例得到的 H5 可作为桌面导入来源；选取独立项目目录，避免覆盖示例来源。

1. 运行 `uv run python -B -m dyntool_gui.app`，在“导入与筛选”页导入生成的 H5 样本集。
2. 在“数据处理”页执行一个处理动作，确认派生结果和任务报告。
3. 点击“保存分析数据”，选择项目目录，在其 `analysis_data` 子目录保存完整主集；再点击“保存项目”记录仓库引用。
4. 重新打开项目并运行处理或绘图，按需恢复已保存仓库中的结果。关闭前分别确认分析数据和工作区状态，取消时留在当前项目。

这条桌面路径不自动写回导入来源，数据保存提供单样本提交保证。对应回归为 `tests/test_gui_analysis_persistence.py`；完整迁移说明见 `docs/developer/gui_single_route_migration.md`。
