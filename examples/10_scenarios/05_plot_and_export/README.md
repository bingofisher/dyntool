# 绘图并导出

任务目标：从模型导出 plot payload，并用 plotter-first 接口渲染与落图。

输入：示例内部构造的曲线与模型对象。  
输出：时间曲线图与楼层值专题图。

运行命令：`python examples/10_scenarios/05_plot_and_export/main.py`  
关键 API：`to_plot_payload()`、`render_payload()`、`StoryValuePlotter`  
对应测试：`tests/test_examples_systems.py::test_scenario_plot_and_export`
