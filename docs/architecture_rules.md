# 架构与规则

稳定性：`Internal API`

项目采用 `application -> domain/compute` 与 `infrastructure -> domain` 的分层约束。

## 核心规则

- `compute` 不反向依赖 `domain`
- 历史模块只允许删除或归档，不再新增业务功能
- 正式公开面保持最小且稳定
- 文档、示例、测试和公开 API 说明必须同步
- 仓库文本文件统一使用 UTF-8 无 BOM 与 LF
- Python 程序中的文本读写必须显式写出 `encoding="utf-8"`

## 类型与参数规则

- 公开 API 与主线核心实现禁止用 `object` 作为可替代真实类型的兜底注解。
- 稳定第三方对象优先使用具体类型，例如 `Axes`、`Figure`、`Artist`、`DataFrame`。
- 动态边界优先使用 `Protocol`、`Callable`、枚举、dataclass、`TypedDict` 或泛型。
- 裸 `**kwargs` 只允许出现在少量底层透传边界；必须改成具名容器或在 docstring 中列出支持键。
- 正式开放参数容器名固定为 `csv_read_options`、`provider_options`、`extras`。
- 兼容层接口必须显式标注稳定性与迁移定位；当正式替代路径稳定后，应及时删除历史 plotting payload 一类兼容入口。

## Docstring 规则

- 公开模块、公开类、公开函数、公开方法以及主线核心函数统一使用中文 Google 风格 docstring。
- 最低要求包含：功能概述、`Args`、`Returns`、`Raises`、`Notes` 或副作用说明。
- 参数说明必须写出实际业务意义与行为影响，不能只写抽象名词。
- 兼容层接口的 docstring 也必须明确写出“兼容层入口”或 `Internal API`，不能伪装成正式主用法。
