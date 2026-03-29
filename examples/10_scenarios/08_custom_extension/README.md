# 自定义扩展
稳定性：`Internal API`

这个示例演示如何在仓库外部定义一套对标 `vibtest` 的自定义领域对象，并验证它能继续复用现有主链。

- 输入：外部 `Metadata / DefaultSample / DefaultSampleSet`、示例 `JerkSeries`、同一组加速度数据
- 输出：模型 CSV、外部样本持久化结果、roundtrip 恢复结果和绘图结果
- 对应文档：`docs/developer/custom_extension.md`

示例重点不是新增正式公共扩展协议，而是展示当前可行的内部方案：

- `compute` 作为主路径
- `calc_*` / `eval_*` 作为兼容实现层
- consumer 侧 registry bridge 负责 payload 恢复
- external 与内置 `vibtest` 的结果对比验证
