# 构建并管理样本

任务目标：从多个样本构建 `DefaultSampleSet`，批量评价并检查结果组织。

输入：示例内部构造的振动样本。  
输出：已完成评价的样本集摘要。

运行命令：`python examples/10_scenarios/02_build_and_manage_samples/main.py`  
关键 API：`DefaultSample.from_accel_data()`、`DefaultSampleSet.from_samples()`、`DefaultSampleSet.eval_zvl()`  
对应测试：`tests/test_examples_systems.py::test_scenario_build_and_manage_samples`
