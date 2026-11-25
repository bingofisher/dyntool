"""结构化 payload 往返恢复。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from dyntool import AccelSeries, DefaultSample, Metadata
from dyntool.domain.samples.registry import sample_from_structured_payload
from dyntool.domain.models.registry import model_from_structured_payload
from examples._bootstrap import print_summary


def main(output_dir: Path | None = None) -> dict[str, object]:
    """运行结构化 payload 往返 recipe。"""

    _ = output_dir
    # docs:begin structured_payload_roundtrip
    accel = AccelSeries.from_data([0.0, 0.12, -0.03, 0.01], dt=0.01)
    payload = accel.to_structured_payload()
    restored = model_from_structured_payload(payload)
    sample = DefaultSample(metadata=Metadata(identity={"case": "交换示例"}), accel=accel)
    sample.compute.freqspec()
    restored_sample = sample_from_structured_payload(sample.to_structured_payload())
    assert restored_sample.uid == sample.uid
    velocity = accel.calc_vel().convert_units({"value": "cm/s"}, replace=False)
    snapshot = velocity.to_xarray()
    restored_velocity = type(velocity).from_xarray(snapshot)
    assert restored_velocity.to_dict()["_dyntool"] == velocity.to_dict()["_dyntool"]
    assert restored_velocity.value_unit == velocity.value_unit
    # docs:end structured_payload_roundtrip
    return {
        "sample_category": sample.to_structured_payload().category,
        "result_status": restored_sample._slot_state["freqspec"]["status"],
        "xarray_velocity_unit": restored_velocity.value_unit,
        "original_type": type(accel).__name__,
        "restored_type": type(restored).__name__,
        "axis_unit": accel.axis_unit,
        "value_unit": accel.units["value"],
    }


if __name__ == "__main__":
    result: dict[str, Any] = main()
    print_summary(result)
