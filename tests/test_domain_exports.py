"""检查 domain 主实现包的导出一致性。"""

from __future__ import annotations

import pytest

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
from dyntool.domain.enums import SampleDomain
from dyntool.domain.samples import DefaultSample, DefaultSampleSet, VibrationTestSample, VibrationTestSampleSet
from dyntool.domain.samples.base import SampleBaseModel
from dyntool.domain.samples.registry import sample_from_structured_payload, sample_set_from_structured_payload


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
    assert issubclass(DefaultSample, SampleBaseModel)
    assert callable(sample_from_structured_payload)


def _build_default_sample() -> DefaultSample:
    return DefaultSample.from_accel_data(
        [0.0, 0.1, -0.02],
        dt=0.01,
        metadata=Metadata(extra={"source": "sensor-a"}),
    )


def _build_vibration_test_sample() -> VibrationTestSample:
    return VibrationTestSample.from_accel_data(
        [0.0, 0.1, -0.02],
        dt=0.01,
        sample_domain=SampleDomain.VIBRATION_TEST,
        metadata_cls=TypeModuleVibrationTestMetadata,
        case="case-1",
        point="P1",
        instr="ACC-01",
        dir="Z",
        record="R1",
        timestamp="2026-03-08 12:00:00",
    )


def test_sample_payload_restores_default_sample_category() -> None:
    sample = _build_default_sample()
    payload = sample.to_structured_payload().to_dict()
    payload["category"] = "DefaultSample"

    restored = sample_from_structured_payload(payload)

    assert isinstance(restored, DefaultSample)


def test_sample_set_payload_restores_default_sample_set_category() -> None:
    sample = _build_default_sample()
    sample_set = DefaultSampleSet.from_samples([sample])
    payload = sample_set.to_structured_payload().to_dict()
    payload["category"] = "DefaultSampleSet"

    restored = sample_set_from_structured_payload(payload)

    assert isinstance(restored, DefaultSampleSet)


def test_sample_payload_rejects_removed_legacy_sample_category() -> None:
    sample = _build_default_sample()
    payload = sample.to_structured_payload().to_dict()
    payload["category"] = "Sample"

    with pytest.raises(ValueError, match="旧样本类别名 Sample 已移除，请迁移为 DefaultSample。$") as exc_info:
        sample_from_structured_payload(payload)

    assert str(exc_info.value) == "旧样本类别名 Sample 已移除，请迁移为 DefaultSample。"


def test_sample_set_payload_rejects_removed_legacy_sample_set_category() -> None:
    sample = _build_default_sample()
    sample_set = DefaultSampleSet.from_samples([sample])
    payload = sample_set.to_structured_payload().to_dict()
    payload["category"] = "SampleSet"

    with pytest.raises(ValueError, match="旧样本集类别名 SampleSet 已移除，请迁移为 DefaultSampleSet。$") as exc_info:
        sample_set_from_structured_payload(payload)

    assert str(exc_info.value) == "旧样本集类别名 SampleSet 已移除，请迁移为 DefaultSampleSet。"


def test_sample_payload_restores_vibration_test_sample_category() -> None:
    sample = _build_vibration_test_sample()
    payload = sample.to_structured_payload().to_dict()
    payload["category"] = "VibrationTestSample"

    restored = sample_from_structured_payload(payload)

    assert isinstance(restored, VibrationTestSample)


def test_sample_set_payload_restores_vibration_test_sample_set_category() -> None:
    sample = _build_vibration_test_sample()
    sample_set = VibrationTestSampleSet.from_samples([sample], sample_domain=SampleDomain.VIBRATION_TEST)
    payload = sample_set.to_structured_payload().to_dict()
    payload["category"] = "VibrationTestSampleSet"

    restored = sample_set_from_structured_payload(payload)

    assert isinstance(restored, VibrationTestSampleSet)


def test_sample_payload_rejects_unknown_category() -> None:
    sample = _build_default_sample()
    payload = sample.to_structured_payload().to_dict()
    payload["category"] = "UnknownSample"

    with pytest.raises(ValueError, match="不支持的样本类别: UnknownSample$"):
        sample_from_structured_payload(payload)


def test_sample_set_payload_rejects_unknown_category() -> None:
    sample = _build_default_sample()
    sample_set = DefaultSampleSet.from_samples([sample])
    payload = sample_set.to_structured_payload().to_dict()
    payload["category"] = "UnknownSampleSet"

    with pytest.raises(ValueError, match="不支持的样本集类别: UnknownSampleSet$"):
        sample_set_from_structured_payload(payload)
