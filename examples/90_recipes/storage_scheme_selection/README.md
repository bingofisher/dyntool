# storage_scheme_selection

适用场景：需要在模型 CSV、样本集 H5、SQLite+H5 并行样本集与目录导出之间选择正式存储方案。

最小代码：运行 `main.py`，查看不同方案的输出路径和单位检查结果。

本轮补充约定：

- H5 模型、单样本和样本集写入默认都启用 `gzip`
- 默认压缩级别为 `4`
- 样本/样本集可以通过 `data_options` 覆盖 H5 压缩参数
- `StorageScheme.SET_SQLITE_H5` 会生成 `index.sqlite + payload.h5`，适合大样本集快速打开与 metadata 索引读取
- `SampleSet.convert_storage(...)` 可以把当前样本集复制转换到新的正式存储方案；完整转换后当前实例会自动切换到新存储
- `data_options` 现在会校验未知键和错用范围，不再静默忽略

常见误区：继续调用样本集对象上的历史 `to_h5()` 或 `to_csv()`，或者在非 H5 方案上传入 `h5_compression`。

关联场景：`04_store_and_reload`
