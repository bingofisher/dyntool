"""CSV 后端测试。"""

import tempfile
from pathlib import Path

import numpy as np
import pytest

from dyntool.domain.constants import DataCategory
from dyntool.domain.models import AccelSeries
from dyntool.infrastructure.persistence_backends import CSVBackend


class TestCSVBackend:
    """验证 CSV 保存、加载和单位检查。"""

    def test_save_and_load_accel_series(self) -> None:
        """AccelSeries 保存为 CSV 后可以完整读回。"""

        backend = CSVBackend()
        dt = 0.002
        n = 100
        accel = AccelSeries.from_data(np.random.randn(n) * 0.01, dt=dt)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "accel.csv"
            backend.save(path, accel)
            assert path.exists()
            loaded = backend.load(path, category=DataCategory.TS_ACCEL)
            assert isinstance(loaded, AccelSeries)
            np.testing.assert_allclose(loaded.get_axis().flatten(), accel.get_axis())
            np.testing.assert_allclose(loaded.get_value().flatten(), accel.get_value())
            assert loaded.dt == accel.dt

    def test_inspect_units_reads_headers(self) -> None:
        """inspect_units 能从 CSV 表头提取单位。"""

        backend = CSVBackend()
        accel = AccelSeries.from_data(
            np.zeros(3),
            dt=10.0,
            axis_unit="millisecond",
            data_unit="g_force",
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "accel.csv"
            accel.to_csv(path)
            inspected = backend.inspect_units(path, category=DataCategory.TS_ACCEL)
        assert inspected == {"time": "millisecond", "value": "g_force"}

    def test_load_requires_category(self) -> None:
        """CSV 读取时未指定 category 会报错。"""

        backend = CSVBackend()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "accel.csv"
            accel = AccelSeries.from_data(np.zeros(10), dt=0.01)
            backend.save(path, accel)
            with pytest.raises(ValueError, match="category"):
                backend.load(path)
