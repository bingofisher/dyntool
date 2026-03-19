# 规范驱动限值模型

`Internal API`

## 目标

`domain.limits` 用于承载“按规范而不是按属性分类”的限值对象，让规范条款、场景和值域结构在领域层可追踪、可查询。

## 当前结构

- `ZVLLimit`：标量 Z 振级限值
- `OTOVLLimit`：1/3 倍频程限值曲线
- `FPVDVLimit`：四次方振动剂量值标量限值
- `FDMVLLimit`：分频振级限值结构占位
- `*.Standard`：公开标准枚举
- `registry.py`：标准条款、资源键和场景解析规则注册表

## 设计约束

- 限值对象直接继承 `DataModelBase`，不复用 `*Eval` 的结果字段形状
- `from_standard(...)` 返回单个已选场景的限值对象
- 标准使用枚举，场景使用字符串
- 条款号内置在注册表中，对外暴露为只读元信息

## 稳定性

- `ZVLLimit`、`OTOVLLimit`、`FPVDVLimit`、`FDMVLLimit`：`Public API`
- `domain.limits.registry` 与公共基类：`Internal API`
