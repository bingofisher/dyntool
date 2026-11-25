"""力、力矩、应力和应变复用现有时程及通用样本框架。"""

from pathlib import Path

import numpy as np
import pytest

from dyntool import (
    DefaultSample,
    DefaultSampleSet,
    ForceSeries,
    Metadata,
    MomentSeries,
    StrainSeries,
    StressSeries,
    UnitSystem,
    storage,
)
from dyntool.domain.compute_api import ComputeSource
from dyntool.domain.models import model_from_structured_payload
from dyntool.domain.samples.registry import sample_from_structured_payload
from dyntool.storage.types import DataCategory, resolve_data_category


CASES = [
    ("force", ForceSeries, "kilonewton", "newton", 1000.0),
    ("moment", MomentSeries, "kilonewton * meter", "newton * meter", 1000.0),
    ("stress", StressSeries, "megapascal", "pascal", 1e6),
    ("strain", StrainSeries, "microstrain", "dimensionless", 1e-6),
]


@pytest.mark.parametrize("field,model_type,unit,si,scale", CASES)
def test_model_units_and_registered_exchange(field, model_type, unit, si, scale) -> None:
    """独立比例基准及正式注册恢复保持类型、单位和二维形状。"""
    values = np.array([[1, 2], [-2, 3], [3, -4]], dtype=float)
    model = model_type.from_data(values, dt=0.01, data_unit=unit)
    np.testing.assert_allclose(model.get_value(unit=si), values * scale)
    assert str(model.category) == field
    assert resolve_data_category(field) is getattr(DataCategory, f"TS_{field.upper()}")
    converted = model.convert_units({"value": si}, replace=False)
    np.testing.assert_allclose(converted.get_value(), values * scale)
    for recovered in (
        model_from_structured_payload(model.to_structured_payload()),
        model_type.from_xarray(model.to_xarray()),
    ):
        assert type(recovered) is model_type
        np.testing.assert_allclose(recovered.get_value(unit=si), values * scale)
        assert recovered.get_value().shape == (3, 2)


@pytest.mark.parametrize("field,model_type,unit,si,scale", CASES)
@pytest.mark.parametrize("fmt", ["csv", "h5"])
def test_model_file_roundtrip(tmp_path: Path, field, model_type, unit, si, scale, fmt: str) -> None:
    """现有 CSV/H5 保存和单位检查无需增加后端分支。"""
    model = model_type.from_data([1, -2, 3], dt=0.01, data_unit=unit)
    target = tmp_path / f"{field}.{fmt}"
    storage.save_model(model, target)
    recovered = storage.load_model(target, model_type)
    np.testing.assert_allclose(recovered.get_value(unit=si), np.array([1, -2, 3]) * scale)
    units = model_type.inspect_units(target, fmt=fmt)
    assert "time" in units and "value" in units


@pytest.mark.parametrize("field,model_type,unit,si,scale", CASES)
def test_fft_preserves_physical_amplitude(field, model_type, unit, si, scale) -> None:
    """已知幅值正弦在显式 SI 输出中保持物理幅值，默认输出保持输入单位。"""
    time = np.arange(2048) / 256
    model = model_type.from_data(2 * np.sin(2 * np.pi * 32 * time), dt=1 / 256, data_unit=unit)
    default = model.calc_freqspec()
    spectrum = model.calc_freqspec(output_unit_system=UnitSystem.si())
    index = np.argmin(abs(spectrum.get_axis(unit="hertz") - 32))
    assert default.amp.get_value()[index] == pytest.approx(2, rel=1e-3)
    assert spectrum.amp.get_value(unit=si)[index] == pytest.approx(2 * scale, rel=1e-3)


def test_default_sample_slots_and_source_flow() -> None:
    """四槽位共享原有构造、受控更新、计算源、追溯及载荷恢复。"""
    models = {field: kind.from_data([1, 2, 3], dt=0.01) for field, kind, *_ in CASES}
    current = DefaultSample(metadata=Metadata(identity={"case": "mechanical"}), **models)
    recovered = sample_from_structured_payload(current.to_structured_payload())
    for field, kind, *_ in CASES:
        assert isinstance(getattr(recovered, field), kind)
        assert current.compute.feature.rms(source=ComputeSource(field)) == pytest.approx(np.sqrt(14 / 3))
        result = current.compute.spectrum.freqspec(source=ComputeSource(field), overwrite=True)
        assert result.success, result.message
        assert current.freqspec.current_units()["amp"] == getattr(current, field).value_unit
        branch = current.compute.flow(source=field).branch("scaled")
        branch.set_result(kind.from_data([4, 5, 6], dt=0.01)).commit()
        np.testing.assert_array_equal(getattr(current, field).get_value(), [4, 5, 6])
    with pytest.raises(TypeError):
        current.update_data(moment=models["stress"])
    assert not hasattr(current.stress, "eval_zvl")


@pytest.mark.parametrize("scheme", list(storage.StorageScheme))
def test_sample_storage_partial_save_and_reopen(tmp_path: Path, scheme: storage.StorageScheme) -> None:
    """六种正式策略通过 schema 保存新槽位，部分更新不删除其他物理量。"""
    models = {field: kind.from_data([1, 2, 3], dt=0.01, data_unit=unit) for field, kind, unit, *_ in CASES}
    current = DefaultSample(metadata=Metadata(identity={"case": "repository"}), **models)
    samples = DefaultSampleSet([current])
    target = tmp_path / "store"
    samples.save(target, storage_scheme=scheme)
    current.update_data(moment=MomentSeries.from_data([7, 8, 9], dt=0.01, data_unit="kilonewton * meter"))
    samples.save(target, storage_scheme=scheme, categories=["moment"])
    loaded = DefaultSampleSet.from_storage(target, storage_scheme=scheme, load_mode=storage.SampleLoadMode.LAZY)
    for field, kind, _, si, scale in CASES:
        model = getattr(loaded[current.uid], field)
        assert isinstance(model, kind)
        expected = np.array([7, 8, 9] if field == "moment" else [1, 2, 3]) * scale
        np.testing.assert_allclose(model.get_value(unit=si), expected)
    report = storage.inspect_storage_repository(target, storage_scheme=scheme, level="deep")
    assert report.is_valid, report.issues


@pytest.mark.parametrize("field,model_type,unit,si,scale", CASES)
def test_sample_compare_and_report_units(tmp_path: Path, field, model_type, unit, si, scale) -> None:
    """无加速度样本的 RMS 比较和导出仍按实际来源规范化单位。"""
    metadata = Metadata(identity={"case": "same"})
    values = np.array([1, -2, 3])
    left = DefaultSampleSet(
        [DefaultSample(metadata=metadata, **{field: model_type.from_data(values, dt=0.01, data_unit=unit)})]
    )
    right = DefaultSampleSet(
        [DefaultSample(metadata=metadata, **{field: model_type.from_data(values * scale, dt=0.01, data_unit=si)})]
    )
    report = left.compare_with(right, features=["rms"])
    assert report.scalar_diff.empty
    target = left.export_series_frame(tmp_path / "series.csv", data_var=field, format="csv")
    assert target.is_file()


def test_strain_percent_conversion() -> None:
    """百分应变与无量纲应变使用现有 Pint 换算。"""
    model = StrainSeries.from_data([1, 2], dt=0.01, data_unit="percent")
    np.testing.assert_allclose(model.get_value(unit="dimensionless"), [0.01, 0.02])
