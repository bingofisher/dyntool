# structured_payload_roundtrip

适用场景：需要把模型导出为结构化 payload，再恢复成正式对象。  
最小代码：运行 `main.py`，查看 `AccelSeries -> payload -> AccelSeries` 往返。  
常见误区：把结构化 payload 当成长期持久化格式，而不是对象恢复桥接格式。  
关联场景：`08_custom_extension`
