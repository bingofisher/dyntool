# 处理并评价振动

任务目标：从时程序列走到频谱、反应谱和评价结果对象。

输入：示例内部构造的加速度序列。  
输出：频谱、反应谱和评价摘要。

运行命令：`python examples/10_scenarios/03_evaluate_vibration/main.py`  
关键 API：`calc_freqspec()`、`calc_respspec_bundle()`、`eval_zvl()`  
对应测试：`tests/test_examples_systems.py::test_scenario_evaluate_vibration`
