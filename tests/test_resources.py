"""ResourceLoader 资源加载测试。"""

from __future__ import annotations

import pytest

from dyntool.application.resource_loader import ResourceLoader


class TestResourceLoader:
    """ResourceLoader get_csv、get_center_freqs。"""

    def test_get_instance(self) -> None:
        a = ResourceLoader.get_instance()
        b = ResourceLoader.get_instance()
        assert a is b

    def test_get_path_center_freq(self) -> None:
        loader = ResourceLoader.get_instance()
        path = loader.get_path("center_freq")
        assert path.name == "1-3倍频程频带与中心频率.csv"
        assert path.exists()

    def test_get_csv_center_freq(self) -> None:
        loader = ResourceLoader.get_instance()
        df = loader.get_csv("center_freq")
        assert "中心频率 (Hz)" in df.columns
        assert len(df) > 0

    def test_get_center_freqs(self) -> None:
        loader = ResourceLoader.get_instance()
        arr, index = loader.get_center_freqs(freq_range=(1.0, 80.0))
        assert len(arr) == len(index)
        assert arr.min() >= 1.0
        assert arr.max() <= 80.0
        arr_narrow, _ = loader.get_center_freqs(freq_range=(10.0, 20.0))
        assert arr_narrow.min() >= 10.0
        assert arr_narrow.max() <= 20.0

    def test_get_path_unknown_key_raises(self) -> None:
        loader = ResourceLoader.get_instance()
        with pytest.raises(KeyError, match="未知资源 key"):
            loader.get_path("unknown_key")
