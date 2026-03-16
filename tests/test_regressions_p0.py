"""P0 缺陷修复回归测试。"""

from __future__ import annotations


from dyntool.domain.constants import DataCategory
from dyntool.domain.metadata import Metadata


def test_metadata_update_accepts_declared_field_even_if_not_set_before() -> None:
    meta = Metadata(extra=None)
    meta.update(extra={"line": "A"})
    assert meta.extra == {"line": "A"}


def test_category_mapping_contains_response_and_spectrum_fields() -> None:
    assert DataCategory.to_sample_attr_name(DataCategory.FS_SPEC) == "freqspec"
    assert DataCategory.to_sample_attr_name(DataCategory.RS_SPEC) == "respspec"
