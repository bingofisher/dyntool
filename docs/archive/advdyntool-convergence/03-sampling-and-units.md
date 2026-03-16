# 阶段 03：采样契约与单位优先级

## 阶段目标
- 固化不规则时间轴、显式重采样和统一单位优先级契约。

## 前置依赖
- `02-sample-model-construction.md`

## 命中 skills
- `writing-plans`
- `planning-with-files`
- `scipy-best-practices`

## 3-subagent 角色分工
- 规划协调：拆分采样 API、重采样 API、单位优先级和测试清单
- 架构评审：保证契约落在恰当层级，不把实现细节塞回 facade
- 数值评审：主审采样检查、显式重采样和单位传播

## Subagent Proposals
### Planning Coordination
- 先补采样状态 API，再统一处理与评估入口的前置校验。

### Architecture Review
- 不新增额外公开时间序列类型，直接增强现有 `TimeSeries` 体系。

### Numerical Review
- 统一要求“依赖均匀采样的方法必须先显式重采样”。

## Cross Review
### Planning Coordination
- 赞同现有模型增量增强，否决另起新的时间序列类型树。

### Architecture Review
- 赞同单位优先级 helper，否决各处继续直接回退全局默认。

### Numerical Review
- 赞同统一采样契约，否决自动重采样继续运行。

## Consensus
- 采样约束和单位优先级先冻结为统一 helper，再扩散到 processing、evaluation 和存储。

## Files to modify
- `src/dyntool/domain/models/time_series.py`
- `src/dyntool/domain/constants.py`
- `src/dyntool/application/processing_service.py`
- `src/dyntool/application/evaluation_service.py`
- `src/dyntool/application/options.py`
- `README.md`
- `ARCHITECTURE.md`
- `tests/test_time_series*.py`
- `tests/typing_public_api.py`

## Files to create
- 可选：`src/dyntool/domain/unit_policy.py`
- 可选：`tests/test_unit_policy.py`

## Files to verify
- `src/dyntool/compute/signals.py`
- `src/dyntool/compute/metrics.py`
- `src/dyntool/compute/solvers.py`

## 文件级操作步骤
1. 目标文件：`src/dyntool/domain/models/time_series.py`
   - 变更目的：增加 `is_uniform_time`、`sampling_info()`、`require_uniform_time()`、`resample_uniform(...)`、`resample_like(...)`
   - 预期影响：不规则时间轴成为显式可检查状态
   - 验证：不规则时间轴对象可建模且能正确报错
2. 目标文件：`src/dyntool/domain/constants.py` 或新 helper
   - 变更目的：统一单位优先级解析
   - 预期影响：构造、转换、读取和保存统一遵守 `输入指定 > 模型默认 > 全局默认`
   - 验证：新增优先级测试用例
3. 目标文件：`src/dyntool/application/processing_service.py`、`src/dyntool/application/evaluation_service.py`
   - 变更目的：统一前置采样和单位检查
   - 预期影响：依赖均匀采样的方法先显式校验
   - 验证：未重采样时能稳定给出中文报错

## 测试步骤
- 运行不规则时间轴建模和重采样测试
- 运行单位优先级测试
- 验证 `eval_zvl`、`freqspec`、`respspec` 等入口在未重采样时稳定报错

## 完成定义
- 采样状态 API 可用
- 重采样是显式动作
- 单位优先级在模型、sample、sampleset、读取、转换中一致

## 回滚与风险
- 若重采样接口设计与现有构造 API 冲突，优先保留采样契约正确性，不牺牲显式性。

