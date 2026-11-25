"""规范驱动限值类测试。"""

from __future__ import annotations

from pathlib import Path

import h5py
import numpy as np
import pandas as pd
import pytest

import dyntool.plotting as dt_plotting
import dyntool.storage as dt_storage
from dyntool.infrastructure.persistence import BackendError
from dyntool import (
    FDMVLLimit,
    FDMVLLimitStandard,
    FPVDVLimit,
    FPVDVLimitStandard,
    OTOVLLimit,
    OTOVLLimitStandard,
    ZVLLimit,
    ZVLLimitStandard,
)


def test_zvl_limit_supports_registered_standards_and_scenes() -> None:
    """Z 振级限值应暴露已注册标准和场景。"""

    assert ZVLLimit.supported_standards() == (
        ZVLLimitStandard.GB_10070_1988,
        ZVLLimitStandard.GB_T_50355_2018,
    )
    assert "特殊住宅区昼间" in ZVLLimit.supported_scenes(ZVLLimitStandard.GB_10070_1988)
    assert "卧室昼间一级" in ZVLLimit.supported_scenes(ZVLLimitStandard.GB_T_50355_2018)


def test_zvl_limit_can_load_city_area_limit_from_standard() -> None:
    """Z 振级限值应能从标准表提取单个场景。"""

    limit = ZVLLimit.from_standard(
        ZVLLimitStandard.GB_10070_1988,
        scene="特殊住宅区昼间",
    )

    assert limit.standard == ZVLLimitStandard.GB_10070_1988
    assert limit.scene == "特殊住宅区昼间"
    assert limit.clause == "3.1.1"
    assert limit.resource_key == "limit_city_zvl"
    assert float(limit.zvl.flat[0]) == pytest.approx(65.0)


def test_otovl_limit_can_load_residential_curve_from_standard() -> None:
    """1/3 倍频程限值应返回频率轴和限值曲线。"""

    limit = OTOVLLimit.from_standard(
        OTOVLLimitStandard.GB_T_50355_2018,
        scene="卧室昼间一级",
    )

    assert limit.standard == OTOVLLimitStandard.GB_T_50355_2018
    assert limit.scene == "卧室昼间一级"
    assert limit.clause == "3.0.2"
    assert limit.resource_key == "limit_residential_otovl"
    assert limit.freq.shape == limit.otovl.shape
    assert float(limit.freq[0]) == pytest.approx(1.0)
    assert float(limit.freq[-1]) == pytest.approx(80.0)
    assert float(limit.otovl[0]) == pytest.approx(76.0)
    assert float(limit.otovl[-1]) == pytest.approx(88.0)


def test_fpvdv_limit_can_load_transport_limit_from_standard() -> None:
    """四次方振动剂量值限值应返回单个标量。"""

    limit = FPVDVLimit.from_standard(
        FPVDVLimitStandard.GB_50868_2013,
        scene="居住建筑夜间",
    )

    assert limit.standard == FPVDVLimitStandard.GB_50868_2013
    assert limit.scene == "居住建筑夜间"
    assert limit.clause == "7.2.3"
    assert limit.resource_key == "limit_transport_fpvdv"
    assert float(limit.fpvdv.flat[0]) == pytest.approx(0.1)


def test_limit_standard_requires_enum_and_scene_must_exist() -> None:
    """公开入口应执行枚举和场景校验。"""

    with pytest.raises(TypeError):
        ZVLLimit.supported_scenes("GB_10070-1988")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        ZVLLimit.from_standard("GB_10070-1988", scene="特殊住宅区昼间")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        ZVLLimit.from_standard(
            ZVLLimitStandard.GB_10070_1988,
            scene="不存在的场景",
        )


