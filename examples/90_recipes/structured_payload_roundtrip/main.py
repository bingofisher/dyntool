"""结构化 payload 往返恢复。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from dyntool import AccelSeries
from dyntool.domain.models.registry import model_from_structured_payload
from examples._bootstrap import print_summary


def main(output_dir: Path | None = None) -> dict[str, object]:
    """运行结构化 payload 往返 recipe。"""

    _ = output_dir
    # docs:begin structured_payload_roundtrip
    accel = AccelSeries.from_data([0.0, 0.12, -0.03, 0.01], dt=0.01)
    payload = accel.to_structured_payload()
    restored = model_from_structured_payload(payload)
    # docs:end structured_payload_roundtrip
    return {
        "original_type": type(accel).__name__,
        "restored_type": type(restored).__name__,
        "axis_unit": accel.axis_unit,
        "value_unit": accel.units["value"],
    }


if __name__ == "__main__":
    result: dict[str, Any] = main()
    print_summary(result)
