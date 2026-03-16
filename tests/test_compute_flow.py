"""ComputeContext/ComputeFlow 与模板流水线测试。"""

from __future__ import annotations

import numpy as np

from dyntool.compute import ComputeContext, ComputeFlow
from dyntool.compute.pipelines import accel_preprocess_template


def test_compute_context_with_updates() -> None:
    base = ComputeContext(freq_range=(2.0, 60.0), extras={"a": 1})
    updated = base.with_updates(freq_range=(1.0, 80.0), extras={"b": 2})
    assert base.freq_range == (2.0, 60.0)
    assert updated.freq_range == (1.0, 80.0)
    assert updated.extras == {"a": 1, "b": 2}


def test_compute_flow_checkpoint_and_branch() -> None:
    flow = ComputeFlow(_result={"value": 1})
    flow.add_metric("m1", 1.0).checkpoint("c1")
    flow.set_result({"value": 2})
    flow.from_checkpoint("c1")
    assert flow.result()["value"] == 1

    branch = flow.branch("test-branch")
    branch.set_result({"value": 3})
    assert flow.result()["value"] == 1
    assert branch.result()["value"] == 3
    assert any(item["action"] == "branch" for item in branch.history())


def test_compute_flow_then_restore_and_commit() -> None:
    flow = ComputeFlow(_result={"value": 1})
    flow.checkpoint("base").then(lambda payload: {"value": payload["value"] + 1})
    assert flow.result()["value"] == 2
    flow.restore("base")
    assert flow.result()["value"] == 1
    committed = flow.commit()
    assert committed == {"value": 1}


def test_accel_preprocess_template_outputs_flow_result() -> None:
    values = np.random.randn(256) * 0.01
    flow = accel_preprocess_template(values, dt=0.01, highpass=1.0)
    result = flow.result()
    assert "axis" in result
    assert "value" in result
    assert "dt" in result
    assert result["value"].shape[0] == values.shape[0]