@pytest.mark.parametrize(
    ("scene", "expected"),
    [
        ("特殊住宅区昼间", 65.0),
        ("特殊住宅区夜间", 62.0),
        ("居民文教区昼间", 65.0),
        ("居民文教区夜间", 62.0),
        ("混合区商业中心区昼间", 70.0),
        ("混合区商业中心区夜间", 67.0),
        ("工业集中区昼间", 75.0),
        ("工业集中区夜间", 72.0),
        ("交通干线道路两侧昼间", 75.0),
        ("交通干线道路两侧夜间", 72.0),
    ],
)
def test_fdmvl_limit_matches_all_jgj_170_scenes(scene: str, expected: float) -> None:
    """JGJ/T 170 表 4.0.1 的每个场景应保留准确的限值和规范出处。"""

    standard = FDMVLLimitStandard.JGJ_T_170_2009
    limit = FDMVLLimit.from_standard(standard, scene=scene)

    assert FDMVLLimit.supported_standards() == (standard,)
    assert scene in FDMVLLimit.supported_scenes(standard)
    assert len(FDMVLLimit.supported_scenes(standard)) == 10
    assert limit.standard == standard
    assert limit.scene == scene
    assert limit.clause == "4.0.1"
    assert limit.resource_key == "limit_building_fdmvl"
    assert limit.current_units()["fdmvl"] == "decibel"
    assert float(limit.get_field("fdmvl").flat[0]) == expected
    assert limit.fdmvl.shape == ()
    assert limit.axis_field is None
    assert not limit.fdmvl.flags.writeable


def test_fdmvl_standard_rejects_strings_other_enums_and_unknown_scenes() -> None:
    """分频最大振级入口应沿用枚举校验及明确选择场景的合同。"""

    with pytest.raises(TypeError, match="FDMVLLimitStandard"):
        FDMVLLimit.from_standard("JGJ/T 170-2009", scene="居民文教区夜间")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="FDMVLLimitStandard"):
        FDMVLLimit.from_standard(ZVLLimitStandard.GB_10070_1988, scene="居民文教区夜间")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="FDMVLLimitStandard"):
        FDMVLLimit.supported_scenes("JGJ/T 170-2009")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="未找到场景"):
        FDMVLLimit.from_standard(FDMVLLimitStandard.JGJ_T_170_2009, scene="不存在的场景")


def test_limit_h5_preserves_standard_and_chinese_scene(tmp_path: Path) -> None:
    """限值模型经现有 H5 链路重开应保留标准、中文场景和单位。"""

    limit = ZVLLimit.from_standard(ZVLLimitStandard.GB_10070_1988, scene="特殊住宅区昼间")
    target = tmp_path / "limit.h5"
    dt_storage.save_model(limit, target)
    restored = dt_storage.load_model(target, ZVLLimit)

    assert restored.standard == limit.standard
    assert restored.scene == limit.scene
    assert restored.clause == limit.clause
    assert restored.resource_key == limit.resource_key
    assert restored.current_units() == limit.current_units()
    assert float(restored.zvl) == 65.0


def test_fdmvl_scalar_roundtrips_through_registry_and_h5(tmp_path: Path) -> None:
    """标量限值经注册入口及 H5 重开应保留类别、单位和规范来源。"""

    from dyntool.domain.models import model_from_structured_payload

    limit = FDMVLLimit.from_standard(FDMVLLimitStandard.JGJ_T_170_2009, scene="居民文教区夜间")
    target = tmp_path / "fdmvl_limit.h5"
    dt_storage.save_model(limit, target)
    recovered = [
        FDMVLLimit.from_dict(limit.to_dict()),
        model_from_structured_payload(limit.to_structured_payload()),
        dt_storage.load_model(target, FDMVLLimit),
    ]
    for restored in recovered:
        assert isinstance(restored, FDMVLLimit)
        assert restored.category is dt_storage.DataCategory.FDMVL_LIMIT
        assert float(restored.fdmvl) == 62.0
        assert restored.fdmvl.shape == ()
        assert restored.standard is FDMVLLimitStandard.JGJ_T_170_2009
        assert restored.scene == limit.scene
        assert restored.clause == "4.0.1"
        assert restored.resource_key == "limit_building_fdmvl"
        assert restored.current_units() == {"fdmvl": "decibel"}
    assert dt_storage.inspect_model_units(target, FDMVLLimit) == {"fdmvl": "decibel"}


