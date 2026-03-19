# 处理、评价与绘图

任务目标：从两条加速度时程出发，批量计算 `freqspec`、`respspec`，执行单样本振动评价，并演示类式绘图与传递函数分析器。

前置输入：示例内部构造两条振动时程，无需外部文件。

运行命令：`python examples/10_scenarios/03_evaluate_vibration/main.py`

输出产物：
- 样本集批量 `freqspec` 计算结果
- 样本集批量 `respspec` 计算结果
- 单样本 `zvl` 评价结果
- `TransferFunctionAnalyzer` 生成的 `FreqSpec`
- `FramePlotter` 渲染后的图对象

关键 API：
- `SampleSet.calc_freqspec()`
- `sample_set.processing.calc_respspec()`
- `TransferFunctionAnalyzer.from_samples(...).solve()`
- `FramePlotter().add(...) + plot()`

对应文档：
- [处理、评价与结果对象](/D:/BaiduSyncdisk/13_CodeRepository/Projects/AdvDynTool/docs/usage/03_processing_and_results.md)

对应测试：
- `tests/test_examples_systems.py::test_scenario_evaluate_vibration`
- `tests/test_transfer_function.py`
- `tests/test_plotting.py`

常见问题：
- 批量谱计算默认是严格模式，遇到失败会直接中止；要继续处理剩余样本，请显式传 `strict=False`。
- `overwrite=False` 时，如果目标结果已存在，会返回“跳过”而不是重新计算。
