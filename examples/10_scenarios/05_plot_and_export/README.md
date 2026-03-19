# 绘图并导出

任务目标：使用 `PlotDataset` 和 plotter-first 接口完成基础绘图与落图。  
输入：示例内部构造的时程数据模型。  
输出：基于 `PlotDataset` 的原始曲线图与模型曲线图。  
运行命令：`python examples/10_scenarios/05_plot_and_export/main.py`  
关键 API：`PlotDataset.from_axis_value()`、`FramePlotter.add()`、`FramePlotter.plot()`  
对应测试：`tests/test_examples_systems.py::test_scenario_plot_and_export`
