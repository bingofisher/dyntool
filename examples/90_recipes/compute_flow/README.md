# compute_flow

适用场景：需要对单个样本做阶段化处理、创建检查点、派生分支并比较处理前后差异。  
最小代码：运行 `main.py`，查看 `truncate / highpass / checkpoint / branch / restore / commit` 的完整链路。  
常见误区：`commit(replace=False)` 只返回结果副本，不会原位写回样本槽位。  
稳定性：`Public API`。样本分支继承原槽位提交能力：`replace=True` 写回原样本并返回样本，主流保留自己的计算快照；普通无绑定流返回结果。分支的计算状态及可变上下文独立。仅预览须显式使用 `replace=False`。
关联文档：`docs/usage/03_processing_and_results.md`
