# 单位系统

- 稳定性：`Public API`
- 适用对象：需要保证处理、保存和绘图单位一致的使用者
- 对应示例：`examples/90_recipes/units_and_unit_views/main.py`
- 对应测试：`tests/test_examples_workflows.py::test_recipe_units_and_unit_views`

## 用途

`UnitSystem` 的 `force/moment/stress/strain` 分别为力、力矩、应力及应变的默认表示，默认值为 `newton`、`newton * meter`、`pascal`、`dimensionless`。`engineering()` 对这四项沿用相同默认值；其他工程表示通过 `data_unit`、`convert_units()` 或显式 `UnitSystem` 指定。Pint 已支持 `microstrain` 和 `percent`，例如 1000 με = 0.001、1% = 0.01。无量纲应变的尺度仍须换算，不能把 1000 με 当成 1000。

单位不是附属信息，而是计算正确性的核心输入。模型读写、派生计算和图表标注都依赖单位语义。

## 求解与比较单位

计算阶段使用秒、Hz、m/s²、m/s、m；`calc_unit_system` 不改变物理结果，工程输出只在求解后转换。样本集比较采用 SI 绝对容差，普通标量表显示单位保持不变。详见 [核心库迁移说明](../developer/core_correctness_migration.md)。
