# structured_payload_roundtrip

稳定性：`Internal API`

适用场景：需要验证结构化 payload 与内部对象恢复桥接是否一致。  
最小代码：运行 `main.py`，查看 `AccelSeries -> payload -> AccelSeries` 往返。  
注意：这个示例依赖内部 registry，不属于正式公开面，不计入正式 recipe 口径。  
关联主题：`docs/developer/custom_extension.md`

示例同时验证正式 `DefaultSample` 类别和可选计算追溯往返；历史错误类别使用显式离线迁移，源文件保持原样。详见 [核心整改合同](../../../docs/developer/core_architecture_remediation.md)。

稳定性：`Public API`。示例同时验证非 SI 速度的 xarray 快照往返、单位和追溯保留。外部编辑快照数值或时间轴后须移除对应旧追溯。
