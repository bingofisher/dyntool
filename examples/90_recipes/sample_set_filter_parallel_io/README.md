# sample_set_filter_parallel_io

适用场景：要在批量读写样本集时启用 `filter`、`workers` 和 `chunk_size`。  
最小代码：运行 `main.py`，检查筛选保存后的加载数量。  
常见误区：以为 `load(filter=...)` 会清空现有数据集。  
关联场景：`04_store_and_reload`
