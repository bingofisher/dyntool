# 文档规范

`Internal API`

仓库中的模块、类、公开函数与公开方法统一使用中文 Google 风格 docstring。

## 规则

- 模块 docstring 说明职责边界
- 类 docstring 优先写 `Attributes`
- 函数和方法优先写 `Args`、`Returns`、`Raises`
- 重点入口再补 `Notes`
- 关键变量优先写在 docstring、字段注释或 `#:` 说明中

## 枚举说明

- 只有真实枚举类才使用“枚举值说明/影响”
- 普通字符串取值或策略分支放在参数说明与 `Notes` 中
