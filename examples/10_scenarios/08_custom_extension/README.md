# 自定义扩展

任务目标：新增自定义序列、元数据、样本与样本集，并接入标准存储链路。

输入：示例内部定义的 `JerkSeries` 与实验元数据。  
输出：模型 CSV、样本集目录和恢复结果。

运行命令：`python examples/10_scenarios/08_custom_extension/main.py`  
关键 API：`DataModelBase`、`MetadataBase`、`SampleBase`、`SampleSetBase.from_storage()`  
对应测试：`tests/test_examples_systems.py::test_scenario_custom_extension`
