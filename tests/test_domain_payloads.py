"""StructuredPayload 与 xarray 回环测试。"""

from __future__ import annotations

from datetime import datetime

import numpy as np

from dyntool.domain.metadata import (
    Metadata,
    MetadataBase,
    VibrationTestMetadata,
)
from dyntool.domain.models import AccelSeries, FreqSpec
from dyntool.domain.samples import DefaultSample, DefaultSampleSet
from dyntool.domain.serialization import StructuredPayload


def test_accel_structured_payload_roundtrip() -> None:
    accel = AccelSeries.from_data(
        [0.0, 1.0, -1.0, 0.5],
        dt=10.0,
        axis_unit="millisecond",
        data_unit="g_force",
    )
    payload = accel.to_structured_payload()
    assert isinstance(payload, StructuredPayload)
    restored = AccelSeries.from_structured_payload(payload)
    np.testing.assert_allclose(
        restored.get_axis(unit="second"),
        accel.get_axis(unit="second"),
    )
    np.testing.assert_allclose(
        restored.get_value(unit="meter/second**2"),
        accel.get_value(unit="meter/second**2"),
        rtol=1e-6,
        atol=1e-6,
    )


def test_accel_xarray_roundtrip() -> None:
    accel = AccelSeries.from_data(
        [0.0, 0.2, -0.1, 0.0],
        dt=0.01,
    )
    xr_obj = accel.to_xarray()
    restored = AccelSeries.from_xarray(xr_obj)
    np.testing.assert_allclose(restored.get_axis(), accel.get_axis())
    np.testing.assert_allclose(restored.get_value(), accel.get_value())


def test_composite_model_structured_payload_roundtrip() -> None:
    accel = AccelSeries.from_data(np.random.randn(128) * 0.01, dt=0.002)
    freqspec = accel.calc_freqspec()
    payload = freqspec.to_structured_payload()
    restored = FreqSpec.from_structured_payload(payload)
    assert restored.amp is not None
    assert freqspec.amp is not None
    np.testing.assert_allclose(
        restored.amp.get_value(),
        freqspec.amp.get_value(),
    )


def test_metadata_structured_payload_roundtrip() -> None:
    metadata = VibrationTestMetadata(
        case="c1",
        point="p1",
        instr="a1",
        dir="Z",
        record="r1",
        timestamp=datetime(2026, 3, 8, 12, 0, 0),
    )
    payload = metadata.to_structured_payload()
    restored = MetadataBase.from_structured_payload(payload)
    assert isinstance(restored, VibrationTestMetadata)
    assert restored.uid == metadata.uid


def test_sample_structured_payload_roundtrip() -> None:
    sample = DefaultSample(
        metadata=Metadata(extra={"source": "sensor-a"}),
        accel=AccelSeries.from_data([0.0, 0.2, -0.1], dt=0.01),
    )
    payload = sample.to_structured_payload()
    restored = DefaultSample.from_structured_payload(payload)
    assert restored.uid == sample.uid
    assert restored.accel is not None
    assert sample.accel is not None
    np.testing.assert_allclose(restored.accel.get_value(), sample.accel.get_value())


def test_sample_set_structured_payload_roundtrip() -> None:
    sample = DefaultSample(
        metadata=Metadata(extra={"batch": "b1"}),
        accel=AccelSeries.from_data([0.0, 0.1, 0.0, -0.1], dt=0.005),
    )
    sample_set = DefaultSampleSet({sample.uid: sample})
    payload = sample_set.to_structured_payload()
    restored = DefaultSampleSet.from_structured_payload(payload)
    assert len(restored) == 1
    assert sample.uid in restored
    assert restored[sample.uid].accel is not None
