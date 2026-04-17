# 处理、评价与绘图

任务目标：从两条加速度时程出发，批量计算 `freqspec`、`respspec`，执行单样本振动评价，并演示显式 plotter 绘图。

前置输入：示例内部构造两条振动时程，无需外部文件。

运行命令：`python examples/10_scenarios/03_evaluate_vibration/main.py`

输出产物：

- 样本集批量 `freqspec` 计算结果
- 样本集批量 `respspec` 计算结果
- 单样本 `zvl` 评价结果
- 样本集 `scalar_frame(features=["pga", "rms", "crest_factor"])` 特征表
- `TransferFunctionAnalyzer` 生成的 `FreqSpec`
- `FramePlotter(theme=...).plot_dataset(...)` 生成的图对象

关键 API：

- `DefaultSampleSet.calc_freqspec()`
- `sample_set.compute.response.respspec()`
- `sample_set.scalar_frame(features=[...])`
- `TransferFunctionAnalyzer.from_samples(...).solve()`
- `PlotDataset.from_* (...)`
- `FramePlotter(...).plot_dataset(dataset, ax=ax)`

对应文档：`docs/usage/03_processing_and_results.md`

对应测试：

- `tests/test_examples_systems.py::test_scenario_evaluate_vibration`
- `tests/test_transfer_function.py`
- `tests/test_plotting.py`
