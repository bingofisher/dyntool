# 建筑室内振动与隔振效果展示

稳定性：核心计算与存储使用 `Public API`；项目与桌面启动属于 GUI `Internal API`；生成器和场景配置为 `Private / implementation detail`。

这是正式维护的 GUI 场景示例。数据明确标注为合成，不代表实测建筑、建筑传播模型或隔振装置仿真，不作工程合格判定。

在仓库根目录运行：

```powershell
uv run --group gui python -B -m examples.10_scenarios.09_gui_building_showcase.main --open
```

省略 `--open` 时只生成项目，不启动窗口。可用 `--output-dir tmp/my_building_showcase` 指定空目录；目标非空时拒绝覆盖。默认在 `tmp/gui_showcase/` 下创建新目录。

## 场景与生成物

- 36 样本：4 工况（背景、交通、设备隔振前、设备隔振后）× 3 楼层（地下室、二层室内、六层室内）× X/Y/Z。
- 固定种子 20261004，每条 8192 点、256 Hz、名义时长 32 秒；单位为秒和 m/s²。
- 背景为低幅噪声和 3 Hz 分量，交通为 8/16 Hz 分段事件，设备为 25/50 Hz 分量。楼层系数为 0.6/1.0/1.4，方向系数为 0.7/0.8/1.0。隔振后严格为对应前值的 0.35 倍。
- 全部样本已有频谱、响应谱、ZVL 和 OTOVL。评价为 0.5–80 Hz、1 秒窗口；ZVL 使用统一 WK 权重，仅用于展示。响应谱为 0.05–2 秒的 40 个对数间隔点。
- `building.dyntool.json` 为项目；`raw_data/` 和 `raw_csv/` 为原始数据；`analysis_data/` 为可写 SQLite/H5 分析仓库；`exports/` 包含标量 CSV 和 4 张实际结果对比图片；`manifest.json` 记录配置和真实子集 UID。

## 操作路径

1. `--open` 自动进入图形绘制并显示二层 Z 向隔振前后时程。来源切换到 `freqspec`、`otovl` 或 `respspec`，点击“渲染”。
2. 在“导入与筛选”查看工况和楼层子集，修改筛选条件或保存新子集。
3. 在“数据处理”选择方法和范围；重算已有结果必须开启覆盖。未预计算的 FDMVL、FPVDV 可按界面参数另行体验。
4. 保存图片后，先保存分析数据（Ctrl+Shift+S），再保存项目（Ctrl+S）。这些操作不会写回原始仓库。
5. 用普通“打开项目”读取 JSON 后，数据与子集仍可使用，点击“渲染”重新生成画布。

项目引用目前使用绝对路径，移动目录后需在新位置重新生成。时间戳为固定演示时间，不是采集时间。现有桥梁和通用占位演示保持原行为。

回归：`tests/test_gui_building_showcase.py`；正式 smoke 不打开窗口。
