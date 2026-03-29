# AdvDynTool 综合收敛复核入口

复核任何中大型收敛阶段时，固定按以下顺序读取：

1. `task_plan.md`
2. 对应阶段文件
3. `findings.md`
4. `progress.md`
5. 本阶段涉及的代码、测试、README、ARCHITECTURE 与文档页面

## 复核重点

- 是否偏离当前 `dyntool` 正式公开面。
- 是否重新引入已移除的历史入口。
- 是否破坏单位优先级、存储口径或默认行为。
- 是否破坏分层约束。
- 是否遗漏 README、ARCHITECTURE 与 MkDocs 同步。
- 是否存在未补齐的测试或门禁缺口。

## 建议结合的技能

- `advdyntool-impact-analysis`
- `advdyntool-doc-sync`
- `advdyntool-quality-gates`
- `software-architecture`

## 复核结论标准

- 发现公开 API、单位、存储、默认行为或分层规则问题时，不得判定为完成。
- 文档未同步时，不得判定为完成。
- 验证证据不足时，不得判定为完成。
