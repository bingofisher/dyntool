"""规范驱动限值类测试。"""

from __future__ import annotations

import pytest

from dyntool import (
    FDMVLLimit,
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


def test_fdmvl_limit_keeps_structure_placeholder() -> None:
    """分频振级限值当前应保留结构但无预置数据。"""

    assert FDMVLLimit.supported_standards() == ()
