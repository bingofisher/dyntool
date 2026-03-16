# 数据输入与标准类型

稳定性：`Public API`

## 这页解决什么问题

这页说明如何把真实输入文件读成正式数据模型，如何检查单位，以及如何在标准类型之间保持一致的恢复与转换语义。

## 最短可运行用法

```python
from dyntool import AccelSeries

accel = AccelSeries.from_data([0.0, 0.1, -0.03], dt=0.01)
payload = accel.to_structured_payload()
print(payload["category"])
```

## 关键代码片段

--8<-- "generated/snippets/csv_unit_roundtrip.py"

## 标准类型 / 枚举 / 参数契约

- `AccelSeries.from_csv(...)`
- `AccelSeries.inspect_units(...)`
- `model_from_structured_payload(...)`
- `Metadata` 与成熟预设元数据类型

## 常见误区

- 只关心数值，不检查导入后的轴单位和值单位
- 把结构化 payload 当成长期持久化格式，而不是恢复桥接格式

## 相关示例

- 场景：[main.py](/D:/BaiduSyncdisk/13_CodeRepository/Projects/AdvDynTool/examples/10_scenarios/01_import_and_normalize/main.py)
- Recipe：[main.py](/D:/BaiduSyncdisk/13_CodeRepository/Projects/AdvDynTool/examples/90_recipes/units_and_unit_views/main.py)
- Recipe：[main.py](/D:/BaiduSyncdisk/13_CodeRepository/Projects/AdvDynTool/examples/90_recipes/metadata_patterns/main.py)

## 相关 API

- `AccelSeries`
- `Metadata`
- `model_from_structured_payload`
