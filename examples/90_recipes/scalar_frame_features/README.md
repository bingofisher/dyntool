# scalar_frame_features

适用场景：需要把样本集的标量指标整理成表，例如 `PGA`、`RMS`。  
最小代码：运行 `main.py`，查看 `strict=True` 报错路径和 `strict=False` 的 `NaN` 补齐。  
常见误区：主体指标如 `pga` 走样本或模型主体方法，通用统计量如 `rms` 才走 `compute.feature`。  
关联文档：`docs/usage/03_processing_and_results.md`
