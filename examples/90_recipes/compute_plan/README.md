# compute_plan

适用场景：需要把多步处理流程保存为可复用计划，并重复应用到多个样本。  
最小代码：运行 `main.py`，查看 plan 创建、序列化、恢复与批量执行结果。  
常见误区：`ComputePlan` 定义的是步骤，不直接持有样本数据。  
关联文档：`docs/usage/03_processing_and_results.md`
