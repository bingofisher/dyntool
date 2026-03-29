# peaks_frame

适用场景：需要把多样本的多峰检测结果整理成统一表格。  
最小代码：运行 `main.py`，查看 `height / prominence / distance` 参数、峰数不一致时的 `NaN` 补齐和 `peak_rank` 索引。  
常见误区：`peaks_frame` 针对事件列表，不替代共享物理轴的 `series_frame`。  
关联文档：`docs/usage/03_processing_and_results.md`
