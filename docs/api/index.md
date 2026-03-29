# API 总览

稳定性：`Public API`

正式 API 分为两层：

- 顶层对象 API
- 模块 API：`dyntool.storage`、`dyntool.plotting`、`dyntool.logging`

其中 `dyntool.storage` 除动作函数外，还正式公开存储契约类型：
`DataCategory`、`SampleDomain`、`SampleLoadMode`、`SampleSetViewOptions`、
`StorageAccessMode`、`AttrDataFormat`、`ContainerFormat`、`NameResolver`、
`StorageMode`、`StorageScheme`。

支持模块：

- `dyntool.config`
- `dyntool.resources`

内部模块如 `application.runtime_binding`、`domain.runtime` 和 schema/helper 路径归入 `Internal API`。
