# 建筑室内振动与隔振效果展示

稳定性：核心计算与存储为 `Public API`，GUI 项目与展示启动为 `Internal API`，生成器及场景配置为 `Private / implementation detail`。

该展示不需要用户提供数据。它生成完整的合成建筑振动项目，所有数组、子集和派生结果均实际存在，可用于计算、绘图、保存及重新打开。旧 `--demo bridge|generic` 仍是占位界面演示，不替代本项目。

## 生成并打开

在仓库根目录执行：

```powershell
uv run --group gui python -B -m examples.10_scenarios.09_gui_building_showcase.main --open
```

生成但不打开窗口：

```powershell
uv run --group gui python -B -m examples.10_scenarios.09_gui_building_showcase.main --output-dir tmp/building_showcase
```

输出目标必须为空，默认在 `tmp/gui_showcase/` 下创建新目录。生成器先暂存原始数据、计算结果与项目，通过仓库 deep 检查后才交付；生成失败不交付可打开的半成品。不会覆盖已有项目。

## 数据和结果

36 样本覆盖背景、交通、设备隔振前、设备隔振后，以及地下室、二层室内、六层室内的 X/Y/Z 三方向。固定种子为 20261004，每条 256 Hz、8192 点，名义时长 32 秒。实际最后时间点为 8191/256 秒；轴和值单位为秒和 m/s²。

背景包含低幅噪声与 3 Hz 分量，交通叠加三段 8/16 Hz 事件，设备叠加 25/50 Hz 分量。楼层与方向使用固定幅值系数。对应隔振后信号严格为前值的 0.35 倍，便于检查结果与体验对比。

所有样本预计算频谱、响应谱、ZVL 和 OTOVL。评价窗口 1 秒、范围 0.5–80 Hz，ZVL 统一使用 WK 权重；响应谱周期为 0.05–2 秒的 40 个对数间隔点。权重和幅值仅用于展示，不构成建筑规范应用建议或合格判定。时间戳为固定演示时间，不是采集时间。

| 生成物 | 用途 |
|---|---|
| `building.dyntool.json` | 普通 GUI 项目文件 |
| `raw_data/`、`raw_csv/` | 原始加速度仓库和带单位 CSV |
| `analysis_data/` | 采用现有 SQLite v2/H5 的可写分析仓库 |
| `exports/scalar_results.csv` | 实际评价值、PGA 和 RMS 等标量结果 |
| `exports/*_compare.png` | 时程、频谱、三分之一倍频程和响应谱对比图片 |
| `manifest.json` | 合成标记、配置和实际子集 UID |

## 操作路线

`--open` 自动进入图形页并渲染二层 Z 向隔振前后时程。切换来源 `freqspec`、`otovl` 或 `respspec`，点击渲染查看对应差异。多样本模型图最多 12 条，楼层子集为 12 条，工况子集为 9 条。

在导入与筛选页查看或修改四个工况、三个楼层及隔振对比子集。在数据处理页选择方法、范围并执行；已有结果重算须启用覆盖。FDMVL、FPVDV 没有预计算，可按界面参数另行体验。

图片通过当前图形保存操作导出。分析数据和项目分别保存：先 Ctrl+Shift+S，再 Ctrl+S。后续计算和保存使用分析仓库，原始仓库保持原值；不额外提供整批回滚保证。

用普通“打开项目”重开 JSON 后，选择多样本对比和当前子样本集，再点击渲染恢复数据并重建画布。项目仍使用绝对路径引用，移动目录后应重新生成；本示例不改变项目 JSON 或核心存储格式。

## 功能、示例与测试映射

| 功能 | 示例入口 | 测试 |
|---|---|---|
| 固定种子、单位及隔振比例 | 场景生成入口 | `test_deterministic_matrix_and_known_isolation_scale` |
| 真实仓库、预计算及子集 | 同一入口，不加 `--open` | `test_generated_project_has_real_results_and_subsets` |
| 默认绘图、来源切换和图片保存 | `--open` | `test_showcase_renders_switches_and_exports` |
| 覆盖重算、另存和关闭保护 | 数据处理及文件菜单 | `test_recompute_save_reopen_preserves_raw_repository` |

示例位于 `examples/10_scenarios/09_gui_building_showcase/`，测试位于 `tests/test_gui_building_showcase.py`。生成 smoke 不启动桌面窗口。
