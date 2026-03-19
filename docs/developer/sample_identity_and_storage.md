# Sample / SampleSet 运行流程

稳定性：`Internal API`

## 主流程总览

```mermaid
flowchart TD
    A["Metadata 更新"] --> B["Sample 重新计算 uid"]
    B --> C{"alias 是否手工覆盖"}
    C -- "否" --> D["Sample alias 跟随 metadata.alias"]
    C -- "是" --> E["保持手工 alias"]
    D --> F["SampleSet 重写 key / 校验冲突"]
    E --> F
    F --> G["标记 storage_dirty"]
    G --> H["save / save_all 显式落盘"]
    H --> I["organize_storage 清理旧 UID"]
```

## 各层职责

### `MetadataBase`

- 负责 `uid` 与 `alias` 的生成规则
- 负责在字段赋值和 `update(...)` 时触发 change callback
- 不直接管理样本集索引

### `SampleBase`

- 聚合 metadata 与样本数据项
- 负责 alias 覆盖状态：
  - 自动 alias
  - 手工 alias
  - 显式强制回退
- 负责把 metadata 变化转成：
  - 新 `uid`
  - 新 alias
  - 向 `SampleSet` 回调 identity 变化
- 负责样本级懒加载：
  - `SampleLoadMode.LAZY`
  - `SampleLoadMode.METADATA_ONLY`
  - `ensure_loaded(...)`
  - `unload(...)`

### `SampleSetBase`

- 负责按 `uid` 管理样本
- 负责查询、批量更新和批量加载
- 负责在样本 metadata 变化后：
  - 重写 key
  - 检查 UID 冲突
  - 标记 `storage_dirty`
- 负责把公开 `categories` 规整为内部 `SampleField`，再路由到存储层读写目标

### `SampleSetStorage`

- 负责实际持久化
- 负责按 scheme 路由到底层策略
- 负责样本级 `load_sample(...)` 与集合级 `load_all(...)`
- `save_all()` 写当前状态
- `organize()` 清理不再属于当前样本集的冗余 UID 条目

## alias 规则

### metadata alias

- `MetadataBase.build_alias()` 默认返回 `uid`
- `VibrationTestMetadata.build_alias()` 生成标准业务 alias
- `from_alias()` 只在明确支持的 metadata 子类上实现

### sample alias

优先级固定为：

1. 手工 `set_alias(...)`
2. `metadata.alias`

普通刷新只更新自动 alias。  
显式强制刷新会覆盖手工 alias，并回到 `metadata.alias`。

## 加载模式如何协同

### `METADATA_ONLY`

- `SampleSet.from_storage(..., load_mode=METADATA_ONLY)` 只构造样本壳对象
- 访问未加载槽位会抛错
- 适合只做查询、投影和 metadata 修补

### `LAZY`

- 先构造样本壳对象
- 首次读取 `sample.accel` 之类的 storage slot 时自动 `ensure_loaded()`
- 适合大样本集按需读盘

### `EAGER`

- 立即加载声明目标槽位
- 适合紧接着要做批量计算

## 公开方法与内部方法的边界

### 公开方法

- 面向用户，必须稳定
- 参数和返回值必须完整标注
- docstring 必须解释实际行为、副作用和错误条件

### 内部方法

- 以 `_` 开头
- 只服务于 identity 同步、存储绑定和批处理编排
- 不写进用户文档导航，只在开发者文档说明

### 当前关键内部方法

- `SampleBase._sync_identity_state(...)`
- `SampleBase._set_alias_internal(...)`
- `SampleBase._replace_data_var_internal(...)`
- `SampleSetBase._bind_sample_internal(...)`
- `SampleSetBase._on_sample_metadata_changed(...)`
- `SampleSetBase._on_sample_identity_changed(...)`

## 为什么不能再靠直写

`sample.accel = ...`、`sample.metadata = ...`、`sampleset[uid] = sample` 的问题是：

- 无法统一标记 `storage_dirty`
- 无法统一维护 alias 覆盖状态
- metadata 改名后容易漏掉样本集重索引
- 会把持久化、内存状态和查询索引拆成多套事实来源

因此当前实现要求所有正式路径都回到聚合层方法。 
## 参数与字段补充

- `case`：工况编号，用于区分不同加载工况或试验场景。
- `point`：测点编号，表示传感器或观测位置。
- `instr`：仪器编号，表示采集通道或设备标识。
- `dir`：方向编号，表示测量方向或轴向标识。
- `record`：记录编号，表示同一工况下的记录序号。
- `timestamp`：采样开始时间或记录时间戳。
- `extra`：附加业务信息，不参与标准 identity。
- 对保留的开放参数必须写清支持键，不允许把“透传给底层”当成最终契约。
