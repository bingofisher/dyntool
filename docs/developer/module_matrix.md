# 模块矩阵

`Internal API`

## 当前分层

- `application`：面向顶层门面与运行时组装
- `domain`：领域对象、枚举、schema 与运行时解析
- `compute`：可复用计算与信号处理算法
- `infrastructure`：存储与持久化实现

## domain 内部正式子包

- `domain.metadata`：元数据对象与 schema
- `domain.models`：时程、谱与评价结果对象
- `domain.limits`：规范驱动限值对象、标准枚举与内部注册表
- `domain.samples`：样本、样本集与工作流命名空间
- `domain.runtime`：领域层运行时解析与绑定

## 说明

- `domain.models` 与 `domain.limits` 并列存在，避免把规范表对象混入评价结果命名空间
- `domain.limits.registry` 属于 `Internal API`
- 历史兼容层只允许删除或归档，不再新增业务功能
