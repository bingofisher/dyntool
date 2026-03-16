# 存储并回读

任务目标：完成 `from_accel -> eval -> save/load -> plot` 的最小闭环。

输入：示例内部构造的加速度数据。  
输出：样本集 H5 与绘图文件。

运行命令：`python examples/10_scenarios/04_store_and_reload/main.py`  
关键 API：`SampleSet.save()`、`SampleSet.from_storage()`、`render_payload()`  
对应测试：`tests/test_examples_systems.py::test_scenario_store_and_reload`
