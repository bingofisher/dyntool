"""真实输入文件导入与标准化工作流示例。"""

from __future__ import annotations

from pathlib import Path

from dyntool import AccelSeries, Sample, SampleDomain, SampleSet, StorageScheme


def main(output_dir: Path) -> dict[str, object]:
    """演示从真实 CSV 导入、单位标准化并进入样本存储链路。"""

    source = Path("examples/input_data/simple_accel_with_units.csv")
    normalized_csv = output_dir / "normalized.csv"
    store_path = output_dir / "sample_set.h5"

    accel = AccelSeries.from_csv(source)
    normalized = accel.convert_units({"time": "second", "value": "meter/second**2"}, replace=False)
    normalized.to_csv(normalized_csv)
    inspected = AccelSeries.inspect_units(normalized_csv, fmt="csv")

    sample = Sample.from_models(
        sample_domain=SampleDomain.VIBRATION_TEST,
        accel=normalized,
        case="workflow-real-file",
        point="P1",
        instr="ACC-REAL",
        dir="Z",
        record="R1",
        timestamp="2026-03-16 12:00:00",
    )
    sample.eval_zvl(overwrite=True, freq_range=(2.0, 60.0))
    sample_set = SampleSet.from_samples([sample], sample_domain=SampleDomain.VIBRATION_TEST)
    sample_set.save(store_path, storage_scheme=StorageScheme.SET_H5)

    return {
        "source": str(source),
        "normalized_csv": str(normalized_csv),
        "store_path": str(store_path),
        "inspected": inspected,
    }


__all__ = ["main"]
