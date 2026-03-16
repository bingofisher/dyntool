"""Compute 模板流水线测试。"""

from __future__ import annotations

import numpy as np

from dyntool.compute.pipelines import (
    freq_eval_template,
    resp_eval_template,
    sample_batch_template,
)


def test_freq_eval_template_outputs_flow() -> None:
    """频谱模板应返回包含结果与指标的 flow。"""

    accel = np.random.randn(512) * 0.01
    flow = freq_eval_template(accel, dt=0.002)
    assert flow.result() is not None
    assert "fft_points" in flow.metrics()


def test_resp_eval_template_outputs_flow() -> None:
    """反应谱模板应返回可读结果。"""

    accel = np.random.randn(512) * 0.01
    flow = resp_eval_template(accel, dt=0.002)
    assert flow.result() is not None
    assert flow.artifact("respspec") is not None


def test_sample_batch_template_outputs_batch_size_metric() -> None:
    """批处理模板应记录 batch_size 指标。"""

    items = [1, 2, 3]

    def runner(item: int, *, context: object) -> int:
        del context
        return item * 2

    flow = sample_batch_template(items, runner=runner)
    assert flow.result() == [2, 4, 6]
    assert flow.metrics()["batch_size"] == 3.0
