"""storage runtime 导入契约回归测试。"""

from __future__ import annotations

import importlib


def test_storage_runtime_module_is_importable() -> None:
    """storage runtime 内部模块应可被正常导入。"""

    module = importlib.import_module("dyntool.storage._sample_set_runtime")

    assert hasattr(module, "_SampleSetStorageRuntimeMixin")
