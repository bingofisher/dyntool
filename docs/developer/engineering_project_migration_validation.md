# 工程项目迁移验证（`v1.2.0`）

稳定性：`Internal API`

本文记录 `v1.2.0` 版本线针对真实工程项目输入源的迁移验证方法、对比锚点与成本结论。

## 目标

本轮验证只回答以下问题：

- `v1.2.0` 对真实工程项目的迁移成本有多高
- 成本主要来自数据导入、统计导出、报告包，还是 plotting 改造

本轮不包含：

- 外部结果提取
- zip/归档层回放
- CAD、设计资料目录作为第一输入源

## 固定输入源

本轮只使用以下 3 个时程输入目录：

1. `P-R2-5`
   - `E:\22_WorkingProjects\P-R2-5_科学城别墅地铁振动测试-广州地铁院\C_数据分析\12-D_地铁波数据`
2. `P-R2-6`
   - `E:\22_WorkingProjects\P-R2-6_广州白云站高铁振动测试-铁四院\C_数据分析\D21_振动波时程数据`
3. `P-R2-7`
   - `E:\22_WorkingProjects\P-R2-7_西安环园中路车辆段振震双控设计\A_振动噪声测试\C_数据分析\D21_振动波时程数据`

## 验证主链

脚本入口：

- `scripts/validate_engineering_project_migration.py`

统一验证闭环：

1. 读取时程 `txt` 文件集合
2. 解析文件名中的工况、波号、测点、仪器、时间戳、方向
3. 组织为 `VibrationTestSample` / `VibrationTestSampleSet`
4. 执行最小评价链：
   - `eval_zvl`
   - `scalar_frame`
5. 执行存储闭环：
   - `connect_storage`
   - `save_all`
   - `load_all`
   - `compare_with`
6. 执行交付闭环：
   - `export_scalar_frame`
   - `export_report_package`

说明：

- 原始计划里写的是 `DefaultSample / DefaultSampleSet`
- 实际验证改为 `VibrationTestSample / VibrationTestSampleSet`
- 原因是这 3 个工程项目的文件命名天然携带 `case / point / instr / dir / record / timestamp` 六元业务键，直接映射到 `VibrationTestMetadata` 更稳，也更贴近真实测试项目迁移

## 输入文件形态

### `P-R2-5`

- 文件示例：`C-1_W-DTN10_P-B1_I-167_T-20250508102659_D-001.txt`
- 内容形态：双列，带表头
  - `时间 (s),加速度 (m/s^2)`
- 结论：
  - 时程自带时间列
  - 不需要额外补 `dt`

### `P-R2-6`

- 文件示例：`C-D_W-D1_P-A2_I-166_T-20251026113714_D-001.txt`
- 内容形态：单列，带表头
  - `加速度`
- 结论：
  - 项目侧需要固定 `dt = 0.01`

### `P-R2-7`

- 文件示例：`C-L10-D_W-31_P-A1_I-166_T-20260126050759_D-001.txt`
- 内容形态：单列，带表头
  - `加速度`
- 结论：
  - 项目侧需要固定 `dt = 0.002`

## 结果层对比锚点

### `P-R2-5`

- 结果层：
  - `工况筛选表.csv`
  - `地铁波分割表.csv`
  - `Z振级数据.csv`
  - `分频最大振级数据.csv`
  - `测点数据汇总.xlsx`
- 直接主键对比锚点：
  - `Z振级数据.csv`
- 结论：
  - 原始文件名可直接对齐 `Z振级数据.csv`
  - `地铁波分割表.csv` 中的 `地铁波` 序号属于派生编号，不是原始文件名直出字段

### `P-R2-6`

- 结果层：
  - `Z21_振动波分割表.csv`
  - `Z22_振动波信息表.csv`
  - `D31_Z振级数据.csv`
  - `D32_三分之一分频振级数据-合并.csv`
  - `D90_测试报告数据.xlsx`
- 直接主键对比锚点：
  - `D31_Z振级数据.csv`
- 结论：
  - 原始文件名可直接对齐 `D31_Z振级数据.csv`
  - `Z21/Z22` 属于另一层结果组织，不是最短迁移闭环的第一对比锚点

### `P-R2-7`

- 结果层：
  - `Z21_振动波分割表.csv`
  - `D31_Z振级数据.csv`
  - `D90_测试报告数据.xlsx`
- 实际盘点结果：
  - `Z22_振动波信息表.csv` 在当前目录下不存在
- 直接主键对比锚点：
  - `Z21_振动波分割表.csv`
- 结论：
  - 原始文件名可直接对齐 split 表
  - 不能直接对齐 `D31_Z振级数据.csv`
  - `D31` 使用了归一化后的工况/波号键，需要项目特定适配器

## 实际运行命令

```powershell
uv run python -B scripts/validate_engineering_project_migration.py `
  --subset-size 24 `
  --output-dir .pytest_tmp/engineering_project_migration_validation
```

生成物位置：

- `.pytest_tmp/engineering_project_migration_validation/migration_matrix.json`
- `.pytest_tmp/engineering_project_migration_validation/<project-id>/scalar_frame.xlsx`
- `.pytest_tmp/engineering_project_migration_validation/<project-id>/report_package/`

## 实测迁移矩阵

| 项目 | 输入文件数 | 解析覆盖率 | 直接结果层对齐 | split 表对齐 | reporting 可替代现有导出链 | plotting 是否主成本源 | 迁移成本 | 预计人天 |
| --- | ---: | ---: | ---: | ---: | --- | --- | --- | --- |
| `P-R2-5` | 840 | 100% | `Z振级数据.csv` 840/840 | `0/280` | 是 | 否 | 低 | `0.5-1.5` |
| `P-R2-6` | 490 | 100% | `D31_Z振级数据.csv` 490/490 | `0/490` | 是 | 否 | 中 | `2-4` |
| `P-R2-7` | 184 | 100% | `D31_Z振级数据.csv` 0/184 | `Z21_振动波分割表.csv` 184/184 | 是 | 否 | 高 | `4-7` |

## 结论

### 哪类项目最适合先迁

优先迁移：

- `P-R2-5` 这一类原始文件名可直接映射到结果层主键、且时程格式清晰的标准测试项目

第二批迁移：

- `P-R2-6` 这一类批量规模大、但原始命名与结果层主键仍直接一致的项目

最后迁移：

- `P-R2-7` 这一类结果层已经做过归一化改写、需要项目特定适配器的项目

### plotting 是否是主要成本源

本轮 3 个项目的结论一致：

- plotting 不是主要迁移成本源
- 主要成本来自：
  - 输入命名解析
  - 结果层主键对齐
  - 统计表与报告包目录的替换组织

### `dyntool.reporting` 的收益

本轮 3 个项目的结论一致：

- `dyntool.reporting` 可以直接替代“统计表导出 + 报告素材目录拼装”的大部分现有脚本
- 真正需要项目侧补的，是输入整理和结果层对比适配，而不是新的导出 API

## 建议

建议按以下顺序推动真实项目迁移：

1. `P-R2-5`
   - 用于冻结输入命名解析和最小闭环模板
2. `P-R2-6`
   - 用于验证大样本集批量存储、统计导出和报告包吞吐
3. `P-R2-7`
   - 用于补齐“结果层归一化适配器”模式

不建议：

- 在 `v1.2.0` 未冻结为 `rc/tag` 前，让工程项目直接跟随 branch head
- 直接从 `P-R2-7` 这类高复杂度项目开始
