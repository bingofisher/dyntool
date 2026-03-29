"""传递函数分析主入口测试。"""

from __future__ import annotations

import numpy as np

from dyntool import AccelSeries, SampleDomain, TransferFunctionAnalyzer
from dyntool.domain.models import FreqSpec
from dyntool.domain.samples import DefaultSample


def test_transfer_function_analyzer_supports_arrays_models_and_samples() -> None:
    dt = 0.01
    time = np.arange(0.0, 2.56, dt)
    input_accel = np.sin(2 * np.pi * 5.0 * time)
    output_accel = 2.0 * input_accel

    analyzer = TransferFunctionAnalyzer(input_accel, output_accel, fs=int(round(1.0 / dt)))
    result = analyzer.solve()
    assert result.transfer_function is not None
    assert result.freqspec is not None
    assert isinstance(result.freqspec, FreqSpec)

    input_model = AccelSeries.from_data(input_accel, dt=dt)
    output_model = AccelSeries.from_data(output_accel, dt=dt)
    model_result = TransferFunctionAnalyzer.from_models(input_model, output_model).solve()
    assert isinstance(model_result.freqspec, FreqSpec)
    np.testing.assert_allclose(model_result.frequencies, result.frequencies)

    input_sample = DefaultSample.from_accel_data(
        input_accel,
        dt=dt,
        sample_domain=SampleDomain.VIBRATION_TEST,
        case="case-1",
        point="IN",
        instr="ACC-IN",
        dir="Z",
        record="R1",
        timestamp="2026-03-17 09:00:00",
    )
    output_sample = DefaultSample.from_accel_data(
        output_accel,
        dt=dt,
        sample_domain=SampleDomain.VIBRATION_TEST,
        case="case-1",
        point="OUT",
        instr="ACC-OUT",
        dir="Z",
        record="R2",
        timestamp="2026-03-17 09:00:01",
    )
    sample_result = TransferFunctionAnalyzer.from_samples(input_sample, output_sample).solve()
    assert isinstance(sample_result.freqspec, FreqSpec)
