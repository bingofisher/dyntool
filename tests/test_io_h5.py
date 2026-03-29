"""HDF5 后端测试。"""

import tempfile
from pathlib import Path

import h5py
import numpy as np
import pytest

from dyntool.domain.constants import DataCategory
from dyntool.domain.models import AccelSeries, ZVLEval
from dyntool.infrastructure.persistence_backends import H5Backend


class TestH5Backend:
    """验证 HDF5 的单位保存与读取行为。"""

    def test_save_and_load_accel_series(self) -> None:
        """加速度时程序列能保留数据和单位信息。"""

        backend = H5Backend()
        accel = AccelSeries.from_data(
            np.random.randn(100) * 0.01,
            dt=2.0,
            axis_unit="millisecond",
            data_unit="g_force",
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "accel.h5"
            accel_si = accel.convert_units(
                {"time": "second", "value": "meter/second**2"},
                replace=False,
            )
            backend.save(path, accel_si)
            inspected = backend.inspect_units(path, category=DataCategory.TS_ACCEL)
            loaded = backend.load(path, category=DataCategory.TS_ACCEL).convert_units(
                {"time": "millisecond", "value": "g_force"},
                replace=True,
            )

        assert isinstance(loaded, AccelSeries)
        assert inspected == {
            "time": "second",
            "value": "meter / second ** 2",
        }
        np.testing.assert_allclose(loaded.get_axis().flatten(), accel.get_axis().flatten())
        np.testing.assert_allclose(loaded.get_value().flatten(), accel.get_value().flatten())
        assert loaded.axis_unit == accel.axis_unit
        assert loaded.value_unit == accel.value_unit

    def test_save_and_load_zvl_eval(self) -> None:
        """标量评价结果可以正常 round-trip。"""

        backend = H5Backend()
        zvl = ZVLEval.from_data(zvl=65.0, aw=0.001)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "zvl.h5"
            backend.save(path, zvl)
            loaded = backend.load(path, category=DataCategory.ZVL_EVAL)

        assert isinstance(loaded, ZVLEval)
        assert abs(float(loaded.get_field("zvl").flat[0]) - 65.0) < 1e-9
        assert abs(float(loaded.get_field("aw").flat[0]) - 0.001) < 1e-9
        assert loaded.get_field_unit("zvl") == zvl.get_field_unit("zvl")
        assert loaded.get_field_unit("aw") == zvl.get_field_unit("aw")

    def test_load_requires_category(self) -> None:
        """从原始 HDF5 加载模型时仍要求显式 category。"""

        backend = H5Backend()
        accel = AccelSeries.from_data(np.zeros(10), dt=0.01)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "accel.h5"
            backend.save(path, accel)
            with pytest.raises(ValueError, match="category"):
                backend.load(path)

    def test_save_uses_gzip_compression_by_default(self) -> None:
        backend = H5Backend()
        accel = AccelSeries.from_data(np.random.randn(64) * 0.01, dt=0.01)

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "accel_default_compression.h5"
            backend.save(path, accel)
            with h5py.File(path, "r") as handle:
                dataset = handle["value"]
                assert dataset.compression == "gzip"
                assert dataset.compression_opts == 4

    def test_save_allows_explicit_dataset_options_override(self) -> None:
        backend = H5Backend()
        accel = AccelSeries.from_data(np.random.randn(64) * 0.01, dt=0.01)

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "accel_lzf.h5"
            backend.save(path, accel, dataset_options={"compression": "lzf"})
            with h5py.File(path, "r") as handle:
                dataset = handle["value"]
                assert dataset.compression == "lzf"