def test_fdmvl_scalar_uses_existing_plot_limit_broadcast() -> None:
    """标量阈值应通过既有绘图入口广播，而不生成新的领域频率轴。"""

    axis = np.array([4.0, 8.0, 16.0, 200.0])
    limit = FDMVLLimit.from_standard(FDMVLLimitStandard.JGJ_T_170_2009, scene="居民文教区夜间")
    dataset = dt_plotting.PlotDataset.from_axis_value(
        axis=axis,
        value=[40, 55, 60, 35],
        name="sample",
        category=dt_plotting.PlotCategory.SAMPLE,
    )
    dataset.add_limit(limit, axis=axis, name="night-limit")
    values = dataset.to_dataframe()[(dt_plotting.PlotCategory.LIMIT.value, "night-limit")].to_numpy()
    np.testing.assert_array_equal(values, [62.0, 62.0, 62.0, 62.0])
    assert limit.axis_field is None
    with pytest.raises(ValueError, match="标量限值需要显式提供 axis"):
        dataset.add_limit(limit, name="without-axis")


def test_fdmvl_explicit_scalar_preserves_units_and_rejects_old_curves() -> None:
    """显式构造及表示单位转换保持阈值；旧曲线载荷不得静默截断。"""

    limit = FDMVLLimit.from_data(
        fdmvl=62.0,
        standard=FDMVLLimitStandard.JGJ_T_170_2009,
        scene="居民文教区夜间",
        clause="4.0.1",
        resource_key="limit_building_fdmvl",
        units={"fdmvl": "dB"},
    )
    converted = limit.convert_units({"fdmvl": "decibel"}, replace=False)
    assert float(converted.fdmvl) == float(limit.fdmvl) == 62.0
    assert converted is not limit
    assert converted.standard is limit.standard
    assert limit.to_pandas().shape == (1, 1)
    legacy = limit.to_dict()
    legacy["freq"] = np.array([4.0, 200.0])
    legacy["fdmvl"] = np.array([62.0, 62.0])
    with pytest.raises(ValueError, match="标量"):
        FDMVLLimit.from_dict(legacy)
    legacy.pop("freq")
    with pytest.raises(ValueError, match="标量"):
        FDMVLLimit.from_dict(legacy)


