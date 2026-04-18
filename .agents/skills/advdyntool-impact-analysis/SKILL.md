# AdvDynTool 影响分析

在开始实现前，先扫描受影响层、公开面、单位语义、存储语义、文档联动、示例联动、测试联动和质量门禁。

## 最小输出
- 改动清单
- 风险清单
- 必须同步的 README / ARCHITECTURE / docs / examples / tests
- 需要运行的质量门禁

## 特别关注
- 是否触及 `src/dyntool/__init__.py`
- 是否触及公开模块 API
- 是否触及单位或存储规则
- 是否触及分层边界
