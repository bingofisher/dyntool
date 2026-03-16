# storage_scheme_selection

适用场景：需要在模型 CSV、样本集 H5 与目录导出之间选择标准存储方案。  
最小代码：运行 `main.py`，查看不同方案的输出路径和单位检查结果。  
常见误区：继续调用样本集对象上的历史 `to_h5()` 或 `to_csv()`。  
关联场景：`04_store_and_reload`
