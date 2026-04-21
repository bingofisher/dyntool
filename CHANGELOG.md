# 更新日志

稳定性：`Public API`

## v1.2.1 - 2026-04-21

### 版本线定位

- `v1.2.0` 已作为当前 `1.2.x` 稳定线基线发布
- `v1.2.1` 已作为当前 `1.2.x` 稳定基线正式发布
- 本次正式发布聚焦 plotting 补丁修复、公开配置补齐和工程治理升级
- 前一稳定版本为 `v1.2.0`
- 正式发布事实以对应 `v1.2.1` git tag 为准

### plotting 公开配置补齐

- `PlotTheme` 正式补齐 `grid.x.major / grid.x.minor / grid.y.major / grid.y.minor`
- `axis.x / axis.y` 连续轴配置补齐 `major_step`、`minor_step`、`scientific_*`
- `axis.x.label / axis.y.label` 正式纳入模板 schema
- `OneThirdOctavePlotter` 正式支持 `axis.y = ContinuousAxisSpec`
- `SongTNR` 全局字体快捷入口与主题应用链统一到正式 plotting 主链

### reporting / storage / logging 内部聚合

- `reporting` 内部实现改为 facade + builders / export / writers 结构
- sample-set storage 的重复摘要逻辑收敛为共享私有模块
- logging provider 的运行时状态收进私有 runtime，公开 API 不变

### 仓库治理与文档收口

- 新增仓库治理检查与 helper 结构检查，统一命令口径、正式 schema 口径和内部 helper 反模式治理
- 补齐仓库级 usage guide skill 与相关校验
- 文档、示例、public API baseline、typing 与回归测试同步对齐当前正式口径

## v1.2.0 - 2026-04-18

- plotting 正式主链固定为 `PlotDataset -> PlotTheme -> concrete plotter -> PlotResult.ax`
- `dyntool.reporting` 正式纳入公开面
- storage / runtime 内部边界进一步收紧
- domain helper 结构继续收口，但不改变正式对象 API

## v1.1.2 - 2026-04-04

- 完成 `SET_SQLITE_H5` v2 正式化、样本集主链收口
- 同步测试、baseline、性能基线与仓库门禁

## v1.1.1 - 2026-03-30

- 公开口径回正，统一 `DefaultSample / DefaultSampleSet`
- 补齐 storage 主链说明与文档规则修正

## v1.1.0 - 2026-03-19

- 完成公开面重整
- 资源模块统一到 `dyntool.resources`
- plotting 固定为 `matplotlib` 静态绘图路径
