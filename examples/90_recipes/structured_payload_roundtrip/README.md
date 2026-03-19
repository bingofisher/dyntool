# structured_payload_roundtrip

稳定性：`Internal API`

适用场景：需要验证结构化 payload 与内部对象恢复桥接是否一致。  
最小代码：运行 `main.py`，查看 `AccelSeries -> payload -> AccelSeries` 往返。  
注意：这个示例依赖内部 registry，不属于正式公开面，不计入正式 recipe 口径。  
关联主题：`docs/developer/custom_extension.md`
