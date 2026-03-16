"""ComputeContext 测试。"""

from __future__ import annotations

from dyntool.compute import ComputeContext


def test_compute_context_defaults() -> None:
    """默认上下文应包含基础计算参数。"""

    ctx = ComputeContext()
    assert ctx.freq_range == (1.0, 80.0)
    assert ctx.time_window == 1.0
    assert ctx.damping_ratio == 0.05
    assert ctx.weight_type == "wk"
    assert ctx.extras == {}


def test_compute_context_with_updates_merges_extras() -> None:
    """with_updates 会保留原 extras 并合并新值。"""

    base = ComputeContext(extras={"a": 1})
    updated = base.with_updates(time_window=2.0, extras={"b": 2})
    assert base.time_window == 1.0
    assert updated.time_window == 2.0
    assert updated.extras == {"a": 1, "b": 2}
