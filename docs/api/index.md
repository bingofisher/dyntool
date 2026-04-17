# API 总览

稳定性：`Public API`

正式 API 分为两层：

- 顶层对象 API
- 模块 API：`dyntool.storage`、`dyntool.plotting`、`dyntool.logging`、`dyntool.reporting`

其中 `dyntool.storage` 除动作函数外，还正式公开存储契约类型：
`DataCategory`、`SampleDomain`、`SampleLoadMode`、`SampleSetViewOptions`、
`StorageAccessMode`、`AttrDataFormat`、`ContainerFormat`、`NameResolver`、
`StorageMode`、`StorageScheme`。

支持模块：

- `dyntool.config`
- `dyntool.resources`

正式样本集对象通过 `SampleSetBase` 这一实现基类上的薄委托，把统计导出和报告包导出交给 `dyntool.reporting`。

内部模块如 `application.runtime_binding`、`domain.runtime` 和 schema/helper 路径归入 `Internal API`。
