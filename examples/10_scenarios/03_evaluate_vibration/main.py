"""完成处理、频谱计算与振动评价。"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from dyntool import AccelSeries, Sample, SampleDomain, SampleSet, TransferFunctionAnalyzer
from dyntool.plotting import FramePlotter


def _build_sample(*, suffix: str, phase: float) -> Sample:
    values = np.sin(np.linspace(0.0, 4.0 * np.pi, 512) + phase) * 0.05
    accel = AccelSeries.from_data(values, dt=0.002)
    return Sample.from_models(
        sample_domain=SampleDomain.VIBRATION_TEST,
        accel=accel,
        case=f"case-{suffix}",
        point=f"point-{suffix}",
        instr="accel-01",
        dir="Z",
        record=f"record-{suffix}",
        timestamp="2026-03-16 12:00:00",
    )


def main(output_dir: Path | None = None) -> dict[str, object]:
    """运行样本集批量频谱、反应谱、传递函数与绘图场景。"""

    _ = output_dir

    # docs:begin processing_eval_minimal
    sample_set = SampleSet.from_samples(
        [
            _build_sample(suffix="a", phase=0.0),
            _build_sample(suffix="b", phase=np.pi / 6.0),
        ],
        sample_domain=SampleDomain.VIBRATION_TEST,
    )
    freqspec_results = sample_set.calc_freqspec(overwrite=True)
    respspec_results = sample_set.processing.calc_respspec(overwrite=True)
    first_sample = next(iter(sample_set.values()))
    first_sample.eval_zvl(overwrite=True, freq_range=(2.0, 60.0))
    # docs:end processing_eval_minimal

    # docs:begin plotting_transfer_minimal
    sample_list = list(sample_set.values())
    transfer_result = TransferFunctionAnalyzer.from_samples(sample_list[0], sample_list[1]).solve()
    plotter = FramePlotter()
    plotter.add(first_sample.accel, name="first-sample-accel")
    plot_result = plotter.plot()
    # docs:end plotting_transfer_minimal

    return {
        "sample_count": len(sample_set),
        "freqspec_ok_count": sum(1 for result in freqspec_results.values() if result.success),
        "respspec_ok_count": sum(1 for result in respspec_results.values() if result.success),
        "freqspec_type": type(first_sample.freqspec).__name__,
        "respspec_type": type(first_sample.respspec).__name__,
        "transfer_freqspec_type": type(transfer_result.freqspec).__name__,
        "plot_axes_count": len(plot_result.axes),
        "has_zvl": first_sample.zvl is not None,
    }


if __name__ == "__main__":
    from examples._bootstrap import print_summary

    print_summary(main())