def test_standard_identifiers_are_canonical_and_legacy_value_is_rejected(tmp_path: Path) -> None:
    """标准只接受统一编号，旧字典、表和 H5 均明确拒绝且不改源文件。"""
    from dyntool.domain.models import model_from_structured_payload

    assert ZVLLimitStandard.GB_10070_1988.value == "GB 10070-1988"
    with pytest.raises(ValueError):
        ZVLLimitStandard("GB_10070-1988")
    limit = ZVLLimit.from_standard(ZVLLimitStandard.GB_10070_1988, scene="特殊住宅区昼间")
    raw = limit.to_dict()
    raw["standard"] = "GB_10070-1988"
    frame = limit.to_pandas()
    frame.attrs["standard"] = "GB_10070-1988"
    payload = limit.to_structured_payload()
    payload.data_vars["standard"] = "GB_10070-1988"
    payload.meta["raw_dict"]["standard"] = "GB_10070-1988"
    target = dt_storage.save_model(limit, tmp_path / "legacy.h5")
    with h5py.File(target, "r+") as handle:
        handle["standard"][()] = "GB_10070-1988"
    for restore in (
        lambda: ZVLLimit.from_dict(raw),
        lambda: ZVLLimit.from_pandas(frame),
        lambda: model_from_structured_payload(payload),
        lambda: dt_storage.load_model(target, ZVLLimit),
    ):
        with pytest.raises((ValueError, BackendError)) as caught:
            restore()
        if isinstance(caught.value, BackendError):
            assert isinstance(caught.value.__cause__, ValueError)
            assert "标准编号" in str(caught.value)
    with h5py.File(target, "r") as handle:
        assert handle["standard"].asstr()[()] == "GB_10070-1988"
    canonical = dt_storage.save_model(limit, tmp_path / "canonical.h5")
    with h5py.File(canonical, "r") as handle:
        assert handle["standard"].asstr()[()] == "GB 10070-1988"
    for restored in (
        ZVLLimit.from_dict(limit.to_dict()),
        ZVLLimit.from_pandas(limit.to_pandas()),
        model_from_structured_payload(limit.to_structured_payload()),
        dt_storage.load_model(canonical, ZVLLimit),
    ):
        assert restored.standard is ZVLLimitStandard.GB_10070_1988
        assert float(restored.zvl) == 65.0
    with pytest.raises(ValueError):
        ZVLLimitStandard("GB_10070-2099")
    with pytest.raises(TypeError):
        ZVLLimit.from_standard("GB 10070-1988", scene="特殊住宅区昼间")  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("standard", "expected"),
    [
        (ZVLLimitStandard.GB_10070_1988, "GB 10070-1988"),
        (ZVLLimitStandard.GB_T_50355_2018, "GB/T 50355-2018"),
        (OTOVLLimitStandard.GB_T_50355_2018, "GB/T 50355-2018"),
        (FPVDVLimitStandard.GB_50868_2013, "GB 50868-2013"),
        (FDMVLLimitStandard.JGJ_T_170_2009, "JGJ/T 170-2009"),
    ],
)
def test_all_standard_values_use_canonical_identifiers(standard, expected: str) -> None:
    """所有评价族输出正式编号，Python 成员名称继续使用下划线。"""
    assert standard.value == expected
    assert "_" in standard.name
    assert "_" not in standard.value


@pytest.mark.parametrize(
    ("model_type", "standard", "scene"),
    [
        (ZVLLimit, ZVLLimitStandard.GB_10070_1988, "特殊住宅区昼间"),
        (OTOVLLimit, OTOVLLimitStandard.GB_T_50355_2018, "卧室昼间一级"),
        (FPVDVLimit, FPVDVLimitStandard.GB_50868_2013, "居住建筑夜间"),
        (FDMVLLimit, FDMVLLimitStandard.JGJ_T_170_2009, "居民文教区夜间"),
    ],
)
def test_limit_dataframe_preserves_source_and_is_independent(model_type, standard, scene: str) -> None:
    """限值数值表应携带独立规范与追溯属性，沿既有接口恢复。"""
    limit = model_type.from_standard(standard, scene=scene)
    frame = limit.to_pandas()
    restored = model_type.from_pandas(frame)
    assert restored.standard is standard
    assert restored.scene == scene
    assert restored.clause == limit.clause
    assert restored.resource_key == limit.resource_key
    assert restored.current_units() == limit.current_units()
    assert restored.to_dict()["_dyntool"] == limit.to_dict()["_dyntool"]
    np.testing.assert_array_equal(restored.get_field(limit.value_field), limit.get_field(limit.value_field))
    frame.iloc[0, 0] += 10
    frame.attrs["_dyntool"]["status"] = "stale"
    assert limit.to_dict()["_dyntool"]["status"] == "unknown"
    assert restored.to_dict()["_dyntool"]["status"] == "unknown"
    np.testing.assert_array_equal(restored.get_field(limit.value_field), limit.get_field(limit.value_field))


@pytest.mark.parametrize(
    ("model_type", "standard", "scene"),
    [
        (ZVLLimit, ZVLLimitStandard.GB_10070_1988, "特殊住宅区昼间"),
        (FPVDVLimit, FPVDVLimitStandard.GB_50868_2013, "居住建筑夜间"),
        (FDMVLLimit, FDMVLLimitStandard.JGJ_T_170_2009, "居民文教区夜间"),
    ],
)
@pytest.mark.parametrize("invalid", [None, [], [1.0, 2.0]])
def test_scalar_limits_reject_missing_empty_or_multiple_values(model_type, standard, scene: str, invalid) -> None:
    """标量限值不能缺值补零、空数组越界或截取多个数值的首项。"""
    limit = model_type.from_standard(standard, scene=scene)
    payload = limit.to_dict()
    if invalid is None:
        payload.pop(limit.value_field)
    else:
        payload[limit.value_field] = invalid
    with pytest.raises(ValueError, match="标量"):
        model_type.from_dict(payload)


