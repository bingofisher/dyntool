# AdvDynTool

稳定性：`Public API`

AdvDynTool 是一个面向动力学计算、振动处理与评价的 Python 库。当前正式公开面采用“两层结构”：

- 顶层对象 API：`AccelSeries`、`Metadata`、`Sample`、`SampleSet` 以及常用结果对象、限制对象和枚举
- 动作模块 API：`dyntool.storage`、`dyntool.plotting`、`dyntool.logging`
- 正式支持模块：`dyntool.config`、`dyntool.resources`

当前发布版本：`v1.1.0`

更新记录见 [CHANGELOG.md](CHANGELOG.md)。

## 推荐入口

## 存储补充约定

- `dyntool.storage` 的公开调用方式保持不变
- 单模型 H5、单样本 H5、样本集 H5 默认启用 `gzip` 压缩
- 默认压缩级别为 `4`
- 样本/样本集 `data_options` 现在是正式契约，未知键、错用范围和非法压缩参数会直接报中文错误
- 大样本集如需加快 `load_mode=METADATA_ONLY/LAZY`、metadata 导出与索引读取，可使用 `StorageScheme.SET_SQLITE_H5`
- `SampleSet.convert_storage(...)` 可把当前样本集复制转换到另一种正式 `StorageScheme`；完整转换成功后会自动切换当前实例绑定到新存储

```python
import dyntool.resources as dt_resources
import dyntool.storage as dt_storage
from dyntool import Sample, SampleDomain, VibrationTestMetadata

sample = Sample.from_accel_data(
    [0.0, 0.12, -0.03],
    dt=0.01,
    sample_domain=SampleDomain.VIBRATION_TEST,
    metadata_cls=VibrationTestMetadata,
    case="demo",
    point="P1",
    instr="ACC-01",
    dir="Z",
    record="R1",
    timestamp="2026-03-08 12:00:00",
)
sample.eval_zvl(overwrite=True, freq_range=(2.0, 60.0))
dt_storage.save_sample(sample, "output/sample.h5")
freqs, _ = dt_resources.center_freqs((2.0, 80.0))
print(freqs[:3])
```

## 当前正式边界

- 顶层只保留对象、结果对象、限制对象和必要枚举
- 动作统一走模块，不再恢复 `DynTool` 门面
- plotting 正式固定为 `matplotlib` 静态路径
- `custom_extension` 只作为 `Internal API` 示例保留

## 文档入口

- [文档首页](docs/index.md)
- [公开 API](docs/api/public_api.md)
- [示例总览](docs/examples_overview.md)
- [架构说明](ARCHITECTURE.md)

## 文档与质量命令

```powershell
uv run mkdocs build --strict
uv run python scripts/check_text_quality.py
uv run python scripts/check_docstring_coverage.py
uv run python scripts/check_mkdocs_site.py
uv run pytest -q
```
