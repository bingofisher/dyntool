# compute_flow

适用场景：需要对单个样本做阶段化处理、创建检查点、派生分支并比较处理前后差异。  
最小代码：运行 `main.py`，查看 `truncate / highpass / checkpoint / branch / restore / commit` 的完整链路。  
常见误区：`commit(replace=False)` 只返回结果副本，不会原位写回样本槽位。  
关联文档：`docs/usage/03_processing_and_results.md`
