# 资源驱动评价

任务目标：从内置标准资源中读取约束范围并驱动评价流程。

输入：内置资源表与示例内部构造的振动数据。  
输出：评价摘要与资源驱动结果文件。

运行命令：`python examples/10_scenarios/07_resource_driven_eval/main.py`  
关键 API：`DynTool().resource`、`eval_otovl()`、标准资源查询接口  
对应测试：`tests/test_examples_systems.py::test_scenario_resource_driven_eval`
