# 存储并回读
任务目标：完成 `from_accel -> calc_freqspec/calc_respspec -> save/load -> plot` 的最小闭环，并确认派生谱结果会随样本集一起持久化。

## 这条场景覆盖什么
- `DefaultSampleSet.save()` / `save_all()`
- `DefaultSampleSet.from_storage(...)`
- `StorageScheme.SET_H5`
- `freqspec` / `respspec` 的持久化与回读
- 回读后继续进入 plotting 主链

## 运行命令

```powershell
python examples/10_scenarios/04_store_and_reload/main.py
```

## 输入

- 示例脚本内部构造的一条振动加速度样本
- 由该样本计算得到的 `freqspec` 与 `respspec`

## 关键 API
- `DefaultSample.calc_freqspec(source=...)`
- `DefaultSample.calc_respspec()`
- `DefaultSampleSet.save()`
- `DefaultSampleSet.from_storage()`
- `PlotTheme.default()`
- `PlotDataset.from_model(...)`
- `FramePlotter(theme=theme).plot_dataset(dataset)`

## 预期结果
- 生成样本集 H5 文件
- 回读后的样本仍然包含 `freqspec`
- 回读后的样本仍然包含 `respspec`
- 生成一张回读后数据的绘图文件

## 输出

- 样本集 H5 存储文件
- 回读后验证 `freqspec` / `respspec` 已恢复的运行结果
- 一张基于回读样本绘制的 PNG 图片

## 对应测试

`tests/test_examples_systems.py::test_scenario_store_and_reload`