@pytest.mark.parametrize(
    ("model_type", "standard", "scene"),
    [
        (ZVLLimit, ZVLLimitStandard.GB_10070_1988, "特殊住宅区昼间"),
        (FPVDVLimit, FPVDVLimitStandard.GB_50868_2013, "居住建筑夜间"),
        (FDMVLLimit, FDMVLLimitStandard.JGJ_T_170_2009, "居民文教区夜间"),
    ],
)
def test_scalar_limit_dataframe_requires_exactly_one_row(model_type, standard, scene: str) -> None:
    """标量数值表的多行输入必须报错，不能当作首行有效的规范阈值。"""
    frame = model_type.from_standard(standard, scene=scene).to_pandas()
    repeated = pd.concat([frame, frame], ignore_index=True)
    with pytest.raises(ValueError, match="一行"):
        model_type.from_pandas(repeated)


@pytest.mark.parametrize(
    ("model_type", "standard", "scene"),
    [
        (ZVLLimit, ZVLLimitStandard.GB_10070_1988, "特殊住宅区昼间"),
        (OTOVLLimit, OTOVLLimitStandard.GB_T_50355_2018, "卧室昼间一级"),
        (FPVDVLimit, FPVDVLimitStandard.GB_50868_2013, "居住建筑夜间"),
        (FDMVLLimit, FDMVLLimitStandard.JGJ_T_170_2009, "居民文教区夜间"),
    ],
)
def test_limit_xarray_preserves_shape_units_source_and_snapshot(model_type, standard, scene: str) -> None:
    """xarray 快照往返不把规范字符串当作数组，也不丢失规范和追溯。"""
    limit = model_type.from_standard(standard, scene=scene)
    snapshot = limit.to_xarray()
    restored = model_type.from_xarray(snapshot)
    assert restored.standard is standard
    assert restored.scene == scene
    assert restored.clause == limit.clause
    assert restored.resource_key == limit.resource_key
    assert restored.current_units() == limit.current_units()
    assert restored.to_dict()["_dyntool"] == limit.to_dict()["_dyntool"]
    np.testing.assert_array_equal(restored.get_field(limit.value_field), limit.get_field(limit.value_field))
    assert snapshot[limit.value_field].shape == limit.get_field(limit.value_field).shape
    array = snapshot[limit.value_field].copy(deep=True)
    array.attrs.update(snapshot.attrs)
    from_array = model_type.from_xarray(array)
    assert from_array.to_dict()["_dyntool"] == limit.to_dict()["_dyntool"]
    assert from_array.standard is standard
    assert from_array.current_units() == limit.current_units()
    np.testing.assert_array_equal(from_array.get_field(limit.value_field), limit.get_field(limit.value_field))
    snapshot[limit.value_field].values[...] += 10
    snapshot.attrs["_dyntool"]["revision"] = "外部编辑"
    np.testing.assert_array_equal(restored.get_field(limit.value_field), limit.get_field(limit.value_field))
    assert limit.to_dict()["_dyntool"]["revision"] != "外部编辑"


def test_limit_xarray_rejects_duplicate_unit_conflict() -> None:
    """同一数值的字段单位和重复单位映射不能使用不同尺度。"""
    limit = FPVDVLimit.from_standard(FPVDVLimitStandard.GB_50868_2013, scene="居住建筑夜间")
    snapshot = limit.to_xarray()
    snapshot.attrs["_units"]["fpvdv"] = "cm/s**1.75"
    with pytest.raises(ValueError, match="不一致"):
        FPVDVLimit.from_xarray(snapshot)
