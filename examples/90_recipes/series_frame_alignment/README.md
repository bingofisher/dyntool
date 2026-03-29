# series_frame_alignment

适用场景：需要把多个样本的同类序列按公共索引对齐到一张表。  
最小代码：运行 `main.py`，查看外连接索引、`MultiIndex` 列和缺失样本的 `NaN` 列组。  
常见误区：`strict=False` 只容忍缺数据，不容忍混合不同轴语义。  
关联文档：`docs/usage/03_processing_and_results.md`
