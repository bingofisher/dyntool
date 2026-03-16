"""检查 domain 主实现包的导出一致性。"""

from __future__ import annotations

from dyntool.domain.metadata import Metadata, MetadataBase
from dyntool.domain.metadata.base import (
    MetadataBase as BaseModuleMetadataBase,
    MetadataIDGenerator as BaseModuleMetadataIDGenerator,
)
from dyntool.domain.metadata.normalization import (
    denormalize_flat_dict,
    dump_extra,
    normalize_extra,
)
from dyntool.domain.metadata.registry import metadata_from_structured_payload
from dyntool.domain.metadata.types import Metadata as TypeModuleMetadata
from dyntool.domain.metadata.types import (
    VibrationTestMetadata as TypeModuleVibrationTestMetadata,
)
from dyntool.domain.models import TimeSeries
from dyntool.domain.models.base import DataModelBase
from dyntool.domain.models.registry import model_from_structured_payload
from dyntool.domain.samples import Sample
from dyntool.domain.samples.base import SampleBaseModel
from dyntool.domain.samples.registry import sample_from_structured_payload


def test_metadata_package_exports_are_consistent() -> None:
    assert MetadataBase is BaseModuleMetadataBase
    assert Metadata is TypeModuleMetadata


def test_metadata_base_symbols_are_defined_in_canonical_base_module() -> None:
    assert MetadataBase.__module__ == "dyntool.domain.metadata.base"
    assert BaseModuleMetadataIDGenerator.__module__ == "dyntool.domain.metadata.base"


def test_metadata_normalization_helpers_are_defined_in_canonical_module() -> None:
    assert normalize_extra.__module__ == "dyntool.domain.metadata.normalization"
    assert dump_extra.__module__ == "dyntool.domain.metadata.normalization"
    assert denormalize_flat_dict.__module__ == "dyntool.domain.metadata.normalization"


def test_metadata_type_symbols_are_defined_in_canonical_types_module() -> None:
    assert TypeModuleMetadata.__module__ == "dyntool.domain.metadata.types"
    assert TypeModuleVibrationTestMetadata.__module__ == "dyntool.domain.metadata.types"


def test_metadata_registry_symbol_is_defined_in_canonical_registry_module() -> None:
    assert metadata_from_structured_payload.__module__ == "dyntool.domain.metadata.registry"


def test_models_package_exports_are_consistent() -> None:
    assert issubclass(TimeSeries, DataModelBase)
    assert callable(model_from_structured_payload)


def test_samples_package_exports_are_consistent() -> None:
    assert issubclass(Sample, SampleBaseModel)
    assert callable(sample_from_structured_payload)
