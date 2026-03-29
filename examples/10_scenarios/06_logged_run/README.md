# 带日志运行

任务目标：在正式日志入口下完成评价流程并输出日志文件。

输入：示例内部构造的加速度数据。  
输出：评价结果和目录日志文件。

运行命令：`python examples/10_scenarios/06_logged_run/main.py`  
关键 API：`configure_logging()`、`get_logger()`、`DefaultSample.eval_zvl()`  
对应测试：`tests/test_examples_systems.py::test_scenario_logged_run`
