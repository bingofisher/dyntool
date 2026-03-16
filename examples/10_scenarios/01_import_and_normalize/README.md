# 导入并标准化

任务目标：把真实文本输入导入为正式模型，统一单位后落盘并进入样本链路。

输入：`examples/input_data/` 与 `tests/input_data/` 中的真实输入文件。  
输出：标准化 CSV、样本集 H5。

运行命令：`python examples/10_scenarios/01_import_and_normalize/main.py`  
关键 API：`AccelSeries.from_csv()`、`SampleSet.save()`、`SampleSet.from_storage()`  
对应测试：`tests/test_examples_systems.py::test_scenario_import_and_normalize`
