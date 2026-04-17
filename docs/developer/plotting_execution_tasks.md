# plotting 执行任务（v1.2.0）

稳定性：`Internal API`

## 说明

本页记录 `v1.2.0` 中 plotting 收口任务的完成形态，保留给维护者回溯设计决策和测试边界使用。

这些任务已经在当前 `main` 上落地：

- compat facade 已删除
- `add()+plot()` 旧路径已删除
- plotter 正式输入统一为 `PlotDataset`

## 当前任务

### PT-01：重定 plotting 正式公开面

涉及文件：

- `src/dyntool/plotting/__init__.py`
- `src/dyntool/plotting/types.py`
- `docs/api/public_api.md`
- `docs/baselines/public_api_baseline.toml`

验收标准：

- 顶层导出只保留 `PlotTheme + PlotDataset + concrete plotter + PlotResult`
- compat / helper / legacy plotting 入口不再出现在正式 baseline 中

### PT-02：删除 plotting compat facade

涉及文件：

- `src/dyntool/plotting/config.py`
- `src/dyntool/plotting/_axes_frame.py`
- `src/dyntool/plotting/_axes_helpers.py`
- `src/dyntool/plotting/axes.py`

验收标准：

- 删除 `configure_zh`
- 删除 `ZhPlotConfig`
- 删除 `AxisFrame.from_file()`
- 删除 `GridFrame.from_file()`
- 删除 `LegendHelper.from_file()`
- 删除 `axes.py` facade

### PT-03：收紧 plotter 主链

涉及文件：

- `src/dyntool/plotting/plotters.py`
- `tests/test_plotting.py`
- `tests/typing_public_api.py`
- `examples/_scenario_impls.py`

验收标准：

- 删除 `add()+plot()`
- 删除 plotter 旧输入路径
- plotter 只接受 `PlotDataset`
- `PlotResult.ax` 作为正式微调出口

### PT-04：模板与样式优先级收口

涉及文件：

- `src/dyntool/plotting/config.py`
- `src/dyntool/plotting/assets/plot_theme_report.toml`
- `src/dyntool/plotting/assets/plot_theme_one_third_octave.toml`
- `docs/usage/06_plotting_config_reference.md`

验收标准：

- `PlotTheme` 只保留 `locale / figure / axes / artist / legend`
- 样式优先级固定为：运行时参数 > `PlotDataset.style` > `PlotTheme` > plotter 回退默认值
- 模板文件可被示例或测试直接读取

### PT-05：测试、示例、文档与迁移说明

涉及文件：

- `tests/test_plotting.py`
- `tests/test_public_api.py`
- `tests/typing_public_api.py`
- `docs/usage/05_plotting_logging_resources.md`
- `docs/usage/06_plotting_config_reference.md`
- `docs/systems/08_visualization.md`
- `examples/90_recipes/plot_dataset_and_plotters/README.md`

验收标准：

- 文档与示例统一写成新主链
- compat plotting 入口完全退出正式叙事
- 至少覆盖 `PlotTheme` 模板读取、同轴叠加和 `PlotResult.ax`

## 完成判据

满足以下条件即可认为 plotting 波次完成：

- `v1.2.0` 顶层 plotting 公开面已收紧
- compat facade 已删除
- `PlotDataset -> PlotTheme -> concrete plotter -> PlotResult.ax` 主链稳定
- baseline、typing、tests、docs、examples 一致
