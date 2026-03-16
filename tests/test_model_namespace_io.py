"""模型类 I/O 回归测试。"""

from __future__ import annotations

from pathlib import Path

from dyntool import AccelSeries


def test_model_class_supports_csv_and_h5_roundtrip(tmp_path: Path) -> None:
    accel = AccelSeries.from_data(
        [0.0, 0.1, -0.02, 0.03],
        dt=0.01,
        axis_unit="second",
        data_unit="meter/second**2",
    )
    csv_path = tmp_path / "accel.csv"
    h5_path = tmp_path / "accel.h5"
    accel.to_csv(csv_path)
    accel.to_h5(h5_path)

    csv_loaded = AccelSeries.from_csv(csv_path)
    h5_loaded = AccelSeries.from_h5(h5_path)
    csv_units = AccelSeries.inspect_units(csv_path, fmt="csv")
    h5_units = AccelSeries.inspect_units(h5_path, fmt="h5")

    assert csv_loaded.get_value().shape == accel.get_value().shape
    assert h5_loaded.get_value().shape == accel.get_value().shape
    assert csv_units["time"] == "second"
    assert h5_units["value"].replace(" ", "") == "meter/second**2"
