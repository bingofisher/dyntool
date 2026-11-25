# units_and_unit_views

适用场景：想快速确认模型单位、转换结果和导出单位信息。  
最小代码：运行 `main.py`，查看 `inspect_units()` 与导出 CSV。  
常见误区：把轴单位和值单位混用。  
关联场景：`01_import_and_normalize`

本例还验证 SI 与工程计算上下文得到同一物理速度，以及多通道非 SI CSV 的单位往返。对应回归为 `tests/test_core_numerical_contracts.py`。
