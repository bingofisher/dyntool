# 可视化

- 稳定性：`Public API`
- 适用对象：需要把模型导出的 payload 交给正式 plotter 渲染的使用者
- 对应示例：`examples/10_scenarios/05_plot_and_export/main.py`
- 对应测试：`tests/test_examples_systems.py::test_scenario_plot_and_export`

## 用途

正式绘图采用 plotter-first 结构：模型负责导出 payload，`dyntool.plotting` 负责渲染。
