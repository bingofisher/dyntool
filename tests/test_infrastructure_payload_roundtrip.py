"""基础设施 payload 回环测试。"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from dyntool.domain.models import AccelSeries, model_from_structured_payload
from dyntool.infrastructure.serialization_helpers import dump_payload, load_payload


def test_payload_json_roundtrip_via_infrastructure(tmp_path: Path) -> None:
    """StructuredPayload 通过基础设施 JSON 辅助可完整回环。"""

    accel = AccelSeries.from_data(
        np.array([0.0, 1.0, 0.0]),
        dt=10.0,
        axis_unit="millisecond",
        data_unit="g_force",
    )
    payload = accel.to_structured_payload()
    path = tmp_path / "payload.json"
    dump_payload(path, payload)
    restored_payload = load_payload(path)
    restored = model_from_structured_payload(restored_payload)
    assert isinstance(restored, AccelSeries)
    np.testing.assert_allclose(restored.get_axis(), accel.get_axis())
    np.testing.assert_allclose(restored.get_value(), accel.get_value())
