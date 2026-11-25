# 规范驱动限值模型

`Internal API`

## 目标

`domain.limits` 用于承载“按规范而不是按属性分类”的限值对象，让规范条款、场景和值域结构在领域层可追踪、可查询。

## 当前结构

- `ZVLLimit`：标量 Z 振级限值
- `OTOVLLimit`：1/3 倍频程限值曲线
- `FPVDVLimit`：四次方振动剂量值标量限值
- `FDMVLLimit`：分频最大振级标量限值，支持 JGJ/T 170—2009 表 4.0.1
- `*LimitStandard`：按评价类型划分的公开标准枚举
- `registry.py`：标准条款、资源键和场景解析规则注册表

## 设计约束

- 限值对象通过 `ScalarLimitBase` 或 `CurveLimitBase` 继承 `DataModelBase`，不复用 `*Eval` 的结果字段形状
- `from_standard(...)` 返回单个已选场景的限值对象
- 标准使用枚举，场景使用字符串
- 条款号内置在注册表中，对外暴露为只读元信息

## 标准编号及严格恢复

稳定性：标准枚举及其值、已有模型恢复入口属于 `Public API`；恢复校验属于 `Private / implementation detail`。

按评价类型定义 `ZVLLimitStandard`、`OTOVLLimitStandard`、`FPVDVLimitStandard` 和 `FDMVLLimitStandard`，每部标准为枚举成员。成员名使用下划线，值使用“标准代号 空格编号-年份”，例如 `JGJ_T_170_2009 = "JGJ/T 170-2009"`。同一标准涉及多个评价指标时分别注册对应条款，不能跨评价族传入同名枚举。

`ZVLLimitStandard.GB_10070_1988.value` 为 `GB 10070-1988`。经确认不提供旧编号兼容：字典、结构化载荷、DataFrame / xarray 属性及 H5 恢复均拒绝 `GB_10070-1988`，不猜测其他编号、年份或别名，失败不修改源文件。`from_standard()` 等入口仍只接受相应枚举。资源键、CSV 资源目录和 H5 字段布局保持不变；资源目录中的下划线只是既有路径名称，不是可恢复的标准值。

带旧编号的限值不能直接读取，需核对其实际标准、场景和数值后显式重新构造，并保存为新目标。本次不自动转换或批量重写历史仓库；这一决定只针对标准编号，不取消其他已支持载荷形态的读取合同。

## 分频最大振级接入

`FDMVLLimitStandard.JGJ_T_170_2009` 注册到既有 `LimitStandardSpec`，复用标量场景解析器。资源键为 `limit_building_fdmvl`，规范、场景和单位通过同一链路解析，没有新增平行评价入口或运行时。

`FDMVLLimit` 继承 `ScalarLimitBase`，字段为 `fdmvl`，默认单位为 `decibel`，没有频率轴。其含义是表 4.0.1 的单个分频最大振级阈值，不能把它建成未计权倍频程曲线。`PlotDataset.add_limit(limit, axis=...)` 已支持标量广播，不新增绘图实现。H5 沿用现有字段路径，后端通过 UTF-8 字符串读写标准、中文场景、条款和资源键；单位检查继续只读取属性。

评价计算和工程测量前提不由限值对象隐式执行。使用 JGJ/T 170 口径时需明确选择区域、昼夜、4–200 Hz 频率范围和铅垂向记录，并核对有效列车及测点汇总等测量要求；本次只接入该版标准值，不更改 FDMVL 求解器的默认频率范围或数值算法。

## 原占位接口调整

经确认，原曲线占位结构改为标量模型：`from_data()` 不再接受 `freq`，`fdmvl` 参数改为单个浮点数；`from_standard()` 的参数和返回类保持。默认字段单位只有 `fdmvl`，`to_pandas()` 返回单行数值表，绘图频率轴由调用者传入。

原占位标准枚举没有成员且没有内置标准，不能通过原正式标准入口构造有效规范对象。若项目自行构造过含频率轴的扩展载荷，需先明确其单个阈值，再通过新 `from_data()` 构造；`from_dict()` 拒绝含 `freq` 或多个限值的曲线，不能默认取首值。非恒定曲线不能直接当作本标准的分频最大振级阈值。

旧版程序的空 `FDMVLLimitStandard` 无法识别新增的 JGJ/T 170 标准成员，读取新限值需使用本次实现；既有评价结果和样本仓库的类别与布局没有变化。

H5、字典和结构化载荷保存并恢复规范来源；`to_pandas()` 返回独立数值表，`df.attrs` 自动携带标准、场景、条款、资源键及可选追溯，`from_pandas()` 沿既有接口恢复。外部表仍需显式提供规范来源，缺少追溯时保持来源未知。属性不是 DataFrame 数值编辑的自动追踪器；外部改写数值后应移除原 `_dyntool` 依据。CSV 不承载这些元信息，限值对象往返使用 H5。

所有标量限值的字典恢复必须恰好有一个值；缺值不补零，空值和多个值不截取首项。DataFrame 必须恰好一行。`to_xarray()` 返回保持零维标量或一维曲线的独立 `Dataset`，规范来源和可选追溯放在 attrs，字段单位放在各字段属性；`from_xarray()` 恢复带这些属性的 Dataset 或 DataArray。外部编辑数值后同样需移除原 `_dyntool`；原对象和已经恢复的模型不随快照编辑而改变。

| 功能 | 示例 | 测试 |
|---|---|---|
| 十个区域昼夜阈值、枚举和场景校验 | `examples/10_scenarios/07_resource_driven_eval/main.py` | `tests/test_limits.py`、`tests/test_resources.py` |
| 标量序列化、H5 及中文规范元信息 | 同上 | `test_fdmvl_scalar_roundtrips_through_registry_and_h5` |
| 既有绘图入口广播和完整示例 | 同上 | `test_fdmvl_scalar_uses_existing_plot_limit_broadcast`、`tests/test_examples_systems.py::test_scenario_resource_driven_eval` |
| 原曲线拒绝及单位表示转换 | 同上 | `test_fdmvl_explicit_scalar_preserves_units_and_rejects_old_curves` |
| 标准编号统一、旧值拒绝及四类限值表往返 | 同上 | `test_standard_identifiers_are_canonical_and_legacy_value_is_rejected`、`test_all_standard_values_use_canonical_identifiers`、`test_limit_dataframe_preserves_source_and_is_independent` |
| 标量完整性及 xarray 形状、单位、来源往返 | 同上 | `test_scalar_limits_reject_missing_empty_or_multiple_values`、`test_scalar_limit_dataframe_requires_exactly_one_row`、`test_limit_xarray_preserves_shape_units_source_and_snapshot` |

## 稳定性

- `ZVLLimit`、`OTOVLLimit`、`FPVDVLimit`、`FDMVLLimit`：`Public API`
- `domain.limits.registry` 与公共基类：`Internal API`

## 本次接入验证（2026-10-05）

稳定性：本节为 `Private / implementation detail` 验证记录。

- Python 3.13.12 和最低支持 Python 3.12.12：限值、资源和正式示例定向回归均为 29 项通过。
- 完整回归包含现有 GUI：967 项通过、3 项跳过、1 项既有环境失败，耗时 232.57 秒。唯一失败为 `tests/test_cleanup_guards.py::test_repository_has_no_mkdocs_build_artifacts` 对工作区原有 `.ruff_cache` 的断言；保留用户缓存，不删除或放宽检查。
- 九项仓库守卫、Ruff check/format（含 GUI 和维护脚本）通过；Pyright 0 错误、0 警告。严格文档构建按 AGENTS.md 执行，输出在已忽略目录。
- 使用当前工作区已有版本号构建 wheel，在独立 Python 3.12.12 锁定依赖环境安装；从仓库外及 site-packages 导入，验证十场景资源、62 dB 标量、中文规范元信息 H5 往返和单位检查。没有发布版本。

验证沿用 TEMP 下的隔离依赖环境，未改用户 `.venv` 或 `.venv_local`。本次原始门禁与回归日志位于 `.pytest_tmp/fdmvl-*.log`，示例生成物位于相应 pytest 临时目录。
